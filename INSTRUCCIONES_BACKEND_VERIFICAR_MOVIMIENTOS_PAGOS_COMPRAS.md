# Instrucciones Backend - Verificar Movimientos de Pagos de Compras

## 🔍 Problema Reportado

Los movimientos de tipo `"pago_compra"` no aparecen en el historial del banco cuando se consulta `GET /bancos/{banco_id}/movimientos`.

## ✅ Acción Requerida del Backend

El backend debe verificar los siguientes puntos:

### 1. Verificar en MongoDB si existen movimientos de tipo "pago_compra"

**Consulta en MongoDB:**
```javascript
// Conectar a MongoDB
use rapifarma  // o el nombre de tu base de datos

// Buscar todos los movimientos de tipo "pago_compra"
db.movimientos_bancos.find({ tipo: "pago_compra" }).pretty()

// Contar cuántos hay
db.movimientos_bancos.countDocuments({ tipo: "pago_compra" })

// Verificar el formato de banco_id (debe ser ObjectId, no string)
db.movimientos_bancos.find({ tipo: "pago_compra" }).forEach(function(doc) {
    print("Movimiento ID: " + doc._id);
    print("Banco ID: " + doc.banco_id + " (tipo: " + typeof doc.banco_id + ")");
    print("Tipo: " + doc.tipo);
    print("Monto: " + doc.monto);
    print("---");
})
```

**Qué verificar:**
- ✅ ¿Existen movimientos de tipo `"pago_compra"`?
- ✅ ¿El `banco_id` es ObjectId o string?
- ✅ ¿El `monto` es negativo?
- ✅ ¿La `descripcion` está completa?

### 2. Verificar que el código de creación del movimiento esté presente y se ejecute

**Ubicación:** `app/routes/compras.py` (función `crear_pago_compra`)

**Código que debe estar presente:**
```python
# Si se proporciona banco_id, validar y restar el saldo del banco
if banco_id:
    # ... validación del banco ...
    
    # Crear movimiento en el banco
    movimientos_collection = get_collection("MOVIMIENTOS_BANCOS")
    
    movimiento = {
        "banco_id": banco_oid,  # ✅ ObjectId, NO string
        "tipo": "pago_compra",
        "monto": -abs(monto),  # ✅ Negativo usando abs()
        "divisa": divisa_banco,
        "compra_id": compra_id,
        "pago_id": None,  # Se actualizará después
        "proveedor_id": proveedor_id,
        "proveedor_nombre": proveedor_nombre,
        "numero_factura": numero_factura,
        "fecha": datetime.now().isoformat(),
        "fecha_pago": fecha_pago,
        "usuario": usuario.get("correo", usuario.get("usuarioCorreo", "")),
        "descripcion": descripcion,
        "referencia": referencia,
        "metodo_pago": metodo_pago,
        "notas": notas,
        "saldo_anterior": saldo_actual,
        "saldo_nuevo": nuevo_saldo
    }
    
    # Insertar movimiento
    result_movimiento = await movimientos_collection.insert_one(movimiento)
    movimiento_id = str(result_movimiento.inserted_id)
    movimiento_id_obj = result_movimiento.inserted_id
    
    print(f"[CREAR-PAGO-COMPRA] ✅ Movimiento creado exitosamente!")
    print(f"[CREAR-PAGO-COMPRA] ✅ ID del movimiento: {movimiento_id}")
    print(f"[CREAR-PAGO-COMPRA] ✅ Banco ID (ObjectId): {banco_oid}")
    print(f"[CREAR-PAGO-COMPRA] ✅ Tipo: {movimiento['tipo']}")
    print(f"[CREAR-PAGO-COMPRA] ✅ Monto: {movimiento['monto']} {movimiento['divisa']}")
```

**Verificar:**
- ✅ ¿El código está presente en el archivo?
- ✅ ¿Se ejecuta cuando se crea un pago con `banco_id`?
- ✅ ¿Los logs muestran `✅ Movimiento creado exitosamente!`?

### 3. Verificar que el query en `GET /bancos/{banco_id}/movimientos` no filtre por tipo

**Ubicación:** `app/main.py` (función `obtener_movimientos_banco`)

**Código que debe estar presente:**
```python
# Buscar movimientos: puede estar guardado como string o como ObjectId
query = {
    "$or": [
        {"banco_id": banco_id},  # String (para compatibilidad)
        {"banco_id": banco_oid}   # ObjectId (formato correcto)
    ]
}
# ✅ NO debe haber filtro por tipo aquí

movimientos_docs = await movimientos_collection.find(query).sort("fecha", -1).to_list(length=None)
```

**Verificar:**
- ✅ ¿El query NO incluye `"tipo": "pago_compra"`?
- ✅ ¿El query busca tanto por string como por ObjectId?
- ✅ ¿Los logs muestran los movimientos encontrados por tipo?

### 4. Revisar los logs del backend al crear un pago

**Logs esperados al crear un pago de compra:**

```
[CREAR-PAGO-COMPRA] 📝 Creando movimiento en banco {banco_id} (ObjectId: {banco_oid})
[CREAR-PAGO-COMPRA] 📝 Datos del movimiento: tipo=pago_compra, monto=-500.0, banco_id=ObjectId
[CREAR-PAGO-COMPRA] ✅ Movimiento creado exitosamente!
[CREAR-PAGO-COMPRA] ✅ ID del movimiento: {movimiento_id}
[CREAR-PAGO-COMPRA] ✅ Banco ID (ObjectId): {banco_oid}
[CREAR-PAGO-COMPRA] ✅ Tipo: pago_compra
[CREAR-PAGO-COMPRA] ✅ Monto: -500.0 USD
[CREAR-PAGO-COMPRA] ✅ Descripción: Pago Compra - Proveedor ABC (Factura FAC-001) - Ref: TRF-123
```

**Logs esperados al consultar movimientos:**

```
[OBTENER-MOVIMIENTOS-BANCO] Buscando movimientos para banco: {banco_id}
[OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados X movimientos en MOVIMIENTOS_BANCOS
[OBTENER-MOVIMIENTOS-BANCO] 📊 Movimientos por tipo: {'pago_compra': 2, 'venta': 5, 'vuelto': 1}
[OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados 2 movimientos de tipo 'pago_compra'
```

**Si NO aparecen estos logs:**
- ❌ El código no se está ejecutando
- ❌ Hay un error que no se está mostrando
- ❌ El `banco_id` no se está pasando correctamente

## 🔧 Pasos de Diagnóstico

### Paso 1: Verificar que se crean los movimientos

1. **Crear un pago de compra con `banco_id`:**
   ```bash
   POST /compras/{compra_id}/pagos
   {
     "monto": 500.00,
     "fecha_pago": "2024-11-30",
     "metodo_pago": "transferencia",
     "banco_id": "507f1f77bcf86cd799439011",
     "referencia": "TRF-123456"
   }
   ```

2. **Revisar los logs del backend:**
   - Buscar `[CREAR-PAGO-COMPRA] ✅ Movimiento creado exitosamente!`
   - Si no aparece, el movimiento no se está creando

3. **Verificar en MongoDB:**
   ```javascript
   db.movimientos_bancos.find({ compra_id: "compra_id" }).pretty()
   ```

### Paso 2: Verificar el formato de banco_id

**Problema común:** `banco_id` guardado como string en lugar de ObjectId

**Verificar en MongoDB:**
```javascript
// Ver el tipo de banco_id en los movimientos
db.movimientos_bancos.find({ tipo: "pago_compra" }).forEach(function(doc) {
    if (typeof doc.banco_id === "string") {
        print("⚠️ PROBLEMA: banco_id es string: " + doc.banco_id);
    } else {
        print("✅ banco_id es ObjectId: " + doc.banco_id);
    }
})
```

**Solución:**
- Asegurarse de que en el código se use `banco_oid` (ObjectId) y no `banco_id` (string)

### Paso 3: Verificar la consulta en GET /bancos/{banco_id}/movimientos

1. **Consultar movimientos:**
   ```bash
   GET /bancos/{banco_id}/movimientos
   ```

2. **Revisar los logs:**
   ```
   [OBTENER-MOVIMIENTOS-BANCO] 📊 Movimientos por tipo: {...}
   ```

3. **Verificar en la respuesta:**
   - ¿Aparecen movimientos de tipo `"pago_compra"`?
   - ¿El total de movimientos coincide con lo esperado?

### Paso 4: Verificar la consulta en MongoDB directamente

**Consulta que debe funcionar:**
```javascript
// Obtener el banco_id como ObjectId
var banco_id = "507f1f77bcf86cd799439011";
var banco_oid = ObjectId(banco_id);

// Buscar movimientos (debe encontrar los de tipo "pago_compra")
db.movimientos_bancos.find({
    $or: [
        { banco_id: banco_id },   // String
        { banco_id: banco_oid }   // ObjectId
    ]
}).pretty()
```

**Si esta consulta NO encuentra los movimientos:**
- El `banco_id` en los movimientos no coincide con el del banco
- Hay un problema con el formato del `banco_id`

## ⚠️ Problemas Comunes y Soluciones

### Problema 1: Movimientos no se crean

**Síntomas:**
- No aparecen logs de `✅ Movimiento creado exitosamente!`
- No hay movimientos en MongoDB

**Causas posibles:**
1. El código no se está ejecutando (el `if banco_id:` no se cumple)
2. Hay un error que no se está mostrando
3. El `banco_id` no se está pasando en el request

**Solución:**
- Agregar más logging antes de crear el movimiento
- Verificar que el `banco_id` se esté recibiendo correctamente
- Revisar si hay excepciones que se están silenciando

### Problema 2: Movimientos se crean pero no aparecen en GET

**Síntomas:**
- Los movimientos existen en MongoDB
- No aparecen en `GET /bancos/{banco_id}/movimientos`

**Causas posibles:**
1. `banco_id` guardado como string pero se busca como ObjectId (o viceversa)
2. El query filtra por tipo
3. El `banco_id` en el movimiento no coincide con el del banco

**Solución:**
- Verificar el formato de `banco_id` en MongoDB
- Asegurarse de que el query busque tanto por string como por ObjectId
- Verificar que el query NO filtre por tipo

### Problema 3: banco_id como string en lugar de ObjectId

**Síntomas:**
- Los movimientos se crean
- El `banco_id` en MongoDB es string
- No se encuentran en la consulta

**Solución:**
```python
# ❌ INCORRECTO
movimiento = {
    "banco_id": banco_id,  # String
}

# ✅ CORRECTO
movimiento = {
    "banco_id": banco_oid,  # ObjectId
}
```

## 📋 Checklist de Verificación

- [ ] Verificar en MongoDB que existen movimientos de tipo `"pago_compra"`
- [ ] Verificar que el `banco_id` en los movimientos es ObjectId (no string)
- [ ] Verificar que el código de creación del movimiento esté presente
- [ ] Verificar que los logs muestran `✅ Movimiento creado exitosamente!`
- [ ] Verificar que el query en `GET /bancos/{banco_id}/movimientos` NO filtra por tipo
- [ ] Verificar que el query busca tanto por string como por ObjectId
- [ ] Verificar que los logs muestran los movimientos encontrados por tipo
- [ ] Verificar que los movimientos de tipo `"pago_compra"` aparecen en la respuesta

## 🚀 Próximos Pasos

1. **Compartir este documento con el desarrollador del backend**
2. **Pedirle que ejecute las verificaciones en MongoDB:**
   ```javascript
   db.movimientos_bancos.find({ tipo: "pago_compra" }).pretty()
   ```
3. **Revisar los logs del backend al crear un pago de compra:**
   - Buscar `✅ Movimiento creado exitosamente!`
4. **Verificar que el endpoint `GET /bancos/{banco_id}/movimientos` devuelva todos los tipos de movimientos:**
   - Revisar los logs: `📊 Movimientos por tipo: {...}`
   - Verificar que incluye `'pago_compra': X`

## 📝 Nota Importante

**El frontend está listo y funcionando.** El problema está en el backend:
- Los movimientos no se están creando, O
- Los movimientos no se están devolviendo correctamente

Una vez que el backend verifique y corrija estos puntos, los movimientos de tipo `"pago_compra"` aparecerán automáticamente en el historial del banco.

