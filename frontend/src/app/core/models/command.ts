export interface CommandRequest {
  payload: {
    minHumedad?: number;
    [key: string]: any;   // permite futuras extensiones
  };
}

export interface CommandResponse {
  sent: boolean;
  device_id: string;
}
