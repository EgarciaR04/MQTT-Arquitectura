# ===== Etapa 1: Build =====
FROM node:22-alpine AS builder

WORKDIR /app

# Instalar dependencias primero (caché de capas Docker)
COPY package*.json ./
RUN npm ci

# Copiar el resto del proyecto y compilar
COPY . .
RUN npm run build -- --configuration production --base-href /mqtt/

# ===== Etapa 2: Runtime =====
FROM nginx:1.27-alpine

# Borrar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Nuestra configuración personalizada
COPY nginx.conf /etc/nginx/conf.d/iot.conf

# Copiar el bundle compilado desde la etapa builder.
# La ruta dentro de dist depende del nombre del proyecto en angular.json
# (normalmente dist/frontend/browser en Angular 17+).
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
