#!/usr/bin/env bash
# =============================================================================
# Script: añadir un dispositivo a un usuario existente
# =============================================================================
# Uso:
#   ./add_device.sh
#
# El script preguntará interactivamente por:
#   - URL del backend (por defecto: http://198.199.86.232/api)
#   - Email y contraseña del usuario existente
#   - Datos del dispositivo a registrar
#
# Requisitos: curl, jq
#   sudo apt install curl jq
# =============================================================================

set -euo pipefail

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEFAULT_BACKEND="http://198.199.86.232/mqttapi"

echo -e "${BLUE}=============================================================${NC}"
echo -e "${BLUE}   Añadir dispositivo a usuario existente${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo

# -----------------------------------------------------------------------------
# Verificar dependencias
# -----------------------------------------------------------------------------
for cmd in curl jq; do
    if ! command -v "$cmd" &> /dev/null; then
        echo -e "${RED}Error: '$cmd' no está instalado. Instálalo con:${NC}"
        echo "  sudo apt install $cmd"
        exit 1
    fi
done

# -----------------------------------------------------------------------------
# Recoger datos
# -----------------------------------------------------------------------------
read -rp "URL del backend [$DEFAULT_BACKEND]: " BACKEND_URL
BACKEND_URL=${BACKEND_URL:-$DEFAULT_BACKEND}
BACKEND_URL=${BACKEND_URL%/}

echo
echo -e "${YELLOW}Credenciales del usuario al que se asignará el dispositivo:${NC}"
read -rp "  Email: " USER_EMAIL
if [[ -z "$USER_EMAIL" ]]; then
    echo -e "${RED}Error: el email no puede estar vacío${NC}"
    exit 1
fi

read -rsp "  Contraseña: " USER_PASSWORD
echo
if [[ -z "$USER_PASSWORD" ]]; then
    echo -e "${RED}Error: la contraseña no puede estar vacía${NC}"
    exit 1
fi

echo
echo -e "${YELLOW}Datos del dispositivo:${NC}"
read -rp "  device_id (ej. esp32-jardin-01): " DEVICE_ID
if [[ -z "$DEVICE_ID" ]]; then
    echo -e "${RED}Error: el device_id no puede estar vacío${NC}"
    exit 1
fi

read -rp "  Nombre legible [$DEVICE_ID]: " DEVICE_NAME
DEVICE_NAME=${DEVICE_NAME:-$DEVICE_ID}

read -rp "  Usuario MQTT [$DEVICE_ID]: " MQTT_USER
MQTT_USER=${MQTT_USER:-$DEVICE_ID}

# -----------------------------------------------------------------------------
# 1. Login para obtener JWT
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[1/2] Autenticando usuario...${NC}"

LOGIN_RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$USER_EMAIL&password=$USER_PASSWORD")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
    echo -e "${RED}    Error ($HTTP_CODE) al hacer login: $BODY${NC}"
    echo -e "${RED}    Verifica que el usuario exista y la contraseña sea correcta${NC}"
    exit 1
fi

TOKEN=$(echo "$BODY" | jq -r '.access_token')
if [[ -z "$TOKEN" ]] || [[ "$TOKEN" == "null" ]]; then
    echo -e "${RED}    Error: no se pudo extraer el token de la respuesta${NC}"
    echo "$BODY"
    exit 1
fi

echo -e "${GREEN}    Login correcto${NC}"

# -----------------------------------------------------------------------------
# 2. Registrar el dispositivo
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[2/2] Registrando dispositivo...${NC}"

PAYLOAD=$(jq -n \
    --arg id "$DEVICE_ID" \
    --arg name "$DEVICE_NAME" \
    --arg muser "$MQTT_USER" \
    '{device_id: $id, name: $name, mqtt_username: $muser}')

REGISTER_DEV=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/devices" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

HTTP_CODE=$(echo "$REGISTER_DEV" | tail -n1)
BODY=$(echo "$REGISTER_DEV" | sed '$d')

if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "201" ]]; then
    echo -e "${GREEN}    Dispositivo '$DEVICE_ID' registrado correctamente${NC}"
elif [[ "$HTTP_CODE" == "400" ]] || [[ "$HTTP_CODE" == "409" ]]; then
    echo -e "${YELLOW}    El dispositivo '$DEVICE_ID' ya existe en el sistema${NC}"
    echo -e "${YELLOW}    (puede pertenecer a este u otro usuario)${NC}"
    exit 1
else
    echo -e "${RED}    Error ($HTTP_CODE): $BODY${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Resumen
# -----------------------------------------------------------------------------
echo
echo -e "${BLUE}=============================================================${NC}"
echo -e "${GREEN}Dispositivo registrado en el backend${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo "  Usuario:        $USER_EMAIL"
echo "  device_id:      $DEVICE_ID"
echo "  Nombre:         $DEVICE_NAME"
echo "  Usuario MQTT:   $MQTT_USER"
echo
echo -e "${YELLOW}Pendiente: dar de alta el usuario MQTT en Mosquitto.${NC}"
echo "Usa el script add_mqtt_device.sh para hacerlo en el droplet."
echo
