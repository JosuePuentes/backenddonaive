# Instrucciones para el Frontend - Endpoints Disponibles

## 🔐 Autenticación

### Base URL
```
https://rapifarma-backend.onrender.com
```

### Headers Requeridos
Todas las peticiones (excepto login) requieren:
```javascript
{
  "Authorization": "Bearer <token>",
  "Content-Type": "application/json"
}
```

---

## 📋 Endpoints Disponibles

### 1. Autenticación y Usuario

#### `POST /auth/login`
**Autenticación:** No requerida

**Request:**
```json
{
  "correo": "admin@gmail.com",
  "contraseña": "password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "usuario": {
    "_id": "6830cadaf1916150d7f1d600",
    "correo": "admin@gmail.com",
    "permisos": ["admin_completo"],
    "farmacias": {...}
  }
}
```

#### `GET /auth/me`
**Autenticación:** Requerida

**Response:**
```json
{
  "_id": "6830cadaf1916150d7f1d600",
  "correo": "admin@gmail.com",
  "permisos": ["admin_completo"],
  "farmacias": {...}
}
```

#### `GET /usuarios/me`
**Autenticación:** Requerida

**Response:** (Igual que `/auth/me`)

---

### 2. Usuarios

#### `GET /usuarios`
**Autenticación:** Requerida (Solo admin)

**Response:**
```json
{
  "usuarios": [
    {
      "_id": "6830cadaf1916150d7f1d600",
      "correo": "admin@gmail.com",
      "permisos": ["admin_completo"],
      "farmacias": {...}
    }
  ]
}
```

#### `GET /usuarios/{id}`
**Autenticación:** Requerida (Solo admin)

**Response:**
```json
{
  "usuario": {
    "_id": "6830cadaf1916150d7f1d600",
    "correo": "admin@gmail.com",
    "permisos": ["admin_completo"]
  }
}
```

#### `GET /modificar-usuarios`
**Autenticación:** Requerida (Solo admin)

**Response:** (Igual que `/usuarios`)

#### `GET /modificar-usuarios/me`
**Autenticación:** Requerida

**Response:**
```json
{
  "usuario": {
    "_id": "6830cadaf1916150d7f1d600",
    "correo": "admin@gmail.com",
    "permisos": ["admin_completo"]
  }
}
```

#### `GET /modificar-usuarios/{id}`
**Autenticación:** Requerida (Solo admin)

**Response:**
```json
{
  "usuario": {
    "_id": "6830cadaf1916150d7f1d600",
    "correo": "admin@gmail.com",
    "permisos": ["admin_completo"]
  }
}
```

#### `PATCH /modificar-usuarios/{id}`
**Autenticación:** Requerida (Solo admin)

**Request:**
```json
{
  "permisos": ["admin_completo", "ver_inventario"],
  "farmacias": {...}
}
```

---

### 3. Farmacias

#### `GET /farmacias`
**Autenticación:** No requerida

**Response:**
```json
{
  "farmacias": {
    "01": "Santa Elena",
    "02": "Otra Farmacia"
  }
}
```

#### `GET /farmacias/resumen`
**Autenticación:** No requerida

**Response:**
```json
{
  "farmacias": {
    "01": {
      "id": "01",
      "nombre": "Santa Elena",
      "totalCuadres": 10,
      "costoTotal": 5000,
      "ventasTotal": 8000
    }
  },
  "totalGeneral": {
    "totalCuadres": 10,
    "costoTotal": 5000,
    "ventasTotal": 8000,
    "costoInventarioTotal": 10000
  }
}
```

---

### 4. Compras y Proveedores

#### `GET /compras`
**Autenticación:** Requerida (Permiso: `compras`)

**Query Parameters:**
- `skip` (opcional, default: 0)
- `limit` (opcional, default: 50, max: 100)
- `sucursal_id` (opcional)
- `estado` (opcional: "activa", "cancelada")
- `estado_pago` (opcional: "sin_pago", "abonado", "pagada")

**Response:**
```json
[
  {
    "_id": "...",
    "proveedor_id": "...",
    "proveedor": {
      "nombre": "Proveedor ABC",
      "rif": "J-12345678-9"
    },
    "farmacia": "01",
    "sucursal_id": "sucursal_1",
    "numero_factura": "FAC-001",
    "fecha_compra": "2024-11-30",
    "items": [
      {
        "nombre": "Producto 1",
        "cantidad": 10,
        "costo_unitario": 5.50,
        "precio_unitario": 8.00,
        "subtotal": 55.00
      }
    ],
    "total": 550.00,
    "divisa": "USD",
    "lleva_iva": true,
    "iva": 88.00,
    "total_con_iva": 638.00,
    "estado_pago": "sin_pago",
    "monto_pagado": 0,
    "monto_pendiente": 638.00,
    "dias_credito": 30,
    "dias_mora": 0
  }
]
```

#### `POST /compras`
**Autenticación:** Requerida (Permiso: `compras`)

**Request:**
```json
{
  "proveedor_id": "proveedor_id_123",
  "farmacia": "01",
  "sucursal_id": "sucursal_1",
  "numero_factura": "FAC-001",
  "fecha_compra": "2024-11-30",
  "items": [
    {
      "nombre": "Producto 1",
      "cantidad": 10,
      "costo_unitario": 5.50,
      "precio_unitario": 8.00,
      "marca": "Marca ABC",
      "utilidad": 30,
      "lote": "LOTE-001"
    }
  ],
  "total": 55.00,
  "divisa": "USD",
  "lleva_iva": true,
  "notas": "Notas adicionales"
}
```

**Nota:** Los campos `fecha_compra` y `lote` son opcionales. Si `fecha_compra` no se envía, se usa la fecha actual.

#### `GET /proveedores`
**Autenticación:** Requerida (Permiso: `compras`)

**Query Parameters:**
- `skip` (opcional, default: 0)
- `limit` (opcional, default: 50)
- `estado` (opcional: "activo", "inactivo")

**Response:**
```json
[
  {
    "_id": "...",
    "nombre": "Proveedor ABC",
    "rif": "J-12345678-9",
    "telefono": "0412-1234567",
    "email": "proveedor@example.com",
    "direccion": "Dirección del proveedor",
    "contacto": "Juan Pérez",
    "dias_credito": 30,
    "descuento_comercial": 5.0,
    "descuento_pronto_pago": 2.0,
    "estado": "activo"
  }
]
```

#### `POST /proveedores`
**Autenticación:** Requerida (Permiso: `compras`)

**Request:**
```json
{
  "nombre": "Proveedor ABC",
  "rif": "J-12345678-9",
  "telefono": "0412-1234567",
  "email": "proveedor@example.com",
  "direccion": "Dirección del proveedor",
  "contacto": "Juan Pérez",
  "dias_credito": 30,
  "descuento_comercial": 5.0,
  "descuento_pronto_pago": 2.0,
  "notas": "Notas adicionales"
}
```

#### `PUT /proveedores/{proveedor_id}`
**Autenticación:** Requerida (Permiso: `compras`)

**Request:** (Igual que POST)

#### `GET /productos?search={query}`
**Autenticación:** Requerida (Permiso: `compras`)

**Response:**
```json
[
  {
    "_id": "...",
    "codigo": "PROD-001",
    "nombre": "Producto 1",
    "costo": 5.50,
    "precio": 8.00,
    "marca": "Marca ABC",
    "utilidad_porcentaje": 30
  }
]
```

#### `POST /compras/{compra_id}/pagos`
**Autenticación:** Requerida (Permiso: `compras`)

**Request:**
```json
{
  "monto": 300.00,
  "fecha_pago": "2024-11-30",
  "metodo_pago": "transferencia",
  "referencia": "REF-123456",
  "notas": "Pago parcial"
}
```

---

### 5. Cuentas por Pagar

#### `GET /cuentas-por-pagar`
**Autenticación:** Requerida

**Response:**
```json
[
  {
    "_id": "...",
    "proveedor": "Proveedor ABC",
    "monto": 1000.00,
    "divisa": "USD",
    "montoUsd": 1000.00,
    "fechaEmision": "2024-11-01",
    "fechaVencimiento": "2024-12-01",
    "estatus": "wait",
    "imagenesCuentaPorPagar": []
  }
]
```

#### `POST /cuentas-por-pagar`
**Autenticación:** Requerida

**Request:**
```json
{
  "proveedor": "Proveedor ABC",
  "monto": 1000.00,
  "divisa": "USD",
  "tasa": 1.0,
  "fechaEmision": "2024-11-01",
  "fechaVencimiento": "2024-12-01",
  "fechaRecepcion": "2024-11-02",
  "fechaRegistro": "2024-11-02",
  "imagenesCuentaPorPagar": ["url1", "url2"],
  "descripcion": "Descripción de la cuenta"
}
```

#### `PATCH /cuentas-por-pagar/{id}/estatus`
**Autenticación:** Requerida

**Request:**
```json
{
  "estatus": "approved"
}
```

---

### 6. Pagos CPP

#### `GET /pagoscpp?cuentaPorPagarId={id}`
**Autenticación:** Requerida

**Response:**
```json
[
  {
    "_id": "...",
    "cuentaPorPagarId": "...",
    "monto": 500.00,
    "fecha": "2024-11-30",
    "metodoPago": "transferencia",
    "referencia": "REF-123",
    "estado": "pendiente"
  }
]
```

#### `POST /pagoscpp`
**Autenticación:** Requerida

**Request:**
```json
{
  "cuentaPorPagarId": "cuenta_id_123",
  "monto": 500.00,
  "fecha": "2024-11-30",
  "metodoPago": "transferencia",
  "referencia": "REF-123",
  "bancoEmisor": "Banco A",
  "bancoReceptor": "Banco B"
}
```

---

### 7. Bancos

#### `GET /bancos`
**Autenticación:** Requerida

**Response:**
```json
{
  "bancos": [
    {
      "_id": "...",
      "numero_cuenta": "0102-1234-5678-9012",
      "nombre_banco": "Banco de Venezuela",
      "nombre_titular": "Juan Pérez",
      "saldo": 10000.00,
      "divisa": "USD",
      "activo": true,
      "tipo_metodo": "pago_movil"
    }
  ]
}
```

#### `POST /bancos`
**Autenticación:** Requerida

**Request:**
```json
{
  "numero_cuenta": "0102-1234-5678-9012",
  "nombre_banco": "Banco de Venezuela",
  "nombre_titular": "Juan Pérez",
  "saldo": 0,
  "divisa": "USD",
  "activo": true,
  "tipo_metodo": "pago_movil"
}
```

---

## ⚠️ Notas Importantes

### Sucursales
- Las compras tienen un campo `sucursal_id` que identifica la sucursal
- No hay un endpoint específico para listar sucursales, pero puedes filtrar compras por `sucursal_id`
- El campo `sucursal_id` es opcional en las compras

### Manejo de Errores

**401 Unauthorized:**
```json
{
  "detail": "No se pudo validar las credenciales"
}
```

**403 Forbidden:**
```json
{
  "detail": "No tienes permisos para realizar esta acción. Se requiere: compras"
}
```

**404 Not Found:**
```json
{
  "detail": "Recurso no encontrado"
}
```

**422 Validation Error:**
```json
{
  "detail": "Error de validación: campo -> mensaje",
  "errors": [...]
}
```

### Normalización de Datos

**Campos numéricos opcionales:**
- Si `dias_credito`, `descuento_comercial` o `descuento_pronto_pago` vienen como `undefined` o `null`, el backend los normaliza a `0`

**Campos de fecha:**
- Formato: `YYYY-MM-DD` (ej: "2024-11-30")
- Si `fecha_compra` no se envía, el backend usa la fecha actual

**Campos opcionales en compras:**
- `fecha_compra`: Opcional (usa fecha actual si no se envía)
- `lote`: Opcional en items
- `sucursal_id`: Opcional
- `numero_factura`: Opcional
- `notas`: Opcional

---

## 🔄 Flujo Recomendado

1. **Login:** `POST /auth/login` → Obtener token
2. **Verificar usuario:** `GET /auth/me` o `GET /usuarios/me`
3. **Cargar farmacias:** `GET /farmacias`
4. **Cargar compras:** `GET /compras?skip=0&limit=50`
5. **Cargar proveedores:** `GET /proveedores`
6. **Cargar cuentas por pagar:** `GET /cuentas-por-pagar`
7. **Cargar bancos:** `GET /bancos`

---

## 📝 Ejemplo de Código Frontend

```javascript
// Configuración base
const API_BASE_URL = 'https://rapifarma-backend.onrender.com';

// Función para hacer peticiones autenticadas
async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('token');
  
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error en la petición');
  }
  
  return response.json();
}

// Ejemplos de uso
async function cargarCompras() {
  try {
    const compras = await apiRequest('/compras?skip=0&limit=50');
    return compras;
  } catch (error) {
    console.error('Error al cargar compras:', error);
    throw error;
  }
}

async function crearCompra(compraData) {
  try {
    const compra = await apiRequest('/compras', {
      method: 'POST',
      body: JSON.stringify(compraData)
    });
    return compra;
  } catch (error) {
    console.error('Error al crear compra:', error);
    throw error;
  }
}
```

---

## 🚨 Solución de Problemas

### Endpoints dando 404
1. Verifica que el token sea válido
2. Verifica que el endpoint esté correctamente escrito
3. Espera unos minutos después de un deploy (Render puede tardar en actualizar)
4. Revisa los logs del backend para errores de importación

### Errores 422 (Validación)
- Revisa que todos los campos requeridos estén presentes
- Verifica los tipos de datos (números, strings, fechas)
- Asegúrate de que los campos opcionales sean `null` o no se envíen, no `undefined`

### Errores 403 (Permisos)
- Verifica que el usuario tenga el permiso requerido
- Algunos endpoints requieren permiso `compras`
- Algunos endpoints requieren ser admin (`admin@gmail.com`)

