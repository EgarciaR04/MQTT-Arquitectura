import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/login/login').then(m => m.Login)
  },
  {
    path: 'devices',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/devices/devices').then(m => m.Devices)
  },
  {
    path: 'devices/:deviceId',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/device-detail/device-detail').then(m => m.DeviceDetail)
  },
  { path: '', redirectTo: '/devices', pathMatch: 'full' },
  { path: '**', redirectTo: '/devices' }
];
