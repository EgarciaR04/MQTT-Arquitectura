#!/usr/bin/env bash
# =============================================================================
# Script de provisión: crea usuario y registra dispositivos en el backend IoT
# =============================================================================
# Uso:
#   ./provision_user.sh
#
# El script preguntará interactivamente por:
#   - URL del backend (por defecto: http://198.199.86.232/api)
#   - Email y contraseña del usuario
#   - Dispositivos a registrar (puede añadir varios)
#
# Requisitos: curl, jq
#   sudo apt install curl jq
# =============================================================================

set -euo pipefail

# Colores para que se lea mejor
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # sin color

# Valores por defecto
DEFAULT_BACKEND="http://78.13.114.116/mqttapi"

echo -e "${BLUE}=============================================================${NC}"
echo -e "${BLUE}   Provisión de usuario + dispositivos en backend IoT${NC}"
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
# Recoger datos del usuario
# -----------------------------------------------------------------------------
read -rp "URL del backend [$DEFAULT_BACKEND]: " BACKEND_URL
BACKEND_URL=${BACKEND_URL:-$DEFAULT_BACKEND}

# Quitar barra final si la tiene
BACKEND_URL=${BACKEND_URL%/}

echo
read -rp "Email del nuevo usuario: " USER_EMAIL
if [[ -z "$USER_EMAIL" ]]; then
    echo -e "${RED}Error: el email no puede estar vacío${NC}"
    exit 1
fi

read -rsp "Contraseña (mínimo 8 caracteres): " USER_PASSWORD
echo
if [[ ${#USER_PASSWORD} -lt 8 ]]; then
    echo -e "${RED}Error: la contraseña debe tener al menos 8 caracteres${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# 1. Registrar el usuario
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[1/3] Registrando usuario...${NC}"

REGISTER_RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"$USER_PASSWORD\"}")

HTTP_CODE=$(echo "$REGISTER_RESPONSE" | tail -n1)
BODY=$(echo "$REGISTER_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "201" ]]; then
    echo -e "${GREEN}    Usuario creado correctamente${NC}"
elif [[ "$HTTP_CODE" == "400" ]] || [[ "$HTTP_CODE" == "409" ]]; then
    echo -e "${YELLOW}    El usuario ya existe, continuando con login...${NC}"
else
    echo -e "${RED}    Error ($HTTP_CODE): $BODY${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# 2. Hacer login para obtener el JWT
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[2/3] Obteniendo token JWT...${NC}"

LOGIN_RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$USER_EMAIL&password=$USER_PASSWORD")

HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
    echo -e "${RED}    Error ($HTTP_CODE) al hacer login: $BODY${NC}"
    exit 1
fi

TOKEN=$(echo "$BODY" | jq -r '.access_token')
if [[ -z "$TOKEN" ]] || [[ "$TOKEN" == "null" ]]; then
    echo -e "${RED}    Error: no se pudo extraer el token de la respuesta${NC}"
    echo "$BODY"
    exit 1
fi

echo -e "${GREEN}    Token obtenido${NC}"

# -----------------------------------------------------------------------------
# 3. Registrar dispositivos en bucle
# -----------------------------------------------------------------------------
echo
echo -e "${YELLOW}[3/3] Registro de dispositivos${NC}"
echo "Puedes añadir varios dispositivos. Deja el device_id vacío para terminar."
echo

DEVICE_COUNT=0

while true; do
    echo "--- Dispositivo #$((DEVICE_COUNT + 1)) ---"

    read -rp "  device_id (vacío para terminar): " DEVICE_ID
    if [[ -z "$DEVICE_ID" ]]; then
        break
    fi

    read -rp "  Nombre legible: " DEVICE_NAME
    DEVICE_NAME=${DEVICE_NAME:-$DEVICE_ID}

    read -rp "  Usuario MQTT [$DEVICE_ID]: " MQTT_USER
    MQTT_USER=${MQTT_USER:-$DEVICE_ID}

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
        echo -e "  ${GREEN}Dispositivo '$DEVICE_ID' registrado${NC}"
        DEVICE_COUNT=$((DEVICE_COUNT + 1))
    elif [[ "$HTTP_CODE" == "400" ]] || [[ "$HTTP_CODE" == "409" ]]; then
        echo -e "  ${YELLOW}El dispositivo '$DEVICE_ID' ya existe${NC}"
    else
        echo -e "  ${RED}Error ($HTTP_CODE): $BODY${NC}"
    fi

    echo
done

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo
echo -e "${BLUE}=============================================================${NC}"
echo -e "${GREEN}Provisión completada${NC}"
echo -e "${BLUE}=============================================================${NC}"
echo "  Usuario:       $USER_EMAIL"
echo "  Dispositivos:  $DEVICE_COUNT registrados"
echo
echo -e "${YELLOW}IMPORTANTE — pasos manuales pendientes en el droplet:${NC}"
echo
echo "Por cada dispositivo registrado, necesitas crear su usuario MQTT en"
echo "Mosquitto y añadirle reglas ACL. En el droplet ejecuta:"
echo
echo "  ssh root@198.199.86.232"
echo "  cd /opt/stacks/iot-sistema-riego"
echo
echo "  # 1. Crear usuario MQTT (repite para cada dispositivo)"
echo "  docker run --rm --user root \\"
echo "      -v \"\$(pwd)/mosquitto/config:/mosquitto/config\" \\"
echo "      eclipse-mosquitto:2.0 \\"
echo "      mosquitto_passwd -b /mosquitto/config/passwd DEVICE_ID DEVICE_PASS"
echo
echo "  # 2. Añadir bloque ACL al archivo mosquitto/config/acl:"
echo "  user DEVICE_ID"
echo "  topic write devices/DEVICE_ID/telemetry"
echo "  topic write devices/DEVICE_ID/status"
echo "  topic read  devices/DEVICE_ID/commands"
echo
echo "  # 3. Reiniciar Mosquitto"
echo "  docker compose restart mosquitto"
echo
