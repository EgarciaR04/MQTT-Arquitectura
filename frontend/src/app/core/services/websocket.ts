import { Injectable, inject } from '@angular/core';
import { Subject, Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Auth } from './auth';
import { WebSocketMessage } from '../models/telemetry';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected';

@Injectable({ providedIn: 'root' })
export class Websocket {

  private auth = inject(Auth);

  private socket: WebSocket | null = null;
  private currentDeviceId: string | null = null;
  private shouldReconnect = false;
  private reconnectTimer: any = null;

  // Subjects: como Observables pero también emiten valores manualmente.
  // Los componentes se suscriben a estos para recibir mensajes y estado.
  private messages$ = new Subject<WebSocketMessage>();
  private state$ = new Subject<ConnectionState>();

  /** Stream de mensajes que llegan del backend. */
  onMessage(): Observable<WebSocketMessage> {
    return this.messages$.asObservable();
  }

  /** Stream de cambios de estado de conexión. */
  onStateChange(): Observable<ConnectionState> {
    return this.state$.asObservable();
  }

  /**
   * Abre la conexión al WebSocket del dispositivo indicado.
   * Si ya hay una conexión a otro dispositivo, la cierra antes.
   */
  connect(deviceId: string): void {
    const token = this.auth.getToken();
    if (!token) {
      console.error('[WS] No hay token, abortando');
      return;
    }

    // Si ya estamos conectados al mismo, no hacer nada
    if (this.socket && this.currentDeviceId === deviceId &&
        this.socket.readyState === WebSocket.OPEN) {
      return;
    }

    this.disconnect();

    this.currentDeviceId = deviceId;
    this.shouldReconnect = true;
    this.openSocket();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close(1000, 'client closed');
      this.socket = null;
    }
    this.currentDeviceId = null;
  }

  private openSocket(): void {
    const token = this.auth.getToken();
    if (!token || !this.currentDeviceId) return;

    const url = `${environment.wsUrl}/${this.currentDeviceId}?token=${token}`;
    console.log('[WS] Conectando a', url);
    this.state$.next('connecting');

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log('[WS] Conectado');
      this.state$.next('connected');
    };

    this.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WebSocketMessage;
        this.messages$.next(msg);
      } catch (e) {
        console.warn('[WS] Mensaje no parseable:', event.data);
      }
    };

    this.socket.onerror = (e) => {
      console.error('[WS] Error', e);
    };

    this.socket.onclose = (event) => {
      console.log('[WS] Cerrado:', event.code, event.reason);
      this.socket = null;
      this.state$.next('disconnected');
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        console.log('[WS] Reintentando...');
        this.openSocket();
      }
    }, 3000);
  }
}
