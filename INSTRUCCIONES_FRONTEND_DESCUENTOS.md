# Instrucciones para el Frontend - Manejo de Descuentos en Ventas

## ✅ Backend Listo
El backend ya está completamente configurado para:
- ✅ Guardar `porcentaje_descuento` en el modelo de cliente
- ✅ Aceptar y almacenar descuentos en las ventas
- ✅ Devolver descuentos en las respuestas de clientes y ventas

## Lo que el Frontend DEBE Implementar

### 1. **Guardar descuento en el cliente** ⚠️ CRÍTICO
Cuando se crea o actualiza un cliente, el campo `porcentaje_descuento` debe enviarse:

```javascript
// Al crear/actualizar cliente
const clienteData = {
  cedula: "12345678",
  nombre: "Juan Pérez",
  // ... otros campos
  porcentaje_descuento: 10.0  // ✅ REQUERIDO: Porcentaje de descuento (0-100)
};
```

### 2. **Mostrar descuento en el modal del cliente** ⚠️ CRÍTICO
Cuando se muestra la información del cliente, debe aparecer:

```jsx
// En el modal del cliente
{cliente.porcentaje_descuento && (
  <div className="descuento-badge">
    <span>Descuento: {cliente.porcentaje_descuento}%</span>
  </div>
)}
```

### 3. **Aplicar descuento automáticamente al seleccionar cliente** ⚠️ CRÍTICO
Cuando se selecciona un cliente con descuento, aplicar automáticamente a todos los items:

```javascript
function aplicarDescuentoCliente(cliente, items) {
  if (!cliente.porcentaje_descuento || cliente.porcentaje_descuento === 0) {
    return items; // Sin descuento
  }
  
  return items.map(item => {
    // Guardar precio original ANTES de aplicar descuento
    const precioOriginalBs = item.precio_unitario;
    const precioOriginalUsd = item.precio_unitario_usd || 0;
    
    // Calcular precio con descuento
    const descuento = cliente.porcentaje_descuento / 100;
    const precioConDescuentoBs = precioOriginalBs * (1 - descuento);
    const precioConDescuentoUsd = precioOriginalUsd * (1 - descuento);
    
    return {
      ...item,
      precio_unitario_original: precioOriginalBs,  // ✅ REQUERIDO
      precio_unitario_original_usd: precioOriginalUsd,  // ✅ REQUERIDO
      precio_unitario: precioConDescuentoBs,  // Actualizado con descuento
      precio_unitario_usd: precioConDescuentoUsd,  // Actualizado con descuento
      subtotal: precioConDescuentoBs * item.cantidad,
      subtotal_usd: precioConDescuentoUsd * item.cantidad,
      descuento_aplicado: cliente.porcentaje_descuento  // ✅ REQUERIDO
    };
  });
}
```

### 4. **Mostrar % de descuento en la pantalla de ventas** ⚠️ CRÍTICO
Debe aparecer visiblemente el descuento aplicado:

```jsx
// En la pantalla de ventas
{clienteSeleccionado?.porcentaje_descuento > 0 && (
  <div className="descuento-activo">
    <Badge color="success">
      Descuento: {clienteSeleccionado.porcentaje_descuento}% ACTIVO
    </Badge>
  </div>
)}
```

### 5. **Mostrar precio original y precio con descuento** ⚠️ CRÍTICO
En cada item de la venta, mostrar ambos precios:

```jsx
// En cada item de la lista
{item.precio_unitario_original && (
  <div>
    <span style={{ textDecoration: 'line-through', color: 'gray' }}>
      {item.precio_unitario_original} Bs
    </span>
    <span style={{ color: 'green', fontWeight: 'bold', marginLeft: '8px' }}>
      {item.precio_unitario} Bs
    </span>
    {item.descuento_aplicado > 0 && (
      <Badge color="success" style={{ marginLeft: '8px' }}>
        -{item.descuento_aplicado}%
      </Badge>
    )}
  </div>
)}
```

## Estructura de Datos que el Backend Espera

### Al crear una venta (POST /punto-venta/ventas):

**Cada item debe incluir:**
```json
{
  "producto_id": "...",
  "nombre": "...",
  "codigo": "...",
  "cantidad": 2,
  "precio_unitario": 113.75,  // ✅ Precio CON descuento (Bs)
  "precio_unitario_usd": 2.50,  // ✅ Precio CON descuento (USD)
  "precio_unitario_original": 125.00,  // ✅ REQUERIDO: Precio SIN descuento (Bs)
  "precio_unitario_original_usd": 2.78,  // ✅ REQUERIDO: Precio SIN descuento (USD)
  "subtotal": 227.50,  // ✅ Subtotal CON descuento (Bs)
  "subtotal_usd": 5.00,  // ✅ Subtotal CON descuento (USD)
  "descuento_aplicado": 10.0  // ✅ REQUERIDO: Porcentaje de descuento aplicado
}
```

**La venta debe incluir:**
```json
{
  "items": [...],
  "metodos_pago": [...],
  "total_bs": 227.50,
  "total_usd": 5.00,
  "tasa_dia": 45.50,
  "sucursal": "01",
  "cajero": "...",
  "cliente": "690c40be93d9d9d635fbae83",
  "porcentaje_descuento": 10.0,  // ✅ REQUERIDO: Porcentaje de descuento a nivel de venta
  "notas": ""
}
```

## Lo que el Frontend DEBE hacer

### 1. Al aplicar un descuento al cliente:

**Cuando se selecciona un cliente con descuento:**
- Obtener el porcentaje de descuento del cliente (ej: 10%)
- Aplicar el descuento a todos los items de la venta
- Calcular:
  - `precio_unitario_original` = precio original sin descuento
  - `precio_unitario` = precio original × (1 - descuento/100)
  - `descuento_aplicado` = porcentaje de descuento del cliente
  - `subtotal` = precio_unitario × cantidad

**Ejemplo de cálculo:**
```javascript
const precioOriginal = 125.00;
const descuentoPorcentaje = 10; // 10%
const precioConDescuento = precioOriginal * (1 - descuentoPorcentaje / 100); // 112.50

const item = {
  precio_unitario_original: precioOriginal,  // ✅ REQUERIDO
  precio_unitario: precioConDescuento,  // Con descuento
  descuento_aplicado: descuentoPorcentaje,  // ✅ REQUERIDO
  // ... otros campos
};
```

### 2. Al enviar la venta al backend:

**Asegurar que TODOS los campos estén presentes:**
```javascript
const ventaData = {
  items: items.map(item => ({
    producto_id: item.producto_id,
    nombre: item.nombre,
    codigo: item.codigo,
    cantidad: item.cantidad,
    precio_unitario: item.precio_unitario,  // CON descuento
    precio_unitario_usd: item.precio_unitario_usd,  // CON descuento
    precio_unitario_original: item.precio_unitario_original,  // ✅ REQUERIDO
    precio_unitario_original_usd: item.precio_unitario_original_usd,  // ✅ REQUERIDO
    subtotal: item.subtotal,  // CON descuento
    subtotal_usd: item.subtotal_usd,  // CON descuento
    descuento_aplicado: item.descuento_aplicado  // ✅ REQUERIDO
  })),
  metodos_pago: metodosPago,
  total_bs: totalBs,
  total_usd: totalUsd,
  tasa_dia: tasaDia,
  sucursal: sucursal,
  cajero: cajero,
  cliente: clienteId,
  porcentaje_descuento: descuentoPorcentaje,  // ✅ REQUERIDO
  notas: notas
};
```

### 3. Mostrar el descuento en la interfaz:

**En la pantalla de ventas:**
- Mostrar un badge o indicador visual con el % de descuento aplicado
- Ejemplo: "Descuento: 10%" o "10% OFF"
- Mostrar el precio original tachado y el precio con descuento destacado

**En el modal del cliente:**
- Mostrar el porcentaje de descuento del cliente
- Ejemplo: "Este cliente tiene un descuento del 10%"
- Mostrar un indicador visual cuando el descuento está activo

**En el resumen de la venta:**
- Mostrar el total sin descuento
- Mostrar el descuento aplicado
- Mostrar el total con descuento

### 4. Al obtener el historial de compras del cliente:

**Endpoint: GET /clientes/{cliente_id}/compras/items**

Este endpoint ya devuelve los items con descuentos. El frontend debe:
- Mostrar el precio original y el precio con descuento
- Mostrar el porcentaje de descuento aplicado en cada item
- Calcular y mostrar el ahorro total del cliente

## Checklist para el Frontend

- [ ] Al seleccionar un cliente con descuento, aplicar el descuento automáticamente a todos los items
- [ ] Calcular y guardar `precio_unitario_original` y `precio_unitario_original_usd` para cada item
- [ ] Incluir `descuento_aplicado` en cada item al enviar la venta
- [ ] Incluir `porcentaje_descuento` a nivel de venta al enviar la venta
- [ ] Mostrar el % de descuento en la interfaz de ventas (badge o indicador)
- [ ] Mostrar el descuento del cliente en el modal del cliente
- [ ] Mostrar precio original tachado y precio con descuento destacado
- [ ] Mostrar el ahorro total en el resumen de la venta
- [ ] Al obtener historial de compras, mostrar descuentos aplicados

## Ejemplo de Código para el Frontend

### Aplicar descuento a un item:
```javascript
function aplicarDescuentoAItem(item, descuentoPorcentaje) {
  // Guardar precio original
  const precioOriginalBs = item.precio_unitario;
  const precioOriginalUsd = item.precio_unitario_usd;
  
  // Calcular precio con descuento
  const precioConDescuentoBs = precioOriginalBs * (1 - descuentoPorcentaje / 100);
  const precioConDescuentoUsd = precioOriginalUsd * (1 - descuentoPorcentaje / 100);
  
  // Actualizar item
  return {
    ...item,
    precio_unitario_original: precioOriginalBs,  // ✅ REQUERIDO
    precio_unitario_original_usd: precioOriginalUsd,  // ✅ REQUERIDO
    precio_unitario: precioConDescuentoBs,
    precio_unitario_usd: precioConDescuentoUsd,
    subtotal: precioConDescuentoBs * item.cantidad,
    subtotal_usd: precioConDescuentoUsd * item.cantidad,
    descuento_aplicado: descuentoPorcentaje  // ✅ REQUERIDO
  };
}
```

### Enviar venta con descuentos:
```javascript
async function enviarVenta(ventaData) {
  // Asegurar que todos los campos de descuento estén presentes
  const ventaCompleta = {
    ...ventaData,
    items: ventaData.items.map(item => ({
      ...item,
      precio_unitario_original: item.precio_unitario_original || item.precio_unitario,  // Fallback
      precio_unitario_original_usd: item.precio_unitario_original_usd || item.precio_unitario_usd,  // Fallback
      descuento_aplicado: item.descuento_aplicado || 0  // Fallback a 0 si no hay descuento
    })),
    porcentaje_descuento: ventaData.porcentaje_descuento || 0  // Fallback a 0 si no hay descuento
  };
  
  const response = await fetch('/punto-venta/ventas', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(ventaCompleta)
  });
  
  return response.json();
}
```

## Notas Importantes

1. **El backend NO calcula descuentos**: El frontend debe calcular y enviar todos los valores
2. **Campos opcionales pero recomendados**: Aunque son opcionales, es importante enviarlos para reportes
3. **Validación**: El backend valida la consistencia de descuentos pero no bloquea la venta si hay diferencias menores
4. **Compatibilidad**: Si no hay descuento, enviar `descuento_aplicado: 0` y `porcentaje_descuento: 0`

## Endpoints del Backend Disponibles

- `POST /punto-venta/ventas` - Crear venta (acepta descuentos)
- `GET /clientes/{id}/compras/items` - Obtener items comprados (incluye descuentos)
- `GET /clientes/{id}/compras/total` - Obtener total de compras

