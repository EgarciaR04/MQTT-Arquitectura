"""
Simulador de ESP32 — versión event-driven.

Publica telemetría SOLO cuando hay cambio significativo:
- Cambio discreto (LED, setpoint) -> publica inmediatamente.
- Cambio analógico (temperatura/humedad/presión) -> publica si supera umbral.
- En estado estable, el simulador queda silencioso. El estado "online" del
  Last Will Testament sigue indicando que está vivo.
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import aiomqtt

# === Configuración de conexión ===
MQTT_HOST = "198.199.86.232"   # IP del droplet
MQTT_PORT = 1883
DEVICE_ID = "device001"
MQTT_USER = DEVICE_ID
MQTT_PASS = "device001pass"

# === Comportamiento ===
SENSOR_READ_INTERVAL = 2.0     # cada cuánto leer sensores internamente
THRESHOLD_TEMP = 0.5           # °C
THRESHOLD_HUMIDITY = 2.0       # %
THRESHOLD_PRESSURE = 1.0       # hPa

# Tópicos
TELEMETRY_TOPIC = f"devices/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"devices/{DEVICE_ID}/status"
COMMANDS_TOPIC = f"devices/{DEVICE_ID}/commands"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("mock_esp32")

# Estado de control (modificable por comandos)
state = {
    "led": False,
    "setpoint": 22.0,
}

# Estado físico simulado (lo que "leen" los sensores)
sensors = {
    "temperatura": 22.0,
    "humedad": 55.0,
    "presion": 1015.0,
}

# Última lectura publicada (para comparar)
last_published: dict | None = None

# Evento que dispara publicación inmediata desde apply_command()
state_changed_event = asyncio.Event()


def read_sensors() -> dict:
    """
    Simula la lectura del hardware:
    - Temperatura deriva hacia el setpoint (10% por tick) + ruido bajo el umbral.
    - Humedad y presión hacen pequeño random walk acotado.
    """
    # Termostato: la temperatura se acerca al setpoint
    sensors["temperatura"] += (state["setpoint"] - sensors["temperatura"]) * 0.1
    sensors["temperatura"] += random.uniform(-0.05, 0.05)

    sensors["humedad"] += random.uniform(-0.3, 0.3)
    sensors["humedad"] = max(40.0, min(70.0, sensors["humedad"]))

    sensors["presion"] += random.uniform(-0.1, 0.1)
    sensors["presion"] = max(1005.0, min(1025.0, sensors["presion"]))

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperatura": round(sensors["temperatura"], 2),
        "humedad": round(sensors["humedad"], 1),
        "presion": round(sensors["presion"], 1),
        "led": state["led"],
        "setpoint": state["setpoint"],
    }


def has_significant_change(new: dict, last: dict | None) -> bool:
    """Decide si una lectura nueva amerita publicación."""
    if last is None:
        return True

    # Cambios discretos: siempre publicar
    if new["led"] != last["led"]:
        return True
    if new["setpoint"] != last["setpoint"]:
        return True

    # Cambios analógicos: solo si superan el umbral
    if abs(new["temperatura"] - last["temperatura"]) > THRESHOLD_TEMP:
        return True
    if abs(new["humedad"] - last["humedad"]) > THRESHOLD_HUMIDITY:
        return True
    if abs(new["presion"] - last["presion"]) > THRESHOLD_PRESSURE:
        return True

    return False


def apply_command(payload: dict) -> None:
    """Aplica un comando recibido. Si cambia el estado, dispara publicación."""
    changed = False
    if "led" in payload:
        new_val = bool(payload["led"])
        if new_val != state["led"]:
            state["led"] = new_val
            logger.info("LED -> %s", state["led"])
            changed = True
    if "setpoint" in payload:
        new_val = float(payload["setpoint"])
        if new_val != state["setpoint"]:
            state["setpoint"] = new_val
            logger.info("Setpoint -> %s", state["setpoint"])
            changed = True
    if changed:
        state_changed_event.set()


async def publisher_loop(client: aiomqtt.Client) -> None:
    """
    Bucle event-driven:
    - Despierta cada SENSOR_READ_INTERVAL para leer sensores.
    - O despierta antes si un comando dispara state_changed_event.
    - Solo publica si has_significant_change() retorna True.
    """
    global last_published

    while True:
        # Esperar el siguiente tick o un cambio de estado
        try:
            await asyncio.wait_for(
                state_changed_event.wait(), timeout=SENSOR_READ_INTERVAL
            )
            state_changed_event.clear()
        except asyncio.TimeoutError:
            pass

        new_reading = read_sensors()
        if has_significant_change(new_reading, last_published):
            await client.publish(
                TELEMETRY_TOPIC, json.dumps(new_reading), qos=1
            )
            logger.info("→ Publicado: %s", new_reading)
            last_published = new_reading
        # else: silencio


async def command_listener(client: aiomqtt.Client) -> None:
    async for message in client.messages:
        if str(message.topic) != COMMANDS_TOPIC:
            continue
        try:
            payload = json.loads(message.payload.decode())
            logger.info("← Comando recibido: %s", payload)
            apply_command(payload)
        except json.JSONDecodeError:
            logger.warning("Comando no es JSON válido: %r", message.payload)


async def main() -> None:
    will = aiomqtt.Will(
        topic=STATUS_TOPIC,
        payload=b"offline",
        qos=1,
        retain=True,
    )

    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_HOST,
                port=MQTT_PORT,
                username=MQTT_USER,
                password=MQTT_PASS,
                will=will,
                identifier=f"mock-{DEVICE_ID}",
                keepalive=15,
            ) as client:
                logger.info("Conectado al broker como %s", MQTT_USER)
                await client.publish(STATUS_TOPIC, b"online", qos=1, retain=True)
                await client.subscribe(COMMANDS_TOPIC, qos=1)
                logger.info("Modo event-driven activo. Publicando solo en cambios.")

                async with asyncio.TaskGroup() as tg:
                    tg.create_task(publisher_loop(client))
                    tg.create_task(command_listener(client))

        except aiomqtt.MqttError as e:
            logger.error("Conexión perdida: %s. Reintentando en 5s...", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Saliendo...")