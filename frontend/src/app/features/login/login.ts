import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';

import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class Login {

  private api = inject(Api);
  private auth = inject(Auth);
  private router = inject(Router);

  // Estado del formulario (signals = estado reactivo)
  email = signal('');
  password = signal('');

  // Estado de la UI
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  constructor() {
    // Si ya hay sesión, saltar directamente al listado
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/devices']);
    }
  }

  submit(): void {
    const email = this.email().trim();
    const password = this.password();

    if (!email || !password) {
      this.errorMessage.set('Completa email y contraseña');
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);

    this.api.login(email, password).subscribe({
      next: (response) => {
        this.loading.set(false);
        this.auth.saveToken(response.access_token);
        this.router.navigate(['/devices']);
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        if (err.status === 401) {
          this.errorMessage.set('Email o contraseña incorrectos');
        } else if (err.status === 0) {
          this.errorMessage.set('No se pudo conectar con el servidor');
        } else {
          this.errorMessage.set(`Error (${err.status}): ${err.message}`);
        }
      }
    });
  }
}
