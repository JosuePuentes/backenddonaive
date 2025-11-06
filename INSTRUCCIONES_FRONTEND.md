# Instrucciones para el Frontend - Sincronización con Backend

## ✅ SOLUCIÓN IMPLEMENTADA

El backend ahora busca items **POR CÓDIGO DEL PRODUCTO** (el código que está en la colección PRODUCTOS), no por el código interno de MongoDB.

## Lo que el Frontend DEBE Hacer

### 1. Enviar el CÓDIGO DEL PRODUCTO en el PATCH

**IMPORTANTE**: El frontend debe enviar el **código del producto** (el campo `codigo` del producto en PRODUCTOS), NO el `_id` interno de MongoDB.

### 2. Ejemplo de uso correcto

```javascript
// ✅ CORRECTO - Usar el código del producto
const codigoProducto = item.codigo; // Ejemplo: "67", "PROD001", etc.

await fetch(`/inventarios/${inventarioId}/items/${codigoProducto}`, {
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ 
    cantidad: 10,
    precio_unitario: 25.50,
    costo_unitario: 15.00
  })
});
```

### 3. Ejemplo completo

```javascript
// Obtener items del inventario
const response = await fetch(`/inventarios/${inventarioId}/items`);
const items = await response.json();

// Cada item tiene:
// {
//   _id: "690c40be93d9d9d635fbae83",  // <- NO usar este
//   item_id: "690c40be93d9d9d635fbae83", // <- NO usar este
//   codigo: "67",  // <- ✅ USAR ESTE (código del producto)
//   nombre: "Producto X",
//   cantidad: 5,
//   ...
// }

// Modificar un item usando el CÓDIGO del producto
const codigoProducto = item.codigo; // "67"
await fetch(`/inventarios/${inventarioId}/items/${codigoProducto}`, {
  method: 'PATCH',
  body: JSON.stringify({ cantidad: 10 })
});
```

### 4. Ejemplo INCORRECTO (no hacer esto)

```javascript
// ❌ INCORRECTO - No uses el _id interno de MongoDB
await fetch(`/inventarios/${inventarioId}/items/${item._id}`, {
  method: 'PATCH',
  ...
});

// ❌ INCORRECTO - No uses el item_id interno
await fetch(`/inventarios/${inventarioId}/items/${item.item_id}`, {
  method: 'PATCH',
  ...
});
```

## Cómo funciona el Backend

El backend ahora busca en este orden:

1. **PRIORIDAD 1**: Busca el producto en PRODUCTOS por código
   - Si `item_id` es un ObjectId, busca el producto por `_id` y obtiene su código
   - Si `item_id` no es ObjectId, asume que es el código y busca directamente
   - Luego busca el item en el inventario que tenga ese código

2. **PRIORIDAD 2**: Si no encuentra por código del producto, busca por `_id` interno del item

3. **PRIORIDAD 3**: Si no encuentra, busca por código directamente en items

4. **PRIORIDAD 4**: Si no encuentra, busca por índice numérico

## Checklist para el Frontend

- [x] ✅ Usar el campo `codigo` del item para hacer PATCH
- [x] ✅ NO usar `_id` o `item_id` internos de MongoDB
- [x] ✅ El código debe ser el mismo que está en la colección PRODUCTOS
- [x] ✅ Asegurarse de que el `inventario_id` en la URL coincida con el inventario del item

## Notas Adicionales

- El backend agrega automáticamente `inventario_id` a los items que no lo tengan
- Los nuevos items se crean automáticamente con `inventario_id`
- El script de migración `migrate_add_inventario_id_to_items.py` actualizará los items existentes
- El backend soporta códigos numéricos y strings

