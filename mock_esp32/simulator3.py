"""
Simulador de ESP32 — versión con 2 sensores de humedad y control automático de LEDs.

Telemetría publicada:
{
    "humedad1": float,
    "humedad2": float,
    "ledRojo1": bool, "ledVerde1": bool,
    "ledRojo2": bool, "ledVerde2": bool,
    "minHumedad": float,
    "timestamp": str
}

Comandos aceptados:
    { "minHumedad": <float> }

Lógica de control (igual que la del firmware real):
    Para cada sensor N (1 y 2):
        si humedadN < minHumedad:  ledRojoN=True,  ledVerdeN=False
        sino:                      ledRojoN=False, ledVerdeN=True

Los LEDs NO se pueden controlar por comando — son consecuencia del estado físico.
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import aiomqtt

# === Conexión ===
MQTT_HOST = "198.199.86.232"
MQTT_PORT = 1883
DEVICE_ID = "device003"
MQTT_USER = DEVICE_ID
MQTT_PASS = "device003pass"

# === Comportamiento ===
SENSOR_READ_INTERVAL = 2.0
THRESHOLD_HUMIDITY = 0.3       # %  — variación mínima de humedad para publicar

# === Tópicos ===
TELEMETRY_TOPIC = f"devices/{DEVICE_ID}/telemetry"
STATUS_TOPIC = f"devices/{DEVICE_ID}/status"
COMMANDS_TOPIC = f"devices/{DEVICE_ID}/commands"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("mock_esp32")

# === Estado de control (modificable por comando) ===
control = {
    "minHumedad": 50.0,
}

# === Estado físico simulado ===
sensors = {
    "humedad1": 55.0,
    "humedad2": 55.0,
}

last_published: dict | None = None
state_changed_event = asyncio.Event()


def evaluate_leds(humedad: float, min_h: float) -> tuple[bool, bool]:
    """Lógica de control idéntica a la del ESP32 real."""
    if humedad < min_h:
        return True, False     # rojo, verde
    else:
        return False, True


def read_sensors_and_apply_control() -> dict:
    """
    Lee los dos sensores (random walk acotado) y aplica la lógica de control
    para decidir el estado de los 4 LEDs.
    """
    # Random walk acotado para cada sensor
    sensors["humedad1"] += random.uniform(-0.8, 0.8)
    sensors["humedad1"] = max(20.0, min(90.0, sensors["humedad1"]))

    sensors["humedad2"] += random.uniform(-0.8, 0.8)
    sensors["humedad2"] = max(20.0, min(90.0, sensors["humedad2"]))

    min_h = control["minHumedad"]
    rojo1, verde1 = evaluate_leds(sensors["humedad1"], min_h)
    rojo2, verde2 = evaluate_leds(sensors["humedad2"], min_h)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "humedad1": round(sensors["humedad1"], 1),
        "humedad2": round(sensors["humedad2"], 1),
        "ledRojo1": rojo1,
        "ledVerde1": verde1,
        "ledRojo2": rojo2,
        "ledVerde2": verde2,
        "minHumedad": min_h,
    }


def has_significant_change(new: dict, last: dict | None) -> bool:
    """Publica si algún booleano cambió o si una humedad varió más del umbral."""
    if last is None:
        return True

    # Cualquier cambio en los LEDs o en minHumedad: publicar
    for key in ("ledRojo1", "ledVerde1", "ledRojo2", "ledVerde2", "minHumedad"):
        if new[key] != last[key]:
            return True

    # Cambios analógicos: solo si superan el umbral
    if abs(new["humedad1"] - last["humedad1"]) > THRESHOLD_HUMIDITY:
        return True
    if abs(new["humedad2"] - last["humedad2"]) > THRESHOLD_HUMIDITY:
        return True

    return False


def apply_command(payload: dict) -> None:
    """Solo acepta cambios en minHumedad. Los LEDs los decide el dispositivo."""
    if "minHumedad" not in payload:
        logger.warning("Comando ignorado, no contiene 'minHumedad': %s", payload)
        return

    try:
        new_val = float(payload["minHumedad"])
    except (TypeError, ValueError):
        logger.warning("Valor de minHumedad inválido: %r", payload["minHumedad"])
        return

    if new_val != control["minHumedad"]:
        control["minHumedad"] = new_val
        logger.info("minHumedad -> %s", new_val)
        state_changed_event.set()


async def publisher_loop(client: aiomqtt.Client) -> None:
    global last_published
    while True:
        try:
            await asyncio.wait_for(
                state_changed_event.wait(), timeout=SENSOR_READ_INTERVAL
            )
            state_changed_event.clear()
        except asyncio.TimeoutError:
            pass

        new_reading = read_sensors_and_apply_control()
        if has_significant_change(new_reading, last_published):
            await client.publish(TELEMETRY_TOPIC, json.dumps(new_reading), qos=1)
            logger.info("→ Publicado: %s", new_reading)
            last_published = new_reading


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
                logger.info(
                    "Listo. minHumedad inicial=%s — publicando solo en cambios.",
                    control["minHumedad"],
                )

                async with asyncio.TaskGroup() as tg:
                    tg.create_task(publisher_loop(client))
                    tg.create_task(command_listener(client))

        except aiomqtt.MqttError as e:
            logger.error("Conexión perdida: %s. Reintento en 5s.", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Saliendo...")
