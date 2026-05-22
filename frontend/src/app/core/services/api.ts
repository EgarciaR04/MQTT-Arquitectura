import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { TokenResponse } from '../models/token';
import { Device } from '../models/device';
import { TelemetryRecord } from '../models/telemetry';
import { CommandRequest, CommandResponse } from '../models/command';

@Injectable({ providedIn: 'root' })
export class Api {

  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  // ===== Auth =====

  /**
   * POST /auth/login
   * El backend espera form-urlencoded (OAuth2PasswordRequestForm).
   */
  login(email: string, password: string): Observable<TokenResponse> {
    const body = new HttpParams()
      .set('username', email)
      .set('password', password);

    return this.http.post<TokenResponse>(
      `${this.baseUrl}/auth/login`,
      body.toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );
  }

  // ===== Dispositivos =====

  listDevices(): Observable<Device[]> {
    return this.http.get<Device[]>(`${this.baseUrl}/devices`);
  }

  getTelemetry(deviceId: string, limit: number = 100): Observable<TelemetryRecord[]> {
    return this.http.get<TelemetryRecord[]>(
      `${this.baseUrl}/devices/${deviceId}/telemetry`,
      { params: new HttpParams().set('limit', limit) }
    );
  }

  sendCommand(deviceId: string, command: CommandRequest): Observable<CommandResponse> {
    return this.http.post<CommandResponse>(
      `${this.baseUrl}/devices/${deviceId}/command`,
      command
    );
  }

  /** Atajo para el comando más común. */
  setMinHumedad(deviceId: string, value: number): Observable<CommandResponse> {
    return this.sendCommand(deviceId, { payload: { minHumedad: value } });
  }

  setBombaBloqueada(deviceId: string, value: boolean): Observable<CommandResponse> {
    return this.sendCommand(deviceId, { payload: { bombaBloqueada: value } });
  }

  setBombaForzada(deviceId: string, value: boolean): Observable<CommandResponse> {
    return this.sendCommand(deviceId, { payload: { bombaForzada: value } });
  }
}
