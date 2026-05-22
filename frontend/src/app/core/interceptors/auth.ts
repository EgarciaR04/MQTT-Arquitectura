import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Auth } from '../services/auth';

/**
 * Interceptor funcional que añade el header
 *   Authorization: Bearer <jwt>
 * a todas las peticiones excepto las de /auth/.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(Auth);
  const token = auth.getToken();

  // Los endpoints de /auth/* no llevan token
  const isAuthEndpoint = req.url.includes('/auth/');

  if (token && !isAuthEndpoint) {
    const authed = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
    return next(authed);
  }

  return next(req);
};
