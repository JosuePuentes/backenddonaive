# Instrucciones Frontend - Pagos de Compras

## 📋 Endpoint: `POST /compras/{compra_id}/pagos`

### Descripción
Registra un pago para una compra. El monto se suma al `monto_pagado` (abonado) y se resta del `monto_pendiente` (total adeudado). Si se proporciona un `banco_id`, el saldo del banco se resta automáticamente.

### URL
```
POST https://rapifarma-backend.onrender.com/compras/{compra_id}/pagos
```

### Headers Requeridos
```javascript
{
  "Authorization": "Bearer <token>",
  "Content-Type": "application/json"
}
```

### Request Body

#### Campos Requeridos
- `monto` (number, opcional): Monto del pago. Si no se envía, se usa 0 (pero debe ser > 0 para ser válido)
- `metodo_pago` (string, requerido): Método de pago (ej: "efectivo", "transferencia", "pago_movil", "cheque", etc.)

#### Campos Opcionales
- `fecha_pago` (string, opcional): Fecha del pago en formato `YYYY-MM-DD`. Si no se envía, se usa la fecha actual
- `banco_id` (string, opcional): ID del banco utilizado para el pago. Si se proporciona:
  - El banco debe existir y estar activo
  - El banco debe tener suficiente saldo
  - El saldo del banco se restará automáticamente
- `referencia` (string, opcional): Referencia del pago (número de cheque, transferencia, etc.)
- `notas` (string, opcional): Notas adicionales sobre el pago

### Ejemplo de Request

#### Pago con banco (recomendado)
```json
{
  "monto": 500.00,
  "fecha_pago": "2024-11-30",
  "metodo_pago": "transferencia",
  "banco_id": "692b87bab007a7d0121981ed",
  "referencia": "TRF-123456",
  "notas": "Pago parcial de compra"
}
```

#### Pago en efectivo (sin banco)
```json
{
  "monto": 300.00,
  "fecha_pago": "2024-11-30",
  "metodo_pago": "efectivo",
  "notas": "Pago en efectivo"
}
```

#### Pago mínimo (solo método requerido)
```json
{
  "monto": 200.00,
  "metodo_pago": "pago_movil"
}
```

### Response (201 Created)

```json
{
  "_id": "pago_id_123",
  "compra_id": "692b87bab007a7d0121981ed",
  "monto": 500.00,
  "fecha_pago": "2024-11-30",
  "metodo_pago": "transferencia",
  "banco_id": "692b87bab007a7d0121981ed",
  "referencia": "TRF-123456",
  "notas": "Pago parcial de compra",
  "usuario_creacion": "admin@gmail.com",
  "fecha_creacion": "2024-11-30T12:00:00"
}
```

### Lógica del Backend

1. **Validación de compra:**
   - Verifica que la compra existe
   - Verifica que la compra no esté cancelada

2. **Cálculo de montos:**
   - `monto_total` = `total_con_iva` o `total` de la compra
   - `monto_pagado_actual` = monto ya pagado anteriormente
   - `nuevo_monto_pagado` = `monto_pagado_actual` + `monto` del pago
   - `monto_pendiente` = `monto_total` - `nuevo_monto_pagado`

3. **Validación de banco (si se proporciona `banco_id`):**
   - Verifica que el banco existe
   - Verifica que el banco esté activo
   - Verifica que el banco tenga suficiente saldo
   - **Resta el saldo del banco:** `nuevo_saldo = saldo_actual - monto`

4. **Actualización de compra:**
   - `monto_pagado` = `nuevo_monto_pagado` (suma del nuevo pago)
   - `monto_pendiente` = `monto_total - nuevo_monto_pagado` (resta del total adeudado)
   - `estado_pago` = calculado automáticamente:
     - `"sin_pago"` si `monto_pagado` = 0
     - `"abonado"` si `0 < monto_pagado < monto_total`
     - `"pagada"` si `monto_pagado >= monto_total`

### Errores Posibles

#### 400 Bad Request
```json
{
  "detail": "El monto del pago debe ser mayor a 0"
}
```

#### 400 Bad Request
```json
{
  "detail": "El método de pago es requerido"
}
```

#### 400 Bad Request
```json
{
  "detail": "El monto del pago excede el total pendiente. Total: 1000, Pagado: 500, Pendiente: 500"
}
```

#### 400 Bad Request (si se proporciona banco_id)
```json
{
  "detail": "El banco no tiene suficiente saldo. Saldo disponible: 300, Monto requerido: 500"
}
```

#### 400 Bad Request
```json
{
  "detail": "El banco seleccionado no está activo"
}
```

#### 404 Not Found
```json
{
  "detail": "Compra no encontrada"
}
```

#### 404 Not Found (si se proporciona banco_id)
```json
{
  "detail": "Banco no encontrado"
}
```

### Ejemplo de Código Frontend

```javascript
// Función para registrar un pago
async function registrarPago(compraId, datosPago) {
  try {
    const token = localStorage.getItem('token');
    
    const response = await fetch(
      `https://rapifarma-backend.onrender.com/compras/${compraId}/pagos`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          monto: datosPago.monto,
          fecha_pago: datosPago.fecha_pago || new Date().toISOString().split('T')[0],
          metodo_pago: datosPago.metodo_pago,
          banco_id: datosPago.banco_id, // Opcional
          referencia: datosPago.referencia, // Opcional
          notas: datosPago.notas // Opcional
        })
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al registrar pago');
    }
    
    const pago = await response.json();
    console.log('Pago registrado exitosamente:', pago);
    return pago;
    
  } catch (error) {
    console.error('Error al registrar pago:', error);
    throw error;
  }
}

// Ejemplo de uso
const datosPago = {
  monto: 500.00,
  fecha_pago: "2024-11-30",
  metodo_pago: "transferencia",
  banco_id: "692b87bab007a7d0121981ed", // ID del banco seleccionado
  referencia: "TRF-123456",
  notas: "Pago parcial"
};

registrarPago("compra_id_123", datosPago)
  .then(pago => {
    console.log('Pago registrado:', pago);
    // Actualizar la UI con el nuevo estado de la compra
    // El monto_pagado y monto_pendiente se actualizan automáticamente
  })
  .catch(error => {
    alert(`Error: ${error.message}`);
  });
```

### Flujo Completo

1. **Usuario selecciona "Pagar/Abonar" en una compra**
2. **Frontend muestra modal con:**
   - Campo de monto
   - Selector de método de pago
   - Selector de banco (si el método requiere banco)
   - Campo de referencia (opcional)
   - Campo de notas (opcional)

3. **Usuario completa el formulario y envía**
4. **Backend procesa:**
   - Valida los datos
   - Si hay `banco_id`, resta el saldo del banco
   - Crea el registro de pago
   - Actualiza la compra:
     - Suma el monto a `monto_pagado`
     - Resta el monto de `monto_pendiente`
     - Actualiza `estado_pago`

5. **Frontend recibe la respuesta y actualiza la UI**

### Notas Importantes

1. **Campo `monto` es opcional en el esquema pero debe ser > 0:**
   - El backend valida que `monto > 0`
   - Si no se envía o es 0, se rechazará con error 400

2. **Campo `fecha_pago` es opcional:**
   - Si no se envía, el backend usa la fecha actual
   - Formato: `YYYY-MM-DD` (ej: "2024-11-30")

3. **Campo `banco_id` es opcional:**
   - Solo se requiere si el método de pago usa un banco
   - Si se proporciona, el saldo del banco se resta automáticamente
   - El banco debe existir, estar activo y tener suficiente saldo

4. **Actualización automática de montos:**
   - `monto_pagado` = suma de todos los pagos
   - `monto_pendiente` = `monto_total - monto_pagado`
   - `estado_pago` = calculado automáticamente según los montos

5. **Validación de saldo del banco:**
   - Si el banco no tiene suficiente saldo, se rechaza el pago
   - El error incluye el saldo disponible y el monto requerido

### Checklist para el Frontend

- [ ] Validar que `monto > 0` antes de enviar
- [ ] Validar que `metodo_pago` no esté vacío
- [ ] Si se selecciona un banco, mostrar su saldo disponible
- [ ] Validar que el saldo del banco sea suficiente antes de enviar
- [ ] Formatear `fecha_pago` como `YYYY-MM-DD`
- [ ] Manejar errores de validación (400)
- [ ] Manejar errores de banco no encontrado (404)
- [ ] Manejar errores de saldo insuficiente (400)
- [ ] Actualizar la UI después de un pago exitoso
- [ ] Mostrar el nuevo `monto_pagado` y `monto_pendiente` actualizados

