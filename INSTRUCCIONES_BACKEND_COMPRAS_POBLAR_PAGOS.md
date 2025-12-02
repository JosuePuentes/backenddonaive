# Instrucciones Backend - Poblar Pagos en GET /compras

## ✅ Implementación Completada

El endpoint `GET /compras` ahora obtiene todos los pagos de cada compra y calcula los montos y el estado desde los pagos reales.

## 📋 Cambios Realizados

### 1. Obtención de Pagos

**Ubicación:** `app/routes/compras.py` (función `listar_compras`)

**Lógica implementada:**
- Para cada compra, se obtienen todos los pagos desde la colección `PAGOS_COMPRAS`
- Los pagos se ordenan por `fecha_creacion` ascendente (más antiguos primero)
- Se formatean todos los campos de cada pago

### 2. Cálculo de Montos

**Monto Abonado (`monto_abonado`):**
```python
monto_abonado = sum(pago.monto for pago in pagos_compra)
```
- Se suma el monto de todos los pagos de la compra
- Si no hay pagos, `monto_abonado = 0`

**Monto Restante (`monto_restante`):**
```python
monto_restante = total_precio_venta - monto_abonado
```
- `total_precio_venta` = `total_con_iva` o `total` de la compra
- Se calcula como la diferencia entre el total y lo abonado

### 3. Cálculo de Estado

**Reglas implementadas:**
```python
if monto_abonado >= monto_total:
    estado_pago = "pagada"
elif monto_abonado > 0:
    estado_pago = "abonado"
else:
    estado_pago = "sin_pago"
```

- **"pagada"**: Si `monto_abonado >= total_precio_venta`
- **"abonado"**: Si `monto_abonado > 0` y `monto_abonado < total_precio_venta`
- **"sin_pago"**: Si `monto_abonado = 0`

### 4. Array de Pagos

Cada compra ahora incluye un array `pagos` con todos los pagos:

```json
{
  "_id": "compra_id",
  "total_con_iva": 1000.00,
  "monto_abonado": 500.00,
  "monto_restante": 500.00,
  "estado_pago": "abonado",
  "pagos": [
    {
      "_id": "pago_id_1",
      "compra_id": "compra_id",
      "monto": 300.00,
      "fecha_pago": "2024-11-30",
      "metodo_pago": "transferencia",
      "referencia": "TRF-123",
      "banco_id": "banco_id",
      "notas": "Pago parcial",
      "usuario_creacion": "admin@gmail.com",
      "fecha_creacion": "2024-11-30T12:00:00"
    },
    {
      "_id": "pago_id_2",
      "compra_id": "compra_id",
      "monto": 200.00,
      "fecha_pago": "2024-12-01",
      "metodo_pago": "efectivo",
      "referencia": null,
      "banco_id": null,
      "notas": null,
      "usuario_creacion": "admin@gmail.com",
      "fecha_creacion": "2024-12-01T10:00:00"
    }
  ]
}
```

## 📊 Estructura de Respuesta

### Campos Agregados

1. **`monto_abonado`** (float): Suma de todos los pagos
2. **`monto_restante`** (float): `total_precio_venta - monto_abonado`
3. **`pagos`** (array): Array completo de pagos de la compra

### Campos Actualizados

1. **`monto_pagado`**: Ahora se calcula desde los pagos reales
2. **`monto_pendiente`**: Ahora se calcula como `monto_total - monto_abonado`
3. **`estado_pago`**: Se calcula según las reglas basadas en `monto_abonado`

## 🔧 Lógica Implementada

### 1. Obtención de Pagos
```python
# Para cada compra, obtener todos sus pagos
pagos_compra = await pagos_collection.find({"compra_id": compra_id_str}).sort("fecha_creacion", 1).to_list(length=None)
```

### 2. Cálculo de Monto Abonado
```python
monto_abonado = 0.0
for pago in pagos_compra:
    monto_abonado += float(pago.get("monto", 0) or 0)
```

### 3. Cálculo de Monto Restante
```python
monto_total = compra.get("total_con_iva") or compra.get("total", 0)
monto_restante = monto_total - monto_abonado
```

### 4. Cálculo de Estado
```python
if monto_abonado >= monto_total:
    estado_pago = "pagada"
elif monto_abonado > 0:
    estado_pago = "abonado"
else:
    estado_pago = "sin_pago"
```

## ✅ Verificación

Después de que el backend implemente los cambios, el frontend puede verificar en la consola:

### Logs Esperados

```
[LISTAR-COMPRAS] Compra {id}: Total=$1000.00, Abonado=$500.00, Restante=$500.00, Estado=abonado, Pagos=2
```

### Estructura de Datos Esperada

```json
{
  "_id": "compra_id",
  "total_con_iva": 1000.00,
  "monto_abonado": 500.00,
  "monto_restante": 500.00,
  "monto_pagado": 500.00,
  "monto_pendiente": 500.00,
  "estado_pago": "abonado",
  "pagos": [
    {
      "_id": "pago_id",
      "monto": 500.00,
      "fecha_pago": "2024-11-30",
      "metodo_pago": "transferencia",
      "referencia": "TRF-123",
      "banco_id": "banco_id"
    }
  ]
}
```

## 🎯 Beneficios

1. **Datos precisos:**
   - Los montos se calculan desde los pagos reales
   - No depende de campos que puedan estar desactualizados

2. **Historial completo:**
   - El frontend tiene acceso a todos los pagos de cada compra
   - Puede mostrar el historial de pagos

3. **Estado correcto:**
   - El estado se calcula automáticamente según los pagos reales
   - Siempre refleja el estado actual

4. **Trazabilidad:**
   - Cada pago está vinculado a su compra
   - Se puede rastrear quién hizo cada pago y cuándo

## 📝 Notas Importantes

1. **Orden de pagos:**
   - Los pagos se ordenan por `fecha_creacion` ascendente (más antiguos primero)
   - Esto permite ver el historial cronológico

2. **Campos numéricos normalizados:**
   - Todos los montos se convierten a `float`
   - Se asegura que nunca sean `None` o `undefined`

3. **Compatibilidad:**
   - Se mantienen los campos `monto_pagado` y `monto_pendiente` para compatibilidad
   - Se agregan `monto_abonado` y `monto_restante` como campos nuevos

4. **Performance:**
   - Se obtienen todos los pagos de una vez para cada compra
   - No hay consultas adicionales por cada pago

## 🚀 Estado

✅ **Implementación completada y desplegada**

El endpoint `GET /compras` ahora:
- Obtiene todos los pagos de cada compra
- Calcula `monto_abonado` sumando todos los pagos
- Calcula `monto_restante` como `total_precio_venta - monto_abonado`
- Calcula el estado según las reglas proporcionadas
- Incluye el array `pagos` completo en la respuesta

El frontend ahora puede:
- Mostrar el monto abonado correcto
- Mostrar el monto restante correcto
- Mostrar el estado correcto
- Mostrar el historial completo de pagos

