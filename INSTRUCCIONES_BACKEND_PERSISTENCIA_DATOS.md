# Instrucciones Backend - Persistencia de Datos

## 🚨 Problema Crítico

**Los proveedores y compras creados no persisten - desaparecen después de un tiempo.**

## ✅ Verificaciones Realizadas

### 1. Verificación de `insert_one()` ✅

**Proveedores:**
- ✅ `POST /proveedores` usa `insert_one()` correctamente (línea 146)
- ✅ Los datos se insertan con todos los campos necesarios
- ✅ Se agrega `fecha_creacion` y `estado: "activo"`

**Compras:**
- ✅ `POST /compras` usa `insert_one()` correctamente (línea 555)
- ✅ Los datos se insertan con todos los campos necesarios
- ✅ Se agrega `fecha_creacion` y `estado: "activa"`

### 2. Verificación de Filtros de Fecha en GET ❌ NO HAY FILTROS

**GET /proveedores:**
```python
# Línea 54 - NO hay filtros de fecha
proveedores = await proveedores_collection.find(query).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
```
- ✅ Solo filtra por `estado` si se proporciona
- ✅ NO filtra por fecha
- ✅ Ordena por `fecha_creacion` descendente (más recientes primero), pero NO excluye datos antiguos

**GET /compras:**
```python
# Línea 1052 - NO hay filtros de fecha
compras = await compras_collection.find(query).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
```
- ✅ Solo filtra por `sucursal_id`, `estado`, `estado_pago` si se proporcionan
- ✅ NO filtra por fecha
- ✅ Ordena por `fecha_creacion` descendente (más recientes primero), pero NO excluye datos antiguos

### 3. Verificación de Índices TTL ❌ NO HAY TTL

**Búsqueda realizada:**
- ✅ NO se encontraron índices TTL en el código
- ✅ NO hay `expireAfterSeconds` en ningún lugar
- ✅ NO hay código que configure TTL automáticamente

### 4. Verificación de Código de Cleanup ❌ NO HAY CLEANUP

**Búsqueda realizada:**
- ✅ NO se encontró código de `delete_one()` o `delete_many()` en los endpoints de compras
- ✅ NO hay código de "cleanup" o "limpieza"
- ✅ NO hay cron jobs que eliminen datos
- ✅ NO hay código que elimine datos automáticamente

### 5. Verificación de Conexión a MongoDB ✅

**Código de conexión:**
- ✅ La conexión se establece correctamente en `app/db/mongo.py`
- ✅ Se usa `AsyncIOMotorClient` que mantiene la conexión persistente
- ✅ No hay código que cierre la conexión automáticamente

## 🔍 Diagnóstico Adicional

### Logging Agregado

Se ha agregado logging detallado en:
- `POST /proveedores`: Muestra los datos antes de insertar y después de crear
- `POST /compras`: Muestra los datos antes de insertar y después de crear

**Ejemplo de logs esperados:**
```
[CREAR-PROVEEDOR] Datos del proveedor a guardar: {...}
[CREAR-PROVEEDOR] Proveedor creado exitosamente: {...}
[CREAR-COMPRA] Compra creada con ID: ...
```

### Verificación Directa en MongoDB

Para verificar que los datos se están guardando correctamente, ejecuta estas consultas en MongoDB:

```javascript
// Verificar proveedores
db.PROVEEDORES.find({}).sort({fecha_creacion: -1}).limit(10)

// Verificar compras
db.COMPRAS.find({}).sort({fecha_creacion: -1}).limit(10)

// Contar total de proveedores
db.PROVEEDORES.countDocuments({})

// Contar total de compras
db.COMPRAS.countDocuments({})

// Verificar proveedores por estado
db.PROVEEDORES.find({estado: "activo"}).count()

// Verificar compras por estado
db.COMPRAS.find({estado: "activa"}).count()
```

## 🛠️ Soluciones Implementadas

### 1. Logging Mejorado

Se agregó logging detallado para rastrear:
- Datos antes de insertar
- Resultado de la inserción
- Datos después de crear
- Errores si ocurren

### 2. Normalización de Campos

Se aseguró que todos los campos numéricos tengan valores por defecto:
- `dias_credito`: 0 si es None
- `descuento_comercial`: 0.0 si es None
- `descuento_pronto_pago`: 0.0 si es None
- `monto_pagado`: 0.0 si es None
- `monto_pendiente`: calculado si es None

### 3. Verificación de Inserción

Después de insertar, se verifica que el documento se creó correctamente:
```python
# Obtener el proveedor creado
proveedor_creado = await proveedores_collection.find_one({"_id": ObjectId(proveedor_id)})
```

## 📋 Checklist de Verificación

- [x] ✅ `POST /proveedores` usa `insert_one()`
- [x] ✅ `POST /compras` usa `insert_one()`
- [x] ✅ `GET /proveedores` NO tiene filtros de fecha
- [x] ✅ `GET /compras` NO tiene filtros de fecha
- [x] ✅ NO hay índices TTL
- [x] ✅ NO hay código de cleanup
- [x] ✅ Logging agregado
- [x] ✅ Verificación de inserción agregada

## 🔧 Acciones Recomendadas

### 1. Verificar en MongoDB Directamente

Ejecuta estas consultas para verificar que los datos existen:

```bash
# Conectar a MongoDB
mongosh "tu_connection_string"

# Ver proveedores
use rapifarma
db.PROVEEDORES.find({}).sort({fecha_creacion: -1})

# Ver compras
db.COMPRAS.find({}).sort({fecha_creacion: -1})
```

### 2. Revisar Logs del Backend

Busca en los logs estos mensajes:
- `[CREAR-PROVEEDOR] Datos del proveedor a guardar:`
- `[CREAR-PROVEEDOR] Proveedor creado exitosamente:`
- `[CREAR-COMPRA] Compra creada con ID:`

### 3. Verificar Variables de Entorno

Asegúrate de que `MONGODB_URI` esté correctamente configurada y apunte a la base de datos correcta.

### 4. Verificar Permisos de MongoDB

Asegúrate de que el usuario de MongoDB tenga permisos de:
- `readWrite` en la base de datos
- No tenga restricciones de TTL o expiración

### 5. Verificar Índices en MongoDB

Ejecuta esto para ver todos los índices:
```javascript
// Ver índices de PROVEEDORES
db.PROVEEDORES.getIndexes()

// Ver índices de COMPRAS
db.COMPRAS.getIndexes()
```

**Busca índices con `expireAfterSeconds`** - si encuentras alguno, elimínalo:
```javascript
// Eliminar índice TTL (ejemplo)
db.PROVEEDORES.dropIndex("nombre_del_indice")
```

## 🚨 Posibles Causas del Problema

### 1. Base de Datos Incorrecta
- Verifica que `MONGODB_URI` apunte a la base de datos correcta
- Verifica que no haya múltiples bases de datos

### 2. Colección Incorrecta
- Verifica que los datos se guarden en `PROVEEDORES` y `COMPRAS` (mayúsculas)
- Verifica que no haya diferencias en mayúsculas/minúsculas

### 3. Filtros en el Frontend
- Verifica que el frontend no esté filtrando por fecha
- Verifica que el frontend esté usando los endpoints correctos

### 4. Caché del Frontend
- Limpia el caché del navegador
- Verifica que el frontend no esté usando datos en caché

### 5. Problema de Conexión
- Verifica que la conexión a MongoDB sea estable
- Verifica que no haya timeouts

## 📝 Próximos Pasos

1. **Verificar en MongoDB directamente** - Usa las consultas proporcionadas arriba
2. **Revisar logs del backend** - Busca los mensajes de logging
3. **Verificar índices TTL** - Ejecuta `getIndexes()` y busca `expireAfterSeconds`
4. **Verificar variables de entorno** - Asegúrate de que `MONGODB_URI` sea correcta
5. **Contactar soporte de MongoDB** - Si usas MongoDB Atlas, verifica que no haya configuraciones de expiración automática

## 🔗 Documentos Relacionados

- `INSTRUCCIONES_BACKEND_COMPRAS.md` - Instrucciones básicas del módulo de compras
- `INSTRUCCIONES_BACKEND_COMPRAS_IVA_CUENTAS_PAGAR.md` - IVA y cuentas por pagar
- `INSTRUCCIONES_BACKEND_COMPRAS_ACTUALIZAR_INVENTARIO.md` - Actualización de inventario

