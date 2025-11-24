# Instrucciones: Campo stock_por_sucursal en Búsqueda de Productos

## Requerimiento

El endpoint `/punto-venta/productos/buscar` debe incluir el campo `stock_por_sucursal` en cada producto con el stock en todas las sucursales, incluyendo el nombre real de cada sucursal.

## Estructura Requerida

Cada producto en la respuesta debe incluir:

```json
{
  "id": "producto_id",
  "nombre": "Nombre del Producto",
  "codigo": "COD123",
  "precio": 100.00,
  "stock": 50,
  "cantidad": 50,
  "stock_por_sucursal": [
    {
      "sucursal_id": "sucursal_id_1",
      "sucursal_nombre": "Sucursal Centro",
      "cantidad": 20,
      "stock": 20
    },
    {
      "sucursal_id": "sucursal_id_2",
      "sucursal_nombre": "Sucursal Norte",
      "cantidad": 30,
      "stock": 30
    }
  ],
  "lotes": [...],
  "sucursal": "sucursal_actual"
}
```

## Implementación Actual

### Función Helper: `obtener_stock_por_sucursal()`

La función `obtener_stock_por_sucursal(codigo_producto: str)` en `app/routes/punto_venta.py`:

1. **Obtiene todas las sucursales** desde las colecciones `SUCURSALES` y `FARMACIAS`
2. **Obtiene el nombre real** de cada sucursal usando `obtener_nombre_sucursal()`
3. **Busca el producto** en todos los inventarios activos por código
4. **Calcula el stock** sumando lotes si existen, o usando la cantidad del item
5. **Retorna una lista** con el stock en todas las sucursales, incluyendo sucursales con stock 0

### Endpoint: `/punto-venta/productos/buscar`

El endpoint ahora incluye `stock_por_sucursal` para cada producto:

```python
# Obtener stock por sucursal para cada producto
stock_por_sucursal_list = []
if codigo_producto:
    try:
        stock_por_sucursal_list = await obtener_stock_por_sucursal(codigo_producto)
    except Exception as e:
        print(f"[BUSCAR-PRODUCTOS] Error al obtener stock por sucursal: {str(e)}")
        # Continuar sin stock por sucursal si hay error

resultado.append(ProductoItem(
    # ... otros campos ...
    stock_por_sucursal=stock_por_sucursal_list,  # Stock en todas las sucursales con nombres
    # ... otros campos ...
))
```

## Schema

El schema `StockPorSucursal` en `app/schemas/punto_venta.py` define la estructura:

```python
class StockPorSucursal(BaseModel):
    """Modelo para stock por sucursal"""
    sucursal_id: str
    sucursal_nombre: Optional[str] = None
    cantidad: int  # Stock total (suma de lotes si existen)
    stock: int  # Alias para compatibilidad
```

## Características Importantes

1. **Nombres Reales de Sucursales**: Se obtienen usando `obtener_nombre_sucursal()` que busca en:
   - Colección `SUCURSALES`
   - Colección `FARMACIAS`
   - Usa el campo `nombre` o `farmacia` del documento

2. **Todas las Sucursales**: Incluye todas las sucursales, incluso si tienen stock 0

3. **Cálculo de Stock**: 
   - Si el item tiene lotes, suma las cantidades de todos los lotes
   - Si no tiene lotes, usa la cantidad del item directamente

4. **Manejo de Errores**: Si hay un error al obtener stock por sucursal, el producto se retorna sin ese campo (lista vacía) en lugar de fallar toda la búsqueda

## Ejemplo de Respuesta Completa

```json
{
  "facturas": [],
  "productos": [
    {
      "id": "507f1f77bcf86cd799439011",
      "nombre": "Paracetamol 500mg",
      "codigo": "PAR500",
      "precio": 5.50,
      "precio_usd": null,
      "stock": 150,
      "cantidad": 150,
      "stock_por_sucursal": [
        {
          "sucursal_id": "507f1f77bcf86cd799439012",
          "sucursal_nombre": "Farmacia Centro",
          "cantidad": 50,
          "stock": 50
        },
        {
          "sucursal_id": "507f1f77bcf86cd799439013",
          "sucursal_nombre": "Farmacia Norte",
          "cantidad": 75,
          "stock": 75
        },
        {
          "sucursal_id": "507f1f77bcf86cd799439014",
          "sucursal_nombre": "Farmacia Sur",
          "cantidad": 25,
          "stock": 25
        }
      ],
      "lotes": [],
      "sucursal": "507f1f77bcf86cd799439012"
    }
  ]
}
```

## Notas de Rendimiento

- La función `obtener_stock_por_sucursal()` puede ser costosa si hay muchos inventarios
- Se ejecuta para cada producto en los resultados de búsqueda
- Si el rendimiento es un problema, se puede optimizar usando agregaciones de MongoDB o cache

## Verificación

Para verificar que funciona correctamente:

1. Hacer una búsqueda de productos: `GET /punto-venta/productos/buscar?q=paracetamol`
2. Verificar que cada producto tenga el campo `stock_por_sucursal`
3. Verificar que cada entrada en `stock_por_sucursal` tenga:
   - `sucursal_id`: ID válido de la sucursal
   - `sucursal_nombre`: Nombre real de la sucursal (no solo el ID)
   - `cantidad`: Stock numérico correcto
   - `stock`: Mismo valor que `cantidad`

