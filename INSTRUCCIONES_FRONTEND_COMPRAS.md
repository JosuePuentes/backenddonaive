# Instrucciones para el Frontend - Módulo de Compras

## Endpoint: POST /compras

### Estructura del Request (JSON)

```json
{
  "proveedor_id": "string (ObjectId del proveedor)",
  "farmacia": "string (código de farmacia, ej: '01')",
  "sucursal_id": "string (ID de sucursal) - OPCIONAL",
  "sucursal": "string (ID de sucursal) - OPCIONAL (alias de sucursal_id)",
  "numero_factura": "string - OPCIONAL",
  "numero_control": "string - OPCIONAL",
  "fecha_compra": "string (YYYY-MM-DD) - OPCIONAL (usa fecha actual si no se envía)",
  "fecha_vencimiento_factura": "string (YYYY-MM-DD) - OPCIONAL",
  "items": [
    {
      "codigo": "string (REQUERIDO)",
      "nombre": "string (REQUERIDO)",
      "cantidad": "number (REQUERIDO, debe ser > 0)",
      "costo_unitario": "number (REQUERIDO, debe ser > 0)",
      "precio_unitario": "number - OPCIONAL",
      "lote": "string - OPCIONAL",
      "fecha_vencimiento": "string (YYYY-MM-DD) - OPCIONAL",
      "descripcion": "string - OPCIONAL",
      "lleva_iva": "boolean - OPCIONAL (default: false)"
    }
  ],
  "total": "number (REQUERIDO, debe ser > 0)",
  "divisa": "string (REQUERIDO: 'BS' o 'USD')",
  "tasa": "number - OPCIONAL (REQUERIDO si divisa es 'BS', debe ser > 0)",
  "lleva_iva": "boolean - OPCIONAL (default: false)",
  "iva": "number - OPCIONAL (default: 0, se calcula automáticamente si lleva_iva es true)",
  "notas": "string - OPCIONAL"
}
```

## Campos Requeridos (OBLIGATORIOS)

1. **proveedor_id**: ID del proveedor (string, ObjectId válido)
2. **farmacia**: Código de la farmacia (string, ej: "01", "02")
3. **items**: Array con al menos 1 item
   - **codigo**: Código del producto (string)
   - **nombre**: Nombre del producto (string)
   - **cantidad**: Cantidad comprada (number, > 0)
   - **costo_unitario**: Costo unitario (number, > 0)
4. **total**: Total de la compra (number, > 0)
5. **divisa**: Divisa de la compra ("BS" o "USD")

## Campos Opcionales

- **sucursal_id** o **sucursal**: ID de la sucursal
- **numero_factura**: Número de factura
- **numero_control**: Número de control
- **fecha_compra**: Si no se envía, se usa la fecha actual automáticamente
- **fecha_vencimiento_factura**: Se calcula automáticamente si hay días de crédito del proveedor
- **items[].precio_unitario**: Precio de venta (opcional)
- **items[].lote**: Número de lote (opcional)
- **items[].fecha_vencimiento**: Fecha de vencimiento del lote (opcional)
- **items[].descripcion**: Descripción adicional (opcional)
- **items[].lleva_iva**: Si el item lleva IVA (opcional, default: false)
- **tasa**: Tasa de cambio (REQUERIDO si divisa es "BS")
- **lleva_iva**: Si la compra lleva IVA (opcional, default: false)
- **iva**: Monto del IVA (opcional, se calcula automáticamente si lleva_iva es true)
- **notas**: Notas adicionales

## Ejemplo Completo de Request

### Ejemplo 1: Compra básica sin IVA
```json
{
  "proveedor_id": "507f1f77bcf86cd799439011",
  "farmacia": "01",
  "sucursal_id": "507f1f77bcf86cd799439012",
  "items": [
    {
      "codigo": "PROD001",
      "nombre": "Paracetamol 500mg",
      "cantidad": 100,
      "costo_unitario": 0.50,
      "precio_unitario": 1.00,
      "lote": "LOTE-2025-001",
      "fecha_vencimiento": "2026-12-31"
    }
  ],
  "total": 50.00,
  "divisa": "USD"
}
```

### Ejemplo 2: Compra con IVA
```json
{
  "proveedor_id": "507f1f77bcf86cd799439011",
  "farmacia": "01",
  "sucursal_id": "507f1f77bcf86cd799439012",
  "numero_factura": "FAC-001",
  "numero_control": "CTL-001",
  "fecha_compra": "2025-01-15",
  "items": [
    {
      "codigo": "PROD001",
      "nombre": "Paracetamol 500mg",
      "cantidad": 100,
      "costo_unitario": 0.50,
      "precio_unitario": 1.00,
      "lleva_iva": true
    }
  ],
  "total": 50.00,
  "divisa": "USD",
  "lleva_iva": true,
  "notas": "Compra mensual"
}
```

### Ejemplo 3: Compra en Bs (requiere tasa)
```json
{
  "proveedor_id": "507f1f77bcf86cd799439011",
  "farmacia": "01",
  "items": [
    {
      "codigo": "PROD001",
      "nombre": "Paracetamol 500mg",
      "cantidad": 100,
      "costo_unitario": 60.00
    }
  ],
  "total": 6000.00,
  "divisa": "BS",
  "tasa": 120.00
}
```

## Cálculo Automático del Backend

El backend calcula automáticamente:

1. **IVA**: Si `lleva_iva` es `true`, calcula `iva = total * 0.16` y `total_con_iva = total + iva`
2. **Fecha de compra**: Si no se envía, usa la fecha actual
3. **Fecha de vencimiento**: Si no se envía y el proveedor tiene `dias_credito`, calcula: `fecha_compra + dias_credito`
4. **Total**: Si no se envía, calcula sumando `cantidad * costo_unitario` de todos los items

## Validaciones del Backend

### Validaciones que el backend realiza:

1. **Permisos**: Requiere permiso `"compras"` o `"admin_completo"`
2. **Proveedor**: Debe existir en la base de datos
3. **Items**: Debe tener al menos 1 item
4. **Divisa BS**: Si `divisa` es "BS", `tasa` es REQUERIDO y debe ser > 0
5. **Cantidad**: Cada item debe tener `cantidad > 0`
6. **Costo unitario**: Cada item debe tener `costo_unitario > 0`
7. **Total**: Debe ser > 0

## Respuesta Exitosa (201 Created)

```json
{
  "_id": "compra_id",
  "proveedor_id": "507f1f77bcf86cd799439011",
  "proveedor_nombre": "Farmacia ABC",
  "farmacia": "01",
  "sucursal_id": "507f1f77bcf86cd799439012",
  "numero_factura": "FAC-001",
  "numero_control": "CTL-001",
  "fecha_compra": "2025-01-15",
  "fecha_vencimiento_factura": "2025-02-14",
  "items": [...],
  "total": 50.00,
  "divisa": "USD",
  "tasa": null,
  "lleva_iva": true,
  "iva": 8.00,
  "total_con_iva": 58.00,
  "notas": "Compra mensual",
  "usuario_creacion": "usuario@email.com",
  "fecha_creacion": "2025-01-15T10:30:00",
  "estado": "activa",
  "estado_pago": "sin_pago",
  "monto_pagado": 0,
  "monto_pendiente": 58.00,
  "dias_credito": 30,
  "dias_mora": 0
}
```

## Errores Comunes

### Error 422 - Validación
```json
{
  "detail": "Error de validación: body -> farmacia: Field required"
}
```
**Solución**: Asegúrate de enviar todos los campos requeridos.

### Error 400 - Tasa requerida
```json
{
  "detail": "La tasa de cambio es requerida cuando la divisa es BS"
}
```
**Solución**: Si `divisa` es "BS", debes enviar `tasa`.

### Error 404 - Proveedor no encontrado
```json
{
  "detail": "Proveedor no encontrado"
}
```
**Solución**: Verifica que el `proveedor_id` sea válido y exista.

## Headers Requeridos

```http
POST /compras
Content-Type: application/json
Authorization: Bearer <token>
```

## Checklist para el Frontend

- [ ] Enviar `proveedor_id` (string, ObjectId válido)
- [ ] Enviar `farmacia` (string, código de farmacia)
- [ ] Enviar `items` (array con al menos 1 item)
  - [ ] Cada item debe tener `codigo` (string)
  - [ ] Cada item debe tener `nombre` (string)
  - [ ] Cada item debe tener `cantidad` (number > 0)
  - [ ] Cada item debe tener `costo_unitario` (number > 0)
- [ ] Enviar `total` (number > 0)
- [ ] Enviar `divisa` ("BS" o "USD")
- [ ] Si `divisa` es "BS", enviar `tasa` (number > 0)
- [ ] Enviar header `Authorization: Bearer <token>`
- [ ] Enviar header `Content-Type: application/json`

## Notas Importantes

1. **fecha_compra es opcional**: Si no se envía, el backend usa la fecha actual
2. **lote es opcional**: Puede enviarse como `null`, `undefined` o simplemente omitirse
3. **IVA se calcula automáticamente**: Si `lleva_iva` es `true`, el backend calcula el 16% sobre el total
4. **Total puede calcularse**: Si no se envía, el backend calcula sumando `cantidad * costo_unitario` de todos los items
5. **nombre del item**: Si no se envía, el backend intenta usar `descripcion` o `codigo` como nombre

