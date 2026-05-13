"""Esquemas Pydantic (validación de entrada/salida del API)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: str


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    mqtt_username: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    name: str
    mqtt_username: str
    created_at: datetime


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    timestamp: datetime
    payload: dict[str, Any]


class CommandRequest(BaseModel):
    payload: dict[str, Any]


class CommandResponse(BaseModel):
    sent: bool
    device_id: str