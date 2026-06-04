import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { DecimalPipe, SlicePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';

import { Api } from '../../core/services/api';
import { Websocket, ConnectionState } from '../../core/services/websocket';
import {
  TelemetryPayload,
  WebSocketMessage,
} from '../../core/models/telemetry';
import { FirmwareRelease } from '../../core/models/firmware';

@Component({
  selector: 'app-device-detail',
  imports: [DecimalPipe, SlicePipe, FormsModule],
  templateUrl: './device-detail.html',
  styleUrl: './device-detail.css'
})
export class DeviceDetail implements OnInit, OnDestroy {

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(Api);
  private ws = inject(Websocket);

  // Identificación del dispositivo (viene de la URL)
  deviceId = signal<string>('');

  // Última telemetría recibida (null hasta que llegue la primera)
  telemetry = signal<TelemetryPayload | null>(null);

  // Estado del WebSocket
  connectionState = signal<ConnectionState>('disconnected');

  // Estado del dispositivo según el LWT (online/offline)
  deviceStatus = signal<'online' | 'offline' | 'updating' | 'unknown'>('unknown');

  // Formulario de comando
  newMinHumedad = signal<number | null>(null);
  sendingCommand = signal(false);
  commandFeedback = signal<{ ok: boolean; text: string } | null>(null);

  // Firmware OTA
  firmwareList = signal<FirmwareRelease[]>([]);
  firmwareVersion = signal('');
  firmwareFile = signal<File | null>(null);
  uploadingFirmware = signal(false);
  firmwareFeedback = signal<{ ok: boolean; text: string } | null>(null);
  firmwarePanelOpen = signal(false);

  private subs: Subscription[] = [];

  ngOnInit(): void {
    // El parámetro de la ruta: /devices/:deviceId
    const id = this.route.snapshot.paramMap.get('deviceId');
    if (!id) {
      this.router.navigate(['/devices']);
      return;
    }
    this.deviceId.set(id);

    // Suscribirse a los mensajes del WebSocket
    this.subs.push(
      this.ws.onMessage().subscribe((msg) => this.handleMessage(msg))
    );

    // Suscribirse al estado de conexión
    this.subs.push(
      this.ws.onStateChange().subscribe((state) => {
        this.connectionState.set(state);
      })
    );

    // Conectar al dispositivo
    this.ws.connect(id);

    // Cargar historial de firmware
    this.loadFirmware(id);
  }

  ngOnDestroy(): void {
    this.ws.disconnect();
    this.subs.forEach((s) => s.unsubscribe());
  }

  private handleMessage(msg: WebSocketMessage): void {
    if (msg.type === 'telemetry' && msg.payload) {
      this.telemetry.set(msg.payload);
      // Si llega telemetría, sabemos que el dispositivo está vivo
      this.deviceStatus.set('online');
    } else if (msg.type === 'status' && msg.status) {
      this.deviceStatus.set(msg.status);
    }
  }

  goBack(): void {
    this.router.navigate(['/devices']);
  }

  sendCommand(): void {
    const value = this.newMinHumedad();

    if (value === null || Number.isNaN(value)) {
      this.commandFeedback.set({ ok: false, text: 'Ingresa un valor' });
      return;
    }
    if (value < 0 || value > 100) {
      this.commandFeedback.set({
        ok: false,
        text: 'Debe ser un número entre 0 y 100',
      });
      return;
    }

    this.sendingCommand.set(true);
    this.commandFeedback.set(null);

    this.api.setMinHumedad(this.deviceId(), value).subscribe({
      next: () => {
        this.sendingCommand.set(false);
        this.commandFeedback.set({
          ok: true,
          text: `Comando enviado: minHumedad = ${value}`,
        });
        this.newMinHumedad.set(null);
      },
      error: (err: HttpErrorResponse) => {
        this.sendingCommand.set(false);
        this.commandFeedback.set({
          ok: false,
          text: `Error ${err.status}: ${err.message}`,
        });
      },
    });
  }

  /** Texto y color del badge según el estado combinado. */
  badgeText(): string {
    if (this.connectionState() === 'connecting') return 'Conectando...';
    if (this.connectionState() === 'disconnected') return 'Reconectando...';
    if (this.deviceStatus() === 'updating') return 'Actualizando firmware...';
    if (this.deviceStatus() === 'offline') return 'Offline';
    if (this.telemetry()) return 'En vivo';
    return 'Esperando datos...';
  }

  badgeClass(): string {
    if (this.connectionState() !== 'connected') return 'badge-warn';
    if (this.deviceStatus() === 'updating') return 'badge-ota';
    if (this.deviceStatus() === 'offline') return 'badge-bad';
    if (this.telemetry()) return 'badge-ok';
    return 'badge-warn';
  }

  toggleBloqueada(): void {
    const t = this.telemetry();
    if (!t) return;

    const nuevo = !(t.bombaBloqueada ?? false);
    this.commandFeedback.set(null);

    this.api.setBombaBloqueada(this.deviceId(), nuevo).subscribe({
      next: () => {
        this.commandFeedback.set({
          ok: true,
          text: nuevo ? 'Bomba bloqueada' : 'Bomba desbloqueada',
        });
      },
      error: (err: HttpErrorResponse) => {
        this.commandFeedback.set({
          ok: false,
          text: `Error ${err.status}: ${err.message}`,
        });
      },
    });
  }

  // ===== Firmware OTA =====

  loadFirmware(id: string): void {
    this.api.listFirmware(id).subscribe({
      next: (list) => this.firmwareList.set(list),
      error: () => {},
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.firmwareFile.set(input.files?.[0] ?? null);
  }

  uploadFirmware(): void {
    const file = this.firmwareFile();
    const version = this.firmwareVersion().trim();

    if (!file) {
      this.firmwareFeedback.set({ ok: false, text: 'Selecciona un archivo .bin' });
      return;
    }
    if (!version) {
      this.firmwareFeedback.set({ ok: false, text: 'Ingresa una versión' });
      return;
    }

    this.uploadingFirmware.set(true);
    this.firmwareFeedback.set(null);

    this.api.uploadFirmware(this.deviceId(), version, file).subscribe({
      next: (release) => {
        this.uploadingFirmware.set(false);
        this.firmwareFile.set(null);
        this.firmwareVersion.set('');
        this.firmwareList.update((list) => [release, ...list]);
        const notified = release.status === 'notified';
        this.firmwareFeedback.set({
          ok: true,
          text: notified
            ? `v${release.version} subida y dispositivo notificado vía MQTT`
            : `v${release.version} subida. No se pudo notificar al dispositivo (offline)`,
        });
      },
      error: (err) => {
        this.uploadingFirmware.set(false);
        this.firmwareFeedback.set({
          ok: false,
          text: `Error ${err.status}: ${err.error?.detail ?? err.message}`,
        });
      },
    });
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }

  toggleForzada(): void {
    const t = this.telemetry();
    if (!t) return;

    // Si está bloqueada, no permitir activar el forzado (defensa extra
    // por si el disabled del HTML fallara)
    if (t.bombaBloqueada && !t.bombaForzada) return;

    const nuevo = !(t.bombaForzada ?? false);
    this.commandFeedback.set(null);

    this.api.setBombaForzada(this.deviceId(), nuevo).subscribe({
      next: () => {
        this.commandFeedback.set({
          ok: true,
          text: nuevo ? 'Bomba forzada activada' : 'Bomba forzada desactivada',
        });
      },
      error: (err: HttpErrorResponse) => {
        this.commandFeedback.set({
          ok: false,
          text: `Error ${err.status}: ${err.message}`,
        });
      },
    });
  }
}
