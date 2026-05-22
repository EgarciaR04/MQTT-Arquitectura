import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'iot_jwt_token';

@Injectable({ providedIn: 'root' })
export class Auth {

  // Signal: estado reactivo. Cualquier componente que lo lea se actualiza
  // automáticamente cuando cambia.
  readonly token = signal<string | null>(this.readFromStorage());

  /** ¿Hay un JWT guardado? */
  isLoggedIn(): boolean {
    return this.token() !== null;
  }

  saveToken(token: string): void {
    localStorage.setItem(STORAGE_KEY, token);
    this.token.set(token);
  }

  getToken(): string | null {
    return this.token();
  }

  logout(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.token.set(null);
  }

  private readFromStorage(): string | null {
    // Protegemos contra entornos sin window (SSR), aunque no usamos SSR.
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEY);
  }
}
