# Instrucciones para el Frontend - Autenticación y Token JWT

## Problema: Errores 401 (No autorizado)

Los endpoints están devolviendo `401 Unauthorized` porque el token JWT no se está enviando correctamente en las peticiones.

## Solución: Enviar el token en todas las peticiones

### 1. **Guardar el token después del login**

```javascript
// Después de hacer login exitoso
const response = await fetch('/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    correo: email,
    contraseña: password
  })
});

const data = await response.json();

// Guardar el token
localStorage.setItem('access_token', data.access_token);
// O usar sessionStorage, cookies, o un estado global (Redux, Context, etc.)
```

### 2. **Crear una función para hacer peticiones autenticadas**

```javascript
// Función helper para hacer peticiones con autenticación
async function fetchWithAuth(url, options = {}) {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    // Redirigir al login si no hay token
    window.location.href = '/login';
    throw new Error('No hay token de autenticación');
  }
  
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,  // ✅ CRÍTICO: Enviar token aquí
    ...options.headers
  };
  
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  // Si el token expiró (401), redirigir al login
  if (response.status === 401) {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
    throw new Error('Token expirado o inválido');
  }
  
  return response;
}
```

### 3. **Usar la función en todas las peticiones**

```javascript
// ✅ CORRECTO: Usar fetchWithAuth
const response = await fetchWithAuth('/punto-venta/tasa-del-dia?fecha=2025-11-07');
const data = await response.json();

// ✅ CORRECTO: Buscar productos
const response = await fetchWithAuth('/punto-venta/productos/buscar?q=SPRAY&sucursal=01');
const productos = await response.json();

// ✅ CORRECTO: Buscar clientes
const response = await fetchWithAuth('/clientes/buscar?q=ANUBIS');
const clientes = await response.json();
```

### 4. **Si usas axios, configurar interceptores**

```javascript
import axios from 'axios';

// Crear instancia de axios
const api = axios.create({
  baseURL: 'https://rapifarma-backend.onrender.com',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Interceptor para agregar token a todas las peticiones
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;  // ✅ CRÍTICO
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor para manejar errores 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expirado o inválido
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Usar la instancia configurada
const response = await api.get('/punto-venta/tasa-del-dia', {
  params: { fecha: '2025-11-07' }
});
```

### 5. **Verificar que el token se envía correctamente**

Abre las DevTools del navegador (F12) y verifica en la pestaña "Network":

1. Selecciona una petición que esté fallando (ej: `/punto-venta/tasa-del-dia`)
2. Ve a la pestaña "Headers"
3. Busca la sección "Request Headers"
4. Debe aparecer: `Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

Si no aparece el header `Authorization`, el token no se está enviando.

## Endpoints que requieren autenticación

Todos estos endpoints requieren el token JWT:

- ✅ `GET /punto-venta/tasa-del-dia?fecha=YYYY-MM-DD`
- ✅ `GET /punto-venta/productos/buscar?q={query}&sucursal={id}`
- ✅ `GET /punto-venta/productos?sucursal={id}`
- ✅ `POST /punto-venta/ventas`
- ✅ `GET /clientes/buscar?q={query}`
- ✅ `GET /clientes`
- ✅ `POST /clientes`
- ✅ `GET /clientes/{id}`
- ✅ `PUT /clientes/{id}`
- ✅ `GET /clientes/{id}/compras/total`
- ✅ `GET /clientes/{id}/compras/items`
- ✅ Y todos los demás endpoints excepto `/auth/login` y `/`

## Formato del header Authorization

El backend espera el token en este formato exacto:

```
Authorization: Bearer <token>
```

**Ejemplo:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBnbWFpbC5jb20iLCJleHAiOjE3NjI0ODg0Nzl9.O7tDV8tDFrbnjyVmeVEnDyWVfQW7JqXmwc1fg_Nc1dk
```

## Checklist para el Frontend

- [ ] Guardar el token después del login (`localStorage`, `sessionStorage`, o estado global)
- [ ] Crear función helper `fetchWithAuth` o configurar axios con interceptores
- [ ] Enviar el header `Authorization: Bearer <token>` en TODAS las peticiones
- [ ] Manejar errores 401 (token expirado) redirigiendo al login
- [ ] Verificar en DevTools que el header `Authorization` se envía correctamente
- [ ] Renovar el token si es necesario (el backend no tiene refresh token, hay que hacer login de nuevo)

## Notas Importantes

1. **El token expira**: Los tokens JWT tienen una fecha de expiración. Si el token expira, el usuario debe hacer login de nuevo.

2. **No enviar token en login**: El endpoint `/auth/login` NO requiere token, solo correo y contraseña.

3. **CORS está configurado**: El backend ya tiene CORS configurado para permitir peticiones desde `https://www.donaive.com.ve`.

4. **El backend valida el token**: Si el token es inválido o expiró, el backend devuelve 401 automáticamente.

## Ejemplo Completo de Implementación

```javascript
// auth.js - Utilidades de autenticación
export const getToken = () => {
  return localStorage.getItem('access_token');
};

export const setToken = (token) => {
  localStorage.setItem('access_token', token);
};

export const removeToken = () => {
  localStorage.removeItem('access_token');
};

export const isAuthenticated = () => {
  return !!getToken();
};

// api.js - Cliente HTTP configurado
import axios from 'axios';
import { getToken, removeToken } from './auth';

const api = axios.create({
  baseURL: 'https://rapifarma-backend.onrender.com',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Agregar token a todas las peticiones
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Manejar errores 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Uso en componentes
import api from './api';

// Obtener tasa del día
const obtenerTasa = async (fecha) => {
  const response = await api.get('/punto-venta/tasa-del-dia', {
    params: { fecha }
  });
  return response.data;
};

// Buscar productos
const buscarProductos = async (query, sucursal) => {
  const response = await api.get('/punto-venta/productos/buscar', {
    params: { q: query, sucursal }
  });
  return response.data;
};

// Buscar clientes
const buscarClientes = async (query) => {
  const response = await api.get('/clientes/buscar', {
    params: { q: query }
  });
  return response.data;
};
```

