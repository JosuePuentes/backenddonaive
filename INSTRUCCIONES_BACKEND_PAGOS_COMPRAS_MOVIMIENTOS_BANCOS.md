# Instrucciones Backend - Movimientos Bancarios para Pagos de Compras

## ✅ Implementación Completada

El endpoint `POST /compras/{compra_id}/pagos` ahora crea automáticamente un movimiento en el banco cuando se registra un pago con `banco_id`.

## 📋 Cambios Realizados

### 1. Creación de Movimiento Bancario

**Ubicación:** `app/routes/compras.py` (función `crear_pago_compra`)

**Lógica implementada:**
- Cuando se registra un pago con `banco_id`, se crea un movimiento en la colección `MOVIMIENTOS_BANCOS`
- El movimiento se crea **después** de restar el saldo del banco
- El movimiento se actualiza con el `pago_id` después de crear el pago

### 2. Estructura del Movimiento

```python
movimiento = {
    "banco_id": banco_id,
    "tipo": "pago_compra",
    "monto": -monto,  # Negativo para indicar egreso
    "divisa": divisa_banco,  # Divisa del banco (USD o BS)
    "compra_id": compra_id,
    "pago_id": pago_id,  # Se actualiza después de crear el pago
    "proveedor_id": proveedor_id,
    "proveedor_nombre": proveedor_nombre,
    "numero_factura": numero_factura,
    "fecha": datetime.now().isoformat(),
    "fecha_pago": fecha_pago,
    "usuario": usuario.get("correo", ""),
    "descripcion": descripcion,  # "Pago Compra - {proveedor} (Factura {numero}) - Ref: {referencia}"
    "referencia": referencia,
    "metodo_pago": metodo_pago,
    "notas": notas,
    "saldo_anterior": saldo_actual,
    "saldo_nuevo": nuevo_saldo
}
```

### 3. Descripción del Movimiento

La descripción se construye automáticamente con:
- Nombre del proveedor
- Número de factura (si existe)
- Referencia del pago (si existe)

**Ejemplos:**
- `"Pago Compra - Proveedor ABC (Factura FAC-001) - Ref: TRF-123456"`
- `"Pago Compra - Proveedor XYZ"`
- `"Pago Compra - Proveedor ABC (Factura FAC-001)"`

## 🔄 Flujo Completo

1. **Usuario registra un pago de compra con `banco_id`**
2. **Backend valida:**
   - Que la compra existe
   - Que el banco existe y está activo
   - Que el banco tiene suficiente saldo
3. **Backend resta el saldo del banco:**
   - `nuevo_saldo = saldo_actual - monto`
4. **Backend crea el movimiento:**
   - Tipo: `"pago_compra"`
   - Monto: `-monto` (negativo, egreso)
   - Descripción: incluye proveedor, factura y referencia
5. **Backend crea el registro de pago**
6. **Backend actualiza el movimiento con `pago_id`**
7. **Backend actualiza la compra:**
   - Suma el monto a `monto_pagado`
   - Resta el monto de `monto_pendiente`
   - Actualiza `estado_pago`

## 📊 Estructura de la Colección MOVIMIENTOS_BANCOS

### Campos Requeridos
- `banco_id` (string): ID del banco
- `tipo` (string): Tipo de movimiento (`"pago_compra"`, `"venta"`, `"vuelto"`, etc.)
- `monto` (float): Monto del movimiento (negativo para egresos)
- `divisa` (string): Divisa del movimiento (`"USD"` o `"BS"`)
- `fecha` (string): Fecha del movimiento (ISO format)
- `usuario` (string): Usuario que creó el movimiento
- `descripcion` (string): Descripción del movimiento
- `saldo_anterior` (float): Saldo del banco antes del movimiento
- `saldo_nuevo` (float): Saldo del banco después del movimiento

### Campos Opcionales (para pagos de compras)
- `compra_id` (string): ID de la compra
- `pago_id` (string): ID del pago
- `proveedor_id` (string): ID del proveedor
- `proveedor_nombre` (string): Nombre del proveedor
- `numero_factura` (string): Número de factura
- `fecha_pago` (string): Fecha del pago
- `referencia` (string): Referencia del pago
- `metodo_pago` (string): Método de pago
- `notas` (string): Notas adicionales

## 🔍 Endpoint de Consulta

### `GET /bancos/{banco_id}/movimientos`

Este endpoint ya está implementado y devuelve todos los movimientos del banco, incluyendo:
- Movimientos de tipo `"pago_compra"` desde `MOVIMIENTOS_BANCOS`
- Movimientos de tipo `"venta"` desde `MOVIMIENTOS_BANCOS`
- Movimientos de tipo `"vuelto"` desde `MOVIMIENTOS_BANCOS`
- Pagos CPP desde `PAGOS_CPP`

**Respuesta:**
```json
{
  "banco_id": "banco_id",
  "numero_cuenta": "0102-1234-5678-9012",
  "nombre_banco": "Banco de Venezuela",
  "movimientos": [
    {
      "_id": "movimiento_id",
      "banco_id": "banco_id",
      "tipo": "pago_compra",
      "monto": -500.00,
      "divisa": "USD",
      "compra_id": "compra_id",
      "pago_id": "pago_id",
      "proveedor_nombre": "Proveedor ABC",
      "numero_factura": "FAC-001",
      "descripcion": "Pago Compra - Proveedor ABC (Factura FAC-001) - Ref: TRF-123",
      "fecha": "2024-11-30T12:00:00",
      "saldo_anterior": 1000.00,
      "saldo_nuevo": 500.00
    }
  ],
  "total": 1
}
```

## ✅ Características Implementadas

1. **Creación automática de movimiento:**
   - Se crea cuando se registra un pago con `banco_id`
   - Tipo: `"pago_compra"`
   - Monto negativo (egreso)

2. **Información completa:**
   - Incluye datos del proveedor
   - Incluye número de factura
   - Incluye referencia del pago
   - Incluye saldos anterior y nuevo

3. **Descripción clara:**
   - Formato: `"Pago Compra - {proveedor} ({factura}) - Ref: {referencia}"`
   - Fácil de identificar en el historial

4. **Vinculación con pago:**
   - El movimiento incluye `compra_id` y `pago_id`
   - Permite rastrear qué compras se pagaron desde cada banco

5. **Divisa correcta:**
   - El monto está en la divisa del banco
   - Se obtiene automáticamente del banco

## 🎯 Resultado para el Frontend

Cuando el frontend consulta `GET /bancos/{banco_id}/movimientos`, verá:

1. **Movimientos de pagos de compras:**
   - Tipo: `"pago_compra"`
   - Monto negativo (en rojo, egreso)
   - Descripción clara con proveedor y factura
   - Información completa para mostrar en el historial

2. **Filtrado y ordenamiento:**
   - Los movimientos se ordenan por fecha (más recientes primero)
   - Se pueden filtrar por tipo si es necesario

3. **Información para mostrar:**
   - Nombre del proveedor
   - Número de factura
   - Referencia del pago
   - Monto y divisa
   - Fecha del pago
   - Saldos anterior y nuevo

## 📝 Notas Importantes

1. **Solo se crea movimiento si hay `banco_id`:**
   - Si el pago es en efectivo (sin banco), no se crea movimiento
   - El movimiento solo se crea para pagos con banco

2. **Monto negativo:**
   - El monto es negativo (`-monto`) para indicar que es un egreso
   - El frontend debe mostrar estos movimientos en rojo

3. **Divisa del banco:**
   - El monto del movimiento está en la divisa del banco
   - Si el banco es USD, el monto es en USD
   - Si el banco es BS, el monto es en BS

4. **Actualización de `pago_id`:**
   - El movimiento se crea primero con `pago_id: None`
   - Después de crear el pago, se actualiza con el `pago_id` real
   - Esto permite vincular el movimiento con el pago

## 🚀 Estado

✅ **Implementación completada y desplegada**

El endpoint `POST /compras/{compra_id}/pagos` ahora:
- Crea automáticamente un movimiento en el banco
- Resta el saldo del banco
- Incluye información completa del proveedor y la compra
- Vincula el movimiento con el pago mediante `pago_id`

Los movimientos aparecerán automáticamente en `GET /bancos/{banco_id}/movimientos` y el frontend podrá mostrarlos en el historial del banco.

