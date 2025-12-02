# Instrucciones Backend - Verificación de Pagos de Compras y Movimientos Bancarios

## ✅ Acción Requerida del Backend

El backend debe verificar que la implementación cumpla con los siguientes requisitos:

### 1. Creación de Movimiento en `POST /compras/{compra_id}/pagos`

**Ubicación:** `app/routes/compras.py` (función `crear_pago_compra`)

**Requisitos:**

1. **`banco_id` debe guardarse como ObjectId:**
   ```python
   from bson import ObjectId
   from bson.errors import InvalidId
   
   # Convertir banco_id a ObjectId
   try:
       banco_oid = ObjectId(banco_id)
   except InvalidId:
       raise HTTPException(status_code=400, detail="ID de banco inválido")
   
   # En el movimiento, usar banco_oid (ObjectId), NO banco_id (string)
   movimiento = {
       "banco_id": banco_oid,  # ✅ ObjectId
       # NO usar: "banco_id": banco_id  # ❌ String
   }
   ```

2. **`monto` debe ser negativo usando `abs()`:**
   ```python
   movimiento = {
       "monto": -abs(monto),  # ✅ Asegura que siempre sea negativo
       # NO usar: "monto": -monto  # ❌ Puede ser positivo si monto es negativo
   }
   ```

3. **`tipo` debe ser `"pago_compra"`:**
   ```python
   movimiento = {
       "tipo": "pago_compra",  # ✅ Tipo correcto
   }
   ```

**Código completo del movimiento:**
```python
movimiento = {
    "banco_id": banco_oid,  # ObjectId, NO string
    "tipo": "pago_compra",
    "monto": -abs(monto),  # Negativo usando abs()
    "divisa": divisa_banco,
    "compra_id": compra_id,
    "pago_id": None,  # Se actualizará después de crear el pago
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
```

### 2. Consulta de Movimientos en `GET /bancos/{banco_id}/movimientos`

**Ubicación:** `app/main.py` (función `obtener_movimientos_banco`)

**Requisitos:**

1. **NO filtrar por tipo:**
   ```python
   # ✅ CORRECTO: Buscar solo por banco_id (sin filtro de tipo)
   query = {
       "$or": [
           {"banco_id": banco_id},  # String (para compatibilidad)
           {"banco_id": banco_oid}   # ObjectId (formato correcto)
       ]
   }
   movimientos_docs = await movimientos_collection.find(query).sort("fecha", -1).to_list(length=None)
   
   # ❌ INCORRECTO: No filtrar por tipo
   # query = {"banco_id": banco_id, "tipo": "pago_compra"}  # ❌ Esto excluiría otros tipos
   ```

2. **Buscar tanto por string como por ObjectId:**
   ```python
   from bson import ObjectId
   from bson.errors import InvalidId
   
   try:
       banco_oid = ObjectId(banco_id)
   except InvalidId:
       raise HTTPException(status_code=400, detail="ID de banco inválido")
   
   # Buscar movimientos: puede estar guardado como string o como ObjectId
   query = {
       "$or": [
           {"banco_id": banco_id},  # String (para compatibilidad con datos antiguos)
           {"banco_id": banco_oid}   # ObjectId (formato correcto)
       ]
   }
   ```

3. **Incluir logging para diagnóstico:**
   ```python
   # Contar movimientos por tipo para diagnóstico
   tipos_encontrados = {}
   for mov in movimientos_docs:
       mov["_id"] = str(mov["_id"])
       tipo_mov = mov.get("tipo", "sin_tipo")
       tipos_encontrados[tipo_mov] = tipos_encontrados.get(tipo_mov, 0) + 1
       movimientos.append(mov)
   
   print(f"[OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados {len(movimientos_docs)} movimientos en MOVIMIENTOS_BANCOS")
   print(f"[OBTENER-MOVIMIENTOS-BANCO] 📊 Movimientos por tipo: {tipos_encontrados}")
   
   # Verificar específicamente movimientos de tipo "pago_compra"
   pagos_compra_count = tipos_encontrados.get("pago_compra", 0)
   if pagos_compra_count > 0:
       print(f"[OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados {pagos_compra_count} movimientos de tipo 'pago_compra'")
   else:
       print(f"[OBTENER-MOVIMIENTOS-BANCO] ⚠️ No se encontraron movimientos de tipo 'pago_compra'")
   ```

## 🔍 Verificación

### Verificar Creación de Movimiento

1. **Crear un pago de compra con `banco_id`:**
   ```bash
   POST /compras/{compra_id}/pagos
   {
     "monto": 500.00,
     "fecha_pago": "2024-11-30",
     "metodo_pago": "transferencia",
     "banco_id": "507f1f77bcf86cd799439011"
   }
   ```

2. **Verificar en MongoDB:**
   ```javascript
   // Conectar a MongoDB y verificar el movimiento
   db.MOVIMIENTOS_BANCOS.findOne({
     "compra_id": "compra_id",
     "tipo": "pago_compra"
   })
   
   // Verificar que:
   // - banco_id es ObjectId (no string)
   // - monto es negativo
   // - tipo es "pago_compra"
   ```

3. **Verificar en los logs del backend:**
   ```
   [CREAR-PAGO-COMPRA] Movimiento creado en banco: {movimiento_id} para banco {banco_id}
   ```

### Verificar Consulta de Movimientos

1. **Consultar movimientos del banco:**
   ```bash
   GET /bancos/{banco_id}/movimientos
   ```

2. **Verificar en los logs del backend:**
   ```
   [OBTENER-MOVIMIENTOS-BANCO] Buscando movimientos para banco: {banco_id}
   [OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados X movimientos en MOVIMIENTOS_BANCOS
   [OBTENER-MOVIMIENTOS-BANCO] 📊 Movimientos por tipo: {'pago_compra': 2, 'venta': 5, 'vuelto': 1}
   [OBTENER-MOVIMIENTOS-BANCO] ✅ Encontrados 2 movimientos de tipo 'pago_compra'
   ```

3. **Verificar en la respuesta:**
   ```json
   {
     "banco_id": "banco_id",
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
         "descripcion": "Pago Compra - Proveedor ABC (Factura FAC-001) - Ref: TRF-123",
         "fecha": "2024-11-30T12:00:00"
       }
     ],
     "total": 1
   }
   ```

## ⚠️ Problemas Comunes

### Problema 1: Movimientos no aparecen en GET /bancos/{banco_id}/movimientos

**Causa:** `banco_id` guardado como string en lugar de ObjectId

**Solución:**
```python
# En POST /compras/{compra_id}/pagos
movimiento = {
    "banco_id": banco_oid,  # ✅ ObjectId
    # NO: "banco_id": banco_id  # ❌ String
}
```

### Problema 2: Movimientos filtrados por tipo

**Causa:** La consulta filtra por tipo

**Solución:**
```python
# En GET /bancos/{banco_id}/movimientos
query = {
    "$or": [
        {"banco_id": banco_id},
        {"banco_id": banco_oid}
    ]
}
# NO agregar: "tipo": "pago_compra"  # ❌ Esto excluiría otros tipos
```

### Problema 3: Monto positivo en lugar de negativo

**Causa:** No se usa `abs()` para asegurar que sea negativo

**Solución:**
```python
movimiento = {
    "monto": -abs(monto),  # ✅ Siempre negativo
    # NO: "monto": -monto  # ❌ Puede ser positivo si monto es negativo
}
```

## 📋 Checklist de Verificación

- [ ] `banco_id` se guarda como ObjectId en el movimiento
- [ ] `monto` se guarda como `-abs(monto)` (siempre negativo)
- [ ] `tipo` es `"pago_compra"`
- [ ] `GET /bancos/{banco_id}/movimientos` NO filtra por tipo
- [ ] `GET /bancos/{banco_id}/movimientos` busca tanto por string como por ObjectId
- [ ] Los logs muestran los movimientos encontrados por tipo
- [ ] Los movimientos de tipo `"pago_compra"` aparecen en la respuesta

## 🚀 Estado

✅ **Implementación completada y desplegada**

Los cambios ya están en el repositorio:
- `POST /compras/{compra_id}/pagos` guarda `banco_id` como ObjectId y `monto` como `-abs(monto)`
- `GET /bancos/{banco_id}/movimientos` devuelve todos los movimientos sin filtrar por tipo
- Logging detallado para diagnóstico

**Comparte estas instrucciones con el desarrollador del backend para que verifique la implementación.**

