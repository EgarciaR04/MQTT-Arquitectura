"""Endpoints de gestión de firmware OTA para dispositivos ESP32."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Device, FirmwareRelease, User
from app.mqtt_handler import publish_ota_available
from app.schemas import FirmwareOut

router = APIRouter(tags=["firmware"])

_STORAGE = Path(settings.firmware_storage_path)
_MAX_SIZE = 4 * 1024 * 1024  # 4 MB


def _ensure_storage() -> None:
    _STORAGE.mkdir(parents=True, exist_ok=True)


async def _get_user_device(db: AsyncSession, user: User, device_id: str) -> Device:
    result = await db.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.owner_id == user.id,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return device


@router.post("/devices/{device_id}/firmware", response_model=FirmwareOut, status_code=201)
async def upload_firmware(
    device_id: str,
    version: str = Form(..., description="Versión del firmware, ej: 1.0.0"),
    file: UploadFile = File(..., description="Binario compilado (.bin)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FirmwareOut:
    """
    Sube un binario .bin para el dispositivo indicado y notifica al ESP32
    vía MQTT que hay una actualización disponible.
    """
    if not (file.filename or "").lower().endswith(".bin"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .bin")

    device = await _get_user_device(db, user, device_id)

    contents = await file.read()
    if len(contents) > _MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {_MAX_SIZE // 1024 // 1024} MB",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    _ensure_storage()
    safe_name = f"{device_id}_{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    file_path = _STORAGE / safe_name

    with open(file_path, "wb") as f:
        f.write(contents)

    release = FirmwareRelease(
        device_id=device.id,
        version=version,
        original_filename=file.filename,
        file_path=str(file_path),
        file_size=len(contents),
        status="ready",
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)

    download_url = f"{settings.public_base_url}/firmware/{release.id}/binary"
    sent = await publish_ota_available(
        device_id=device.device_id,
        firmware_id=release.id,
        version=version,
        url=download_url,
        size=len(contents),
    )

    if sent:
        release.status = "notified"
        release.notified_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(release)

    return release


@router.get("/devices/{device_id}/firmware", response_model=list[FirmwareOut])
async def list_firmware(
    device_id: str,
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FirmwareRelease]:
    """Devuelve el historial de firmware subido para un dispositivo."""
    device = await _get_user_device(db, user, device_id)
    result = await db.execute(
        select(FirmwareRelease)
        .where(FirmwareRelease.device_id == device.id)
        .order_by(desc(FirmwareRelease.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/firmware/{firmware_id}/binary", include_in_schema=False)
async def download_binary(firmware_id: int, db: AsyncSession = Depends(get_db)):
    """
    Descarga el binario. Sin autenticación JWT para que el ESP32 pueda
    hacer la petición HTTP directamente desde su código OTA.
    """
    result = await db.execute(
        select(FirmwareRelease).where(FirmwareRelease.id == firmware_id)
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=404, detail="Firmware no encontrado")

    if not os.path.isfile(release.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

    return FileResponse(
        path=release.file_path,
        media_type="application/octet-stream",
        filename=release.original_filename,
    )
