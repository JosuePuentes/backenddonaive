# Instrucciones: Campo Cliente en Facturas Procesadas

## Puntos Clave

1. **El campo `cliente` debe ser un objeto, no un string (ID)**
2. **Estructura requerida del objeto cliente:**
   ```json
   {
     "_id": "string",
     "nombre": "string", 
     "cedula": "string"
   }
   ```
3. **Si no hay cliente, enviar `cliente: null`**
4. **Siempre hacer lookup del cliente desde la colección `CLIENTES`**
5. **Aplicar esta lógica en todos los endpoints que devuelven ventas/facturas**

## Implementación

### Schema (Pydantic)

Se ha creado el schema `ClienteVentaResponse` en `app/schemas/punto_venta.py`:

```python
class ClienteVentaResponse(BaseModel):
    """Modelo simplificado de cliente para respuestas de ventas"""
    _id: str
    nombre: str
    cedula: str
```

Y se actualizó `VentaResponse` para usar este schema:

```python
class VentaResponse(BaseModel):
    # ... otros campos ...
    cliente: Optional[ClienteVentaResponse] = None  # Objeto cliente o null
```

### Funciones Helper

Se han creado dos funciones helper en `app/routes/punto_venta.py`:

#### 1. `obtener_cliente_venta(cliente_id: Optional[str]) -> Optional[ClienteVentaResponse]`

Obtiene un cliente desde la colección `CLIENTES` por su ID. Retorna un objeto `ClienteVentaResponse` o `None` si no existe.

```python
async def obtener_cliente_venta(cliente_id: Optional[str]) -> Optional[ClienteVentaResponse]:
    """
    Función helper para obtener un cliente desde la colección CLIENTES.
    Retorna un objeto ClienteVentaResponse con _id, nombre y cedula, o None si no existe.
    """
    if not cliente_id:
        return None
    
    try:
        clientes_collection = get_collection("CLIENTES")
        
        # Intentar buscar por ObjectId
        try:
            cliente_doc = await clientes_collection.find_one({"_id": ObjectId(cliente_id)})
            if cliente_doc:
                return ClienteVentaResponse(
                    _id=str(cliente_doc["_id"]),
                    nombre=cliente_doc.get("nombre", ""),
                    cedula=cliente_doc.get("cedula", "")
                )
        except (InvalidId, ValueError):
            # Si no es ObjectId válido, buscar por string
            try:
                cliente_doc = await clientes_collection.find_one({"_id": cliente_id})
                if cliente_doc:
                    return ClienteVentaResponse(
                        _id=str(cliente_doc["_id"]),
                        nombre=cliente_doc.get("nombre", ""),
                        cedula=cliente_doc.get("cedula", "")
                    )
            except Exception as e:
                print(f"[OBTENER-CLIENTE-VENTA] Error al buscar cliente por string {cliente_id}: {str(e)}")
    except Exception as e:
        print(f"[OBTENER-CLIENTE-VENTA] Error al obtener cliente {cliente_id}: {str(e)}")
    
    return None
```

#### 2. `procesar_cliente_en_venta(venta: dict) -> dict`

Procesa el campo `cliente` en una venta, haciendo lookup si es necesario y asegurando la estructura correcta.

```python
async def procesar_cliente_en_venta(venta: dict) -> dict:
    """
    Función helper para procesar el campo cliente en una venta.
    Hace lookup del cliente desde la colección CLIENTES y retorna la venta con cliente procesado.
    Si no hay cliente, establece cliente: None.
    """
    cliente_id = venta.get("cliente")
    if cliente_id:
        # Si cliente es un string (ID), hacer lookup
        if isinstance(cliente_id, str):
            cliente_obj = await obtener_cliente_venta(cliente_id)
            venta["cliente"] = cliente_obj.dict() if cliente_obj else None
        # Si cliente es un dict/objeto, verificar que tenga la estructura correcta
        elif isinstance(cliente_id, dict):
            # Si ya tiene _id, nombre y cedula, mantenerlo
            if all(key in cliente_id for key in ["_id", "nombre", "cedula"]):
                venta["cliente"] = {
                    "_id": str(cliente_id["_id"]),
                    "nombre": cliente_id.get("nombre", ""),
                    "cedula": cliente_id.get("cedula", "")
                }
            else:
                # Si es un objeto pero no tiene la estructura correcta, intentar lookup por _id
                cliente_obj_id = str(cliente_id.get("_id", ""))
                if cliente_obj_id:
                    cliente_obj = await obtener_cliente_venta(cliente_obj_id)
                    venta["cliente"] = cliente_obj.dict() if cliente_obj else None
                else:
                    venta["cliente"] = None
        else:
            venta["cliente"] = None
    else:
        # Si no hay cliente, enviar null
        venta["cliente"] = None
    
    return venta
```

### Endpoints Actualizados

Los siguientes endpoints han sido actualizados para usar estas funciones helper:

1. **`GET /punto-venta/ventas/usuario`** - Obtiene ventas con filtros opcionales
2. **`GET /punto-venta/ventas`** - Obtiene ventas del día
3. **`POST /punto-venta/ventas`** - Registra una nueva venta
4. **`POST /punto-venta/devolucion`** - Procesa una devolución

### Ejemplo de Uso en un Endpoint

```python
@router.get("/ventas/usuario", response_model=VentasUsuarioResponse)
async def obtener_ventas_usuario(...):
    # ... código para obtener ventas ...
    
    facturas = []
    for venta in ventas:
        venta["_id"] = str(venta["_id"])
        
        # Procesar cliente antes de agregar
        venta = await procesar_cliente_en_venta(venta)
        
        facturas.append(VentaResponse(**venta))
    
    return VentasUsuarioResponse(facturas=facturas, ...)
```

## Ejemplo de Respuesta

### Con Cliente

```json
{
  "numero_factura": "FAC-20240101-0001",
  "fecha": "2024-01-01",
  "items": [...],
  "metodos_pago": [...],
  "total_bs": 100.00,
  "sucursal": "sucursal_id",
  "cliente": {
    "_id": "507f1f77bcf86cd799439011",
    "nombre": "Juan Pérez",
    "cedula": "12345678"
  },
  "_id": "venta_id"
}
```

### Sin Cliente

```json
{
  "numero_factura": "FAC-20240101-0001",
  "fecha": "2024-01-01",
  "items": [...],
  "metodos_pago": [...],
  "total_bs": 100.00,
  "sucursal": "sucursal_id",
  "cliente": null,
  "_id": "venta_id"
}
```

## Notas Importantes

1. **Siempre hacer lookup**: Aunque el cliente pueda estar almacenado como objeto en la base de datos, siempre se debe hacer lookup desde la colección `CLIENTES` para asegurar que los datos estén actualizados.

2. **Manejo de errores**: Si el cliente no se encuentra o hay un error al buscarlo, se debe establecer `cliente: null` en lugar de fallar la respuesta.

3. **Compatibilidad**: El código maneja tanto clientes almacenados como string (ID) como objetos, asegurando compatibilidad con datos existentes.

4. **Rendimiento**: Para endpoints que devuelven múltiples ventas, se hacen lookups individuales. Si el rendimiento es un problema, se puede optimizar usando agregaciones de MongoDB con `$lookup`.

## Verificación

Para verificar que los cambios funcionan correctamente:

1. Hacer una petición a cualquier endpoint que devuelva ventas
2. Verificar que el campo `cliente` sea un objeto con `_id`, `nombre` y `cedula`, o `null`
3. Verificar que los datos del cliente coincidan con los de la colección `CLIENTES`

