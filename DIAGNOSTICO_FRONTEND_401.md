# Diagnóstico: Error 401 - Token no se está enviando

## 🔴 Problema Confirmado

Al revisar los headers de la petición, **NO aparece el header `Authorization`**. Esto significa que aunque el código cambió, el token no se está enviando.

## ✅ Verificación en el Frontend

### Paso 1: Verificar que el token se guarda después del login

```javascript
// Después del login, verificar:
const response = await fetch('/auth/login', {
  method: 'POST',
  body: JSON.stringify({ correo, contraseña })
});
const data = await response.json();

console.log('Token recibido:', data.access_token); // ✅ Debe mostrar el token
localStorage.setItem('access_token', data.access_token);

// Verificar que se guardó:
console.log('Token guardado:', localStorage.getItem('access_token')); // ✅ Debe mostrar el token
```

### Paso 2: Verificar que getAuthHeaders() funciona

```javascript
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token');
  console.log('Token obtenido del localStorage:', token); // ✅ Debe mostrar el token
  
  if (!token) {
    console.error('❌ ERROR: No hay token en localStorage');
    return {};
  }
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`  // ✅ CRÍTICO
  };
  
  console.log('Headers creados:', headers); // ✅ Debe mostrar Authorization: Bearer <token>
  return headers;
}
```

### Paso 3: Verificar que fetchWithAuth() usa los headers

```javascript
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('access_token');
  console.log('fetchWithAuth - Token:', token); // ✅ Debe mostrar el token
  
  if (!token) {
    console.error('❌ ERROR: No hay token, redirigiendo al login');
    window.location.href = '/login';
    throw new Error('No hay token de autenticación');
  }
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,  // ✅ CRÍTICO
    ...(options.headers as Record<string, string> || {})
  };
  
  console.log('fetchWithAuth - Headers finales:', headers); // ✅ Debe mostrar Authorization
  
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  console.log('fetchWithAuth - Response status:', response.status); // ✅ Debe mostrar 200, no 401
  
  if (response.status === 401) {
    console.error('❌ ERROR: Token inválido o expirado');
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  }
  
  return response;
}
```

### Paso 4: Verificar que se usa fetchWithAuth() en las peticiones

```javascript
// ❌ INCORRECTO (lo que probablemente está pasando):
const response = await fetch('/punto-venta/tasa-del-dia?fecha=2025-11-07');

// ✅ CORRECTO (lo que debe hacer):
const response = await fetchWithAuth('/punto-venta/tasa-del-dia?fecha=2025-11-07');
```

## 🔍 Checklist de Diagnóstico

Ejecuta estos pasos en la consola del navegador (F12):

1. **Verificar que el token existe:**
   ```javascript
   localStorage.getItem('access_token')
   ```
   Si retorna `null`, el token no se guardó después del login.

2. **Verificar que getAuthHeaders() funciona:**
   ```javascript
   // En la consola, ejecutar:
   const token = localStorage.getItem('access_token');
   const headers = {
     'Authorization': `Bearer ${token}`
   };
   console.log(headers);
   ```
   Debe mostrar: `{ Authorization: "Bearer eyJhbGci..." }`

3. **Verificar en Network tab:**
   - Abre DevTools (F12)
   - Ve a la pestaña "Network"
   - Haz una petición que falle (ej: buscar productos)
   - Selecciona la petición
   - Ve a "Headers" → "Request Headers"
   - **DEBE aparecer:** `Authorization: Bearer <token>`
   - Si NO aparece, el token no se está enviando

## 🛠️ Solución Rápida

Si el token no se está enviando, asegúrate de:

1. **Usar fetchWithAuth() en TODAS las peticiones:**
   ```javascript
   // Buscar productos
   const response = await fetchWithAuth(
     `/punto-venta/productos/buscar?q=${query}&sucursal=${sucursal}`
   );
   
   // Obtener tasa
   const response = await fetchWithAuth(
     `/punto-venta/tasa-del-dia?fecha=${fecha}`
   );
   
   // Buscar clientes
   const response = await fetchWithAuth(
     `/clientes/buscar?q=${query}`
   );
   ```

2. **NO usar fetch() directamente:**
   ```javascript
   // ❌ NUNCA hacer esto:
   fetch('/punto-venta/tasa-del-dia?fecha=2025-11-07')
   
   // ✅ SIEMPRE usar esto:
   fetchWithAuth('/punto-venta/tasa-del-dia?fecha=2025-11-07')
   ```

3. **Si usas axios, configurar interceptores:**
   ```javascript
   import axios from 'axios';
   
   const api = axios.create({
     baseURL: 'https://rapifarma-backend.onrender.com'
   });
   
   // Interceptor para agregar token
   api.interceptors.request.use((config) => {
     const token = localStorage.getItem('access_token');
     if (token) {
       config.headers.Authorization = `Bearer ${token}`;  // ✅ CRÍTICO
     }
     return config;
   });
   
   // Usar api en lugar de fetch
   const response = await api.get('/punto-venta/tasa-del-dia', {
     params: { fecha: '2025-11-07' }
   });
   ```

## 📋 Código Completo de Ejemplo

```typescript
// auth.ts - Utilidades de autenticación
export const getToken = (): string | null => {
  return localStorage.getItem('access_token');
};

export const setToken = (token: string): void => {
  localStorage.setItem('access_token', token);
};

export const removeToken = (): void => {
  localStorage.removeItem('access_token');
};

// api.ts - Cliente HTTP
export async function fetchWithAuth(
  url: string, 
  options: RequestInit = {}
): Promise<Response> {
  const token = getToken();
  
  if (!token) {
    console.error('❌ No hay token, redirigiendo al login');
    window.location.href = '/login';
    throw new Error('No hay token de autenticación');
  }
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,  // ✅ CRÍTICO
    ...(options.headers as Record<string, string> || {})
  };
  
  console.log('🔐 Enviando petición con token:', url);
  
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  if (response.status === 401) {
    console.error('❌ Token inválido o expirado');
    removeToken();
    window.location.href = '/login';
    throw new Error('Token inválido o expirado');
  }
  
  return response;
}

// Uso en componentes
import { fetchWithAuth } from './api';

// Obtener tasa del día
const obtenerTasa = async (fecha: string) => {
  const response = await fetchWithAuth(
    `https://rapifarma-backend.onrender.com/punto-venta/tasa-del-dia?fecha=${fecha}`
  );
  return response.json();
};

// Buscar productos
const buscarProductos = async (query: string, sucursal: string) => {
  const response = await fetchWithAuth(
    `https://rapifarma-backend.onrender.com/punto-venta/productos/buscar?q=${query}&sucursal=${sucursal}`
  );
  return response.json();
};

// Buscar clientes
const buscarClientes = async (query: string) => {
  const response = await fetchWithAuth(
    `https://rapifarma-backend.onrender.com/clientes/buscar?q=${query}`
  );
  return response.json();
};
```

## 🎯 Próximos Pasos

1. **Agregar console.log() en fetchWithAuth()** para ver qué está pasando
2. **Verificar en Network tab** que el header Authorization se envía
3. **Verificar que el token existe** en localStorage
4. **Asegurarse de usar fetchWithAuth()** en lugar de fetch() directamente

## ⚠️ Error Común

Si cambiaste el tipo de headers pero sigues usando `fetch()` directamente en lugar de `fetchWithAuth()`, el token nunca se enviará.

**Solución:** Busca en todo el código todas las llamadas a `fetch()` y reemplázalas por `fetchWithAuth()`.

