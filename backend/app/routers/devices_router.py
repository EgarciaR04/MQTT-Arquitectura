"""Endpoints de dispositivos."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import CommandLog, Device, Telemetry, User
from app.mqtt_handler import publish_command
from app.schemas import (
    CommandRequest, CommandResponse,
    DeviceCreate, DeviceOut, TelemetryOut,
)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    result = await db.execute(select(Device).where(Device.owner_id == user.id))
    return list(result.scalars().all())


@router.post("", response_model=DeviceOut, status_code=201)
async def create_device(
    data: DeviceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Device:
    existing = await db.execute(select(Device).where(Device.device_id == data.device_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="device_id ya está registrado")

    device = Device(
        device_id=data.device_id,
        name=data.name,
        mqtt_username=data.mqtt_username,
        owner_id=user.id,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}/telemetry", response_model=list[TelemetryOut])
async def get_telemetry(
    device_id: str,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Telemetry]:
    device = await _get_user_device(db, user, device_id)
    result = await db.execute(
        select(Telemetry)
        .where(Telemetry.device_id == device.id)
        .order_by(desc(Telemetry.timestamp))
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("/{device_id}/command", response_model=CommandResponse)
async def send_command(
    device_id: str,
    command: CommandRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    device = await _get_user_device(db, user, device_id)
    sent = await publish_command(device.device_id, command.payload)
    if not sent:
        raise HTTPException(status_code=503, detail="Broker MQTT no disponible")

    log = CommandLog(device_id=device.id, user_id=user.id, payload=command.payload)
    db.add(log)
    await db.commit()
    return CommandResponse(sent=True, device_id=device.device_id)


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