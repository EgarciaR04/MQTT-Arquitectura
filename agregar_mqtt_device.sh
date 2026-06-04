#!/usr/bin/env bash
# =============================================================================
# Script: registrar un dispositivo en Mosquitto (passwd + ACL)
# =============================================================================
# Uso (en el servidor EC2):
#   ./agregar_mqtt_device.sh
#
# Requisitos: Docker corriendo con el contenedor iot-mosquitto
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MOSQUITTO_CONFIG="/opt/stacks/mqtt-arqui/mosquitto/config"

echo -e "${BLUE}=============================================================${NC}"
echo -e "${BLUE}   Registrar dispositivo en Mosquitto (passwd + ACL)${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo

# -----------------------------------------------------------------------------
# Recoger datos
# -----------------------------------------------------------------------------
read -rp "device_id (ej. esp32-jardin-01): " DEVICE_ID
if [[ -z "$DEVICE_ID" ]]; then
    echo -e "${RED}Error: el device_id no puede estar vacío${NC}"
    exit 1
fi

read -rsp "Contraseña MQTT para '$DEVICE_ID': " DEVICE_PASS
echo
if [[ -z "$DEVICE_PASS" ]]; then
    echo -e "${RED}Error: la contraseña no puede estar vacía${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# 1. Agregar usuario al passwd de Mosquitto
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[1/3] Registrando usuario en passwd...${NC}"

docker run --rm \
    -v "${MOSQUITTO_CONFIG}:/mosquitto/config" \
    eclipse-mosquitto:2.0 \
    sh -c "mosquitto_passwd -b /mosquitto/config/passwd '${DEVICE_ID}' '${DEVICE_PASS}'"

echo -e "${GREEN}    Usuario '${DEVICE_ID}' añadido al passwd${NC}"

# -----------------------------------------------------------------------------
# 2. Agregar reglas ACL
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[2/3] Añadiendo reglas ACL...${NC}"

# Verificar si el dispositivo ya tiene entrada en el ACL
if grep -q "^user ${DEVICE_ID}$" "${MOSQUITTO_CONFIG}/acl"; then
    echo -e "${YELLOW}    El dispositivo '${DEVICE_ID}' ya tiene reglas ACL, se omite${NC}"
else
    cat >> "${MOSQUITTO_CONFIG}/acl" <<EOF

user ${DEVICE_ID}
topic write devices/${DEVICE_ID}/telemetry
topic write devices/${DEVICE_ID}/status
topic read  devices/${DEVICE_ID}/commands
topic read  devices/${DEVICE_ID}/ota
EOF
    echo -e "${GREEN}    Reglas ACL añadidas para '${DEVICE_ID}'${NC}"
fi

# -----------------------------------------------------------------------------
# 3. Reiniciar Mosquitto para aplicar cambios
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[3/3] Reiniciando Mosquitto...${NC}"

docker restart iot-mosquitto

echo -e "${GREEN}    Mosquitto reiniciado${NC}"

# -----------------------------------------------------------------------------
# Resumen
# -----------------------------------------------------------------------------
echo
echo -e "${BLUE}=============================================================${NC}"
echo -e "${GREEN}Dispositivo registrado en Mosquitto${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo "  device_id:    ${DEVICE_ID}"
echo "  Tópicos:      devices/${DEVICE_ID}/telemetry  (write)"
echo "                devices/${DEVICE_ID}/status     (write)"
echo "                devices/${DEVICE_ID}/commands   (read)"
echo
echo -e "${YELLOW}Recuerda también registrar el dispositivo en el backend con:${NC}"
echo "  ./agregar_dipositivo.sh"
echo
