# Despliegue en Servidor EC2

## Datos del servidor
- **OS:** Amazon Linux 2023
- **Usuario SSH:** `ec2-user`
- **Ruta del proyecto:** `~/mqtt-arqui/`

## Instalar Docker en Amazon Linux 2023
```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker
```

### Instalar Docker Compose (manual)
```bash
sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-Linux-x86_64 -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker compose version
```

---

## Estructura de directorios en el servidor

```
~/servidor/
├── docker-compose.nginx.yml      # nginx general (levantar PRIMERO)
├── nginx-general/
│   └── nginx.conf                # enruta /mqtt/ y /compi/
│
├── mqtt-arqui/                   # proyecto IoT MQTT
│   ├── docker-compose.server.yml
│   ├── .env                      # DB_USERNAME, DB_PASSWORD, DB_DATABASE
│   ├── backend.env               # variables del backend FastAPI
│   ├── nginx/
│   │   └── nginx.conf
│   └── mosquitto/
│       └── config/
│
└── compi/                        # proyecto Arquitectura de Computadoras
    ├── docker-compose.server.yml
    └── nginx/
        └── nginx.conf
```

### Copiar archivos desde local
```bash
# nginx general (desde la raiz del proyecto mqtt)
scp -i tu-key.pem docker-compose.nginx.yml ec2-user@<IP-EC2>:~/servidor/
scp -i tu-key.pem -r nginx-general/        ec2-user@<IP-EC2>:~/servidor/

# proyecto mqtt
scp -i tu-key.pem -r ./proyectomqtt ec2-user@<IP-EC2>:~/servidor/mqtt-arqui
```

---

## Levantar el sistema (orden obligatorio)

```bash
# 1. Primero: crea la red proxy_network y levanta el nginx general
cd ~/servidor
docker compose -f docker-compose.nginx.yml up -d

# 2. Proyecto /mqtt
cd ~/servidor/mqtt-arqui
docker compose -f docker-compose.server.yml pull
docker compose -f docker-compose.server.yml up -d

# 3. Proyecto /compi (cuando este listo)
cd ~/servidor/compi
docker compose -f docker-compose.server.yml pull
docker compose -f docker-compose.server.yml up -d

# Ver logs
docker compose -f docker-compose.server.yml logs -f
```

---

## Rutas disponibles

| URL | Descripción |
|-----|-------------|
| `http://IP/mqtt/` | Frontend Angular (proyecto IoT) |
| `http://IP/mqtt/api/` | Backend FastAPI (HTTP) |
| `http://IP/mqtt/ws/` | WebSocket |
| `http://IP/mqttapi/docs` | Swagger UI |
| `http://IP/compi/` | Proyecto Arquitectura de Computadoras |

---

## Puertos a abrir en EC2 Security Group

| Puerto | Uso |
|--------|-----|
| 22 | SSH |
| 80 | HTTP (nginx) |
| 1883 | MQTT (mosquitto) |

---

## Arquitectura de servicios

```
Browser
  │
  ▼ :80
nginx-general  ──── proxy_network ──── iot-nginx   ──── proxy_network ──── frontend (mqtt)
(nginx-general)                    └─ compi-nginx  │                   └─ backend  (mqtt)
                                                   │                         │
                                                   └── mqtt_internal ──── mosquitto
                                                   └── db_network    ──── postgres
```

Imágenes en Docker Hub (`erivas04`):
- `erivas04/backendmqtt:latest`
- `erivas04/frontendmqtt:latest`
