"""
Simulador de ESP32.

Hace exactamente lo que hará el ESP32 real:
- Publica telemetría cada 5 segundos en devices/{DEVICE_ID}/telemetry
- Publica "online" en devices/{DEVICE_ID}/status al conectar
- Configura Last Will Testament para que el broker publique "offline"
  automáticamente si la conexión se cae
- Se suscribe a devices/{DEVICE_ID}/commands y muestra lo que recibe
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import aiomqtt

# === Configuración ===
MQTT_HOST = "localhost"
MQTT_PORT = 1883
DEVICE_ID = "device001"
MQTT_USER = DEVICE_ID
MQTT_PASS = "device001pass"
PUBLISH_INTERVAL = 5

TELEMETRY_TOPIC = f"devices/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"devices/{DEVICE_ID}/status"
COMMANDS_TOPIC = f"devices/{DEVICE_ID}/commands"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("mock_esp32")

# Estado simulado del dispositivo (se modifica vía comandos)
state = {
    "led": False,
    "setpoint": 22.0,
}


def generate_telemetry() -> dict:
    """Genera una lectura simulada con valores realistas."""
    base_temp = state["setpoint"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperatura": round(base_temp + random.uniform(-1.5, 1.5), 2),
        "humedad": round(random.uniform(45, 65), 1),
        "presion": round(random.uniform(1010, 1020), 1),
        "led": state["led"],
        "setpoint": state["setpoint"],
    }


def apply_command(payload: dict) -> None:
    """Aplica un comando recibido al estado del dispositivo."""
    if "led" in payload:
        state["led"] = bool(payload["led"])
        logger.info("LED -> %s", state["led"])
    if "setpoint" in payload:
        state["setpoint"] = float(payload["setpoint"])
        logger.info("Setpoint -> %s", state["setpoint"])


async def publisher_loop(client: aiomqtt.Client) -> None:
    """Publica telemetría periódicamente."""
    while True:
        telemetry = generate_telemetry()
        await client.publish(TELEMETRY_TOPIC, json.dumps(telemetry), qos=1)
        logger.info("→ %s: %s", TELEMETRY_TOPIC, telemetry)
        await asyncio.sleep(PUBLISH_INTERVAL)


async def command_listener(client: aiomqtt.Client) -> None:
    """Escucha y procesa comandos."""
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
                keepalive=10
            ) as client:
                logger.info("Conectado al broker como %s", MQTT_USER)

                # Anunciar online (retenido para que nuevos suscriptores lo vean)
                await client.publish(STATUS_TOPIC, b"online", qos=1, retain=True)

                await client.subscribe(COMMANDS_TOPIC, qos=1)
                logger.info("Suscrito a %s", COMMANDS_TOPIC)

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