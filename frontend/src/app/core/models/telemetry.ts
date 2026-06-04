/**
 * Payload exacto que publica el ESP32/simulador.
 * Las claves coinciden 1:1 con el JSON.
 */
export interface TelemetryPayload {
  humedad1: number;
  humedad2: number;
  ledRojo1: boolean;
  ledVerde1: boolean;
  ledRojo2: boolean;
  ledVerde2: boolean;
  minHumedad: number;
  timestamp: string;

  // Control de bomba (firmware actual y futuro)
  // Son opcionales para no romper si llega un payload antiguo.
  bombaActiva?: boolean;        // estado real: bomba girando o no
  bombaBloqueada?: boolean;     // modo manual: NO se enciende pase lo que pase
  bombaForzada?: boolean;       // modo manual: se mantiene encendida
}

/**
 * Una entrada de telemetría tal como la devuelve
 * GET /devices/{deviceId}/telemetry
 */
export interface TelemetryRecord {
  id: number;
  device_id: number;
  timestamp: string;
  payload: TelemetryPayload;
}

/**
 * Mensajes que llegan por WebSocket.
 * Pueden ser de tipo "telemetry" o "status".
 */
export interface WebSocketMessage {
  type: 'telemetry' | 'status';
  device_id: string;
  timestamp?: string;
  payload?: TelemetryPayload;
  status?: 'online' | 'offline' | 'updating';
}
