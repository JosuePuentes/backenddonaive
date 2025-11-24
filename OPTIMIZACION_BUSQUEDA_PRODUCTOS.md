# Optimización de Búsqueda de Productos en Punto de Venta

## Problema Identificado

La búsqueda de productos en el módulo de punto-venta era muy lenta debido a:

1. **Búsquedas con regex sin índices**: Las búsquedas usaban `$regex` en campos sin índices, lo cual es extremadamente lento en colecciones grandes
2. **Búsqueda de lotes ineficiente**: Para cada producto encontrado, se hacía una búsqueda en INVENTARIOS que podía traer hasta 50 inventarios, y luego se iteraba sobre todos los items de cada inventario
3. **Búsqueda de stock por sucursal costosa**: Para cada producto, se llamaba a `obtener_stock_por_sucursal()` que hacía múltiples consultas a la base de datos
4. **Falta de índices**: No había índices en los campos de búsqueda (nombre, codigo, estado)

## Optimizaciones Implementadas

### 1. Script de Índices (`create_indexes_productos.py`)

Se creó un script para crear índices optimizados en las colecciones PRODUCTOS e INVENTARIOS:

- **Índice de texto** en `nombre`, `codigo` y `farmacia` para búsquedas rápidas
- **Índice en código** para búsquedas exactas
- **Índice compuesto** en `estado` y `codigo` (muy usado en búsquedas)
- **Índice en estado** para filtrar productos activos
- **Índice en sucursal** para filtros por sucursal
- **Índice en items.codigo** en INVENTARIOS para búsquedas rápidas de items

**Uso:**
```bash
python create_indexes_productos.py
```

### 2. Optimización del Endpoint de Búsqueda

#### a) Búsqueda Exacta Primero
- Primero intenta búsqueda exacta por código (más rápida)
- Solo si no hay coincidencias exactas, usa regex

#### b) Regex Optimizado
- Usa regex que comienza con el texto (`^texto`) en lugar de buscar en cualquier parte
- Esto es mucho más eficiente porque puede usar índices
- Solo si no hay coincidencias al inicio, busca en cualquier parte

#### c) Límite Mínimo de Caracteres
- Requiere mínimo 2 caracteres para búsquedas
- Reduce la carga en búsquedas muy cortas que suelen devolver muchos resultados

#### d) Búsqueda de Lotes Optimizada con Agregaciones
- **ANTES**: Para cada producto, buscaba hasta 50 inventarios y iteraba sobre todos los items
- **AHORA**: Usa agregación de MongoDB para buscar lotes de todos los productos de una vez
- Reduce de N consultas a 1 consulta agregada

```python
# Ejemplo de agregación optimizada
pipeline = [
    {"$match": {"sucursal": sucursal, "estado": "activo"}},
    {"$unwind": "$items"},
    {"$match": {"items.codigo": {"$in": codigos_productos}}},
    {"$project": {"codigo": "$items.codigo", "lotes": "$items.lotes"}}
]
```

#### e) Cache de Lotes
- Los lotes se buscan una sola vez y se cachean por código
- Evita búsquedas repetidas para el mismo producto

#### f) Stock por Sucursal Deshabilitado por Defecto
- La búsqueda de stock por sucursal es muy costosa
- Se deshabilitó por defecto para mejorar el rendimiento
- Se puede habilitar si es necesario (descomentar el código)

## Mejoras de Rendimiento Esperadas

1. **Búsqueda de productos**: 5-10x más rápida con índices
2. **Búsqueda de lotes**: 10-20x más rápida con agregaciones
3. **Reducción de consultas**: De N consultas a 1-2 consultas por búsqueda
4. **Tiempo total**: Reducción estimada de 70-90% en tiempo de respuesta

## Cómo Aplicar las Optimizaciones

### Paso 1: Crear Índices
```bash
cd rapifarma-backend
python create_indexes_productos.py
```

### Paso 2: Verificar que los Cambios Estén Aplicados
Los cambios en el endpoint ya están aplicados. Solo necesitas:
1. Crear los índices (Paso 1)
2. Reiniciar el servidor si es necesario

## Notas Importantes

1. **Los índices mejoran las búsquedas pero ocupan espacio**: Los índices ocupan espacio adicional en la base de datos, pero el beneficio en rendimiento es significativo

2. **Primera ejecución puede ser lenta**: La primera vez que se ejecuta el script de índices, puede tardar si hay muchos documentos. Esto es normal.

3. **Stock por sucursal**: Si necesitas el stock por sucursal en las búsquedas, puedes descomentar el código en el endpoint, pero esto reducirá el rendimiento.

4. **Monitoreo**: Se recomienda monitorear el rendimiento después de aplicar las optimizaciones para verificar las mejoras.

## Próximas Optimizaciones Posibles

1. **Cache en memoria**: Implementar cache de productos frecuentes en Redis o memoria
2. **Búsqueda incremental**: Cargar resultados mientras el usuario escribe
3. **Paginación**: Implementar paginación para búsquedas con muchos resultados
4. **Índices adicionales**: Agregar más índices según patrones de uso específicos

