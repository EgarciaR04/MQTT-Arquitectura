import { Component, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { SlicePipe } from '@angular/common';

import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Device } from '../../core/models/device';

@Component({
  selector: 'app-devices',
  imports: [SlicePipe],
  templateUrl: './devices.html',
  styleUrl: './devices.css'
})
export class Devices implements OnInit {

  private api = inject(Api);
  private auth = inject(Auth);
  private router = inject(Router);

  // Estado de la pantalla
  devices = signal<Device[]>([]);
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loadDevices();
  }

  loadDevices(): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    this.api.listDevices().subscribe({
      next: (devices) => {
        this.loading.set(false);
        this.devices.set(devices);
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        if (err.status === 401) {
          // Token caducado o inválido: forzamos logout
          this.logout();
        } else if (err.status === 0) {
          this.errorMessage.set('No se pudo conectar con el servidor');
        } else {
          this.errorMessage.set(`Error (${err.status}): ${err.message}`);
        }
      }
    });
  }

  openDevice(device: Device): void {
    this.router.navigate(['/devices', device.device_id]);
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
