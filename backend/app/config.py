"""Configuración cargada desde variables de entorno (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = "backend"
    mqtt_pass: str = "backendpass"

    cors_origins: str = "*"

    public_base_url: str = "http://localhost/mqtt/api"
    firmware_storage_path: str = "/app/firmware"


settings = Settings()