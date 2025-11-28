from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongo import get_collection
from app.core.get_current_user import get_current_user
from app.schemas.compras import (
    ProveedorCreate, 
    ProveedorResponse, 
    CompraCreate, 
    CompraResponse
)
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime

router = APIRouter()


def verificar_permiso(usuario: dict, permiso: str):
    """Verifica si el usuario tiene un permiso específico"""
    permisos = usuario.get("permisos", [])
    if permiso not in permisos and "admin_completo" not in permisos:
        raise HTTPException(
            status_code=403,
            detail=f"No tienes permisos para realizar esta acción. Se requiere: {permiso}"
        )


@router.get("/proveedores", response_model=List[ProveedorResponse])
async def listar_proveedores(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros a devolver"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (activo, inactivo)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Listar todos los proveedores con paginación.
    Requiere autenticación.
    """
    try:
        proveedores_collection = get_collection("PROVEEDORES")
        
        # Construir query de filtrado
        query = {}
        if estado:
            query["estado"] = estado
        else:
            # Por defecto, solo mostrar activos
            query["estado"] = {"$ne": "inactivo"}
        
        # Obtener proveedores con paginación
        proveedores = await proveedores_collection.find(query).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
        
        # Formatear resultados
        resultado = []
        for proveedor in proveedores:
            proveedor["_id"] = str(proveedor["_id"])
            
            # Normalizar campos numéricos: si vienen como None o undefined, asignar 0
            proveedor["dias_credito"] = proveedor.get("dias_credito") if proveedor.get("dias_credito") is not None else 0
            proveedor["descuento_comercial"] = proveedor.get("descuento_comercial") if proveedor.get("descuento_comercial") is not None else 0.0
            proveedor["descuento_pronto_pago"] = proveedor.get("descuento_pronto_pago") if proveedor.get("descuento_pronto_pago") is not None else 0.0
            
            if proveedor.get("fecha_creacion"):
                if isinstance(proveedor["fecha_creacion"], datetime):
                    proveedor["fecha_creacion"] = proveedor["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
            if proveedor.get("fecha_actualizacion"):
                if isinstance(proveedor["fecha_actualizacion"], datetime):
                    proveedor["fecha_actualizacion"] = proveedor["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
            
            resultado.append(ProveedorResponse(**proveedor))
        
        print(f"[LISTAR-PROVEEDORES] Proveedores cargados: {len(resultado)} proveedores")
        
        return resultado
        
    except Exception as e:
        print(f"[LISTAR-PROVEEDORES] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar proveedores: {str(e)}"
        )


@router.post("/proveedores", response_model=ProveedorResponse, status_code=201)
async def crear_proveedor(
    proveedor: ProveedorCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Crear un nuevo proveedor.
    Requiere autenticación.
    """
    try:
        proveedores_collection = get_collection("PROVEEDORES")
        
        # Validar que el nombre no esté vacío
        nombre = proveedor.nombre.strip()
        if not nombre:
            raise HTTPException(
                status_code=400,
                detail="El nombre del proveedor es requerido"
            )
        
        # Verificar que no exista un proveedor con el mismo nombre
        proveedor_existente = await proveedores_collection.find_one({
            "nombre": {"$regex": f"^{nombre}$", "$options": "i"}  # Case insensitive
        })
        
        if proveedor_existente:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un proveedor con el nombre {nombre}"
            )
        
        # Validar formato de email si se proporciona
        if proveedor.email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, proveedor.email):
                raise HTTPException(
                    status_code=400,
                    detail="El formato del email no es válido"
                )
        
        # Crear documento del proveedor
        proveedor_dict = proveedor.dict()
        
        # Normalizar campos numéricos: si vienen como None o undefined, asignar 0
        proveedor_dict["dias_credito"] = proveedor_dict.get("dias_credito") if proveedor_dict.get("dias_credito") is not None else 0
        proveedor_dict["descuento_comercial"] = proveedor_dict.get("descuento_comercial") if proveedor_dict.get("descuento_comercial") is not None else 0.0
        proveedor_dict["descuento_pronto_pago"] = proveedor_dict.get("descuento_pronto_pago") if proveedor_dict.get("descuento_pronto_pago") is not None else 0.0
        
        proveedor_dict["fecha_creacion"] = datetime.now()
        proveedor_dict["fecha_actualizacion"] = datetime.now()
        proveedor_dict["estado"] = "activo"
        proveedor_dict["usuario_creacion"] = usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
        
        print(f"[CREAR-PROVEEDOR] Datos del proveedor a guardar: {proveedor_dict}")
        
        # Insertar proveedor
        result = await proveedores_collection.insert_one(proveedor_dict)
        proveedor_id = str(result.inserted_id)
        
        # Obtener el proveedor creado
        proveedor_creado = await proveedores_collection.find_one({"_id": ObjectId(proveedor_id)})
        proveedor_creado["_id"] = str(proveedor_creado["_id"])
        
        # Normalizar campos numéricos en la respuesta
        proveedor_creado["dias_credito"] = proveedor_creado.get("dias_credito") if proveedor_creado.get("dias_credito") is not None else 0
        proveedor_creado["descuento_comercial"] = proveedor_creado.get("descuento_comercial") if proveedor_creado.get("descuento_comercial") is not None else 0.0
        proveedor_creado["descuento_pronto_pago"] = proveedor_creado.get("descuento_pronto_pago") if proveedor_creado.get("descuento_pronto_pago") is not None else 0.0
        
        if proveedor_creado.get("fecha_creacion"):
            if isinstance(proveedor_creado["fecha_creacion"], datetime):
                proveedor_creado["fecha_creacion"] = proveedor_creado["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if proveedor_creado.get("fecha_actualizacion"):
            if isinstance(proveedor_creado["fecha_actualizacion"], datetime):
                proveedor_creado["fecha_actualizacion"] = proveedor_creado["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"[CREAR-PROVEEDOR] Proveedor creado exitosamente: {proveedor_creado}")
        return ProveedorResponse(**proveedor_creado)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREAR-PROVEEDOR] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear proveedor: {str(e)}"
        )


@router.put("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
@router.patch("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
async def actualizar_proveedor(
    proveedor_id: str,
    proveedor_data: ProveedorCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Actualizar un proveedor existente.
    Requiere autenticación.
    """
    try:
        proveedores_collection = get_collection("PROVEEDORES")
        
        # Intentar convertir a ObjectId
        try:
            oid = ObjectId(proveedor_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de proveedor inválido"
            )
        
        # Verificar que el proveedor existe
        proveedor_existente = await proveedores_collection.find_one({"_id": oid})
        if not proveedor_existente:
            raise HTTPException(
                status_code=404,
                detail="Proveedor no encontrado"
            )
        
        # Validar que el nombre no esté vacío
        nombre = proveedor_data.nombre.strip()
        if not nombre:
            raise HTTPException(
                status_code=400,
                detail="El nombre del proveedor es requerido"
            )
        
        # Validar que el nombre no esté duplicado (si se está cambiando)
        if nombre.lower() != proveedor_existente.get("nombre", "").lower():
            proveedor_con_nombre = await proveedores_collection.find_one({
                "nombre": {"$regex": f"^{nombre}$", "$options": "i"},
                "_id": {"$ne": oid}  # Excluir el proveedor actual
            })
            if proveedor_con_nombre:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe otro proveedor con el nombre {nombre}"
                )
        
        # Validar formato de email si se proporciona
        if proveedor_data.email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, proveedor_data.email):
                raise HTTPException(
                    status_code=400,
                    detail="El formato del email no es válido"
                )
        
        # Preparar datos de actualización
        update_data = {
            "nombre": nombre,
            "rif": proveedor_data.rif,
            "telefono": proveedor_data.telefono,
            "email": proveedor_data.email,
            "direccion": proveedor_data.direccion,
            "contacto": proveedor_data.contacto,
            "notas": proveedor_data.notas,
            "fecha_actualizacion": datetime.now(),
            "usuario_actualizacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
        }
        
        # Normalizar campos numéricos: si vienen como None o undefined, asignar 0
        update_data["dias_credito"] = proveedor_data.dias_credito if proveedor_data.dias_credito is not None else 0
        update_data["descuento_comercial"] = proveedor_data.descuento_comercial if proveedor_data.descuento_comercial is not None else 0.0
        update_data["descuento_pronto_pago"] = proveedor_data.descuento_pronto_pago if proveedor_data.descuento_pronto_pago is not None else 0.0
        
        # Remover campos None para no sobrescribir con None (excepto los numéricos que ya normalizamos)
        update_data = {k: v for k, v in update_data.items() if v is not None or k in ["dias_credito", "descuento_comercial", "descuento_pronto_pago"]}
        
        print(f"[ACTUALIZAR-PROVEEDOR] Datos del proveedor a actualizar: {update_data}")
        
        # Actualizar proveedor
        result = await proveedores_collection.update_one(
            {"_id": oid},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Proveedor no encontrado"
            )
        
        # Obtener el proveedor actualizado
        proveedor_actualizado = await proveedores_collection.find_one({"_id": oid})
        proveedor_actualizado["_id"] = str(proveedor_actualizado["_id"])
        
        # Normalizar campos numéricos en la respuesta
        proveedor_actualizado["dias_credito"] = proveedor_actualizado.get("dias_credito") if proveedor_actualizado.get("dias_credito") is not None else 0
        proveedor_actualizado["descuento_comercial"] = proveedor_actualizado.get("descuento_comercial") if proveedor_actualizado.get("descuento_comercial") is not None else 0.0
        proveedor_actualizado["descuento_pronto_pago"] = proveedor_actualizado.get("descuento_pronto_pago") if proveedor_actualizado.get("descuento_pronto_pago") is not None else 0.0
        
        if proveedor_actualizado.get("fecha_creacion"):
            if isinstance(proveedor_actualizado["fecha_creacion"], datetime):
                proveedor_actualizado["fecha_creacion"] = proveedor_actualizado["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if proveedor_actualizado.get("fecha_actualizacion"):
            if isinstance(proveedor_actualizado["fecha_actualizacion"], datetime):
                proveedor_actualizado["fecha_actualizacion"] = proveedor_actualizado["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"[ACTUALIZAR-PROVEEDOR] Proveedor actualizado exitosamente: {proveedor_actualizado}")
        return ProveedorResponse(**proveedor_actualizado)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ACTUALIZAR-PROVEEDOR] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar proveedor: {str(e)}"
        )


@router.get("/productos")
async def buscar_productos_compra(
    search: str = Query(..., description="Query de búsqueda (nombre o código)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Buscar productos por nombre o código para el módulo de compras.
    Requiere permiso: compras
    """
    verificar_permiso(usuario, "compras")
    
    search = search.strip() if search else ""
    if len(search) < 2:
        return []
    
    try:
        productos_collection = get_collection("PRODUCTOS")
        
        # Intentar usar PRODUCTOS, si no existe usar INVENTARIOS
        try:
            await productos_collection.find_one({})
        except:
            productos_collection = get_collection("INVENTARIOS")
        
        # Búsqueda exacta por código primero
        query_exacta = {
            "codigo": search,
            "estado": "activo"
        }
        
        productos_exactos = await productos_collection.find(query_exacta).limit(10).to_list(length=10)
        
        if productos_exactos:
            resultado = []
            for producto in productos_exactos:
                producto["_id"] = str(producto["_id"])
                resultado.append(producto)
            return resultado
        
        # Si no hay coincidencias exactas, buscar por nombre
        query_nombre = {
            "nombre": {"$regex": search, "$options": "i"},
            "estado": "activo"
        }
        
        productos = await productos_collection.find(query_nombre).limit(20).to_list(length=20)
        
        resultado = []
        for producto in productos:
            producto["_id"] = str(producto["_id"])
            resultado.append(producto)
        
        return resultado
        
    except Exception as e:
        print(f"[BUSCAR-PRODUCTOS-COMPRA] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar productos: {str(e)}"
        )


@router.post("/compras", response_model=CompraResponse, status_code=201)
async def crear_compra(
    compra: CompraCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Crear una nueva compra y actualizar el inventario.
    
    La compra:
    1. Valida permisos (requiere permiso 'compras')
    2. Valida que el proveedor exista
    3. Crea un registro de compra en la colección COMPRAS
    4. Busca o crea un inventario activo para la farmacia/sucursal
    5. Para cada item:
       - Si el producto existe en el inventario, actualiza cantidad y costo
       - Si el producto tiene lotes existentes, agrega el nuevo lote a los existentes
       - Si el producto no existe, crea un nuevo item
    6. Crea o actualiza productos en la colección PRODUCTOS
    7. Actualiza el costo total del inventario
    
    Requiere permiso: compras
    """
    # Validar permisos
    verificar_permiso(usuario, "compras")
    
    try:
        # Validar que el proveedor existe
        proveedores_collection = get_collection("PROVEEDORES")
        try:
            proveedor_oid = ObjectId(compra.proveedor_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de proveedor inválido"
            )
        
        proveedor = await proveedores_collection.find_one({"_id": proveedor_oid})
        if not proveedor:
            raise HTTPException(
                status_code=404,
                detail="Proveedor no encontrado"
            )
        
        proveedor_nombre = proveedor.get("nombre", "Proveedor desconocido")
        
        # Validar que la compra tenga items
        if not compra.items or len(compra.items) == 0:
            raise HTTPException(
                status_code=400,
                detail="La compra debe tener al menos un item"
            )
        
        # Validar tasa si la divisa es BS
        if compra.divisa == "BS" and (not compra.tasa or compra.tasa <= 0):
            raise HTTPException(
                status_code=400,
                detail="La tasa de cambio es requerida cuando la divisa es BS"
            )
        
        # Crear registro de compra
        compras_collection = get_collection("COMPRAS")
        compra_dict = compra.dict()
        compra_dict["proveedor_nombre"] = proveedor_nombre
        compra_dict["usuario_creacion"] = usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
        compra_dict["fecha_creacion"] = datetime.now().isoformat()
        compra_dict["estado"] = "activa"
        
        # Convertir items a dict para guardar
        items_dict = []
        for item in compra.items:
            item_dict = item.dict()
            items_dict.append(item_dict)
        compra_dict["items"] = items_dict
        
        # Insertar compra
        result_compra = await compras_collection.insert_one(compra_dict)
        compra_id = str(result_compra.inserted_id)
        
        print(f"[CREAR-COMPRA] Compra creada con ID: {compra_id}")
        
        # Buscar o crear inventario activo para la farmacia/sucursal
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Construir query para buscar inventario activo
        query_inventario = {
            "farmacia": compra.farmacia,
            "estado": "activo"
        }
        if compra.sucursal:
            query_inventario["sucursal"] = compra.sucursal
        
        # Buscar inventario activo más reciente
        inventario_existente = await inventarios_collection.find_one(
            query_inventario,
            sort=[("fecha_creacion", -1)]
        )
        
        inventario_id = None
        items_inventario = []
        costo_total_inventario = 0.0
        
        if inventario_existente:
            inventario_id = str(inventario_existente["_id"])
            items_inventario = inventario_existente.get("items", [])
            costo_total_inventario = inventario_existente.get("costo", 0.0)
            print(f"[CREAR-COMPRA] Inventario existente encontrado: {inventario_id}")
        else:
            # Crear nuevo inventario
            inventario_nuevo = {
                "farmacia": compra.farmacia,
                "sucursal": compra.sucursal,
                "costo": 0.0,
                "usuarioCorreo": usuario.get("correo", usuario.get("usuarioCorreo", "unknown")),
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "estado": "activo",
                "items": [],
                "fecha_creacion": datetime.now()
            }
            
            result_inventario = await inventarios_collection.insert_one(inventario_nuevo)
            inventario_id = str(result_inventario.inserted_id)
            print(f"[CREAR-COMPRA] Nuevo inventario creado: {inventario_id}")
        
        # Procesar items de la compra y actualizar/agregar al inventario
        productos_collection = get_collection("PRODUCTOS")
        nuevos_items = []
        productos_actualizados = []
        costo_total_compra = 0.0
        
        for item_compra in compra.items:
            # Calcular costo del item
            costo_item = item_compra.costo_unitario * item_compra.cantidad
            costo_total_compra += costo_item
            
            # Buscar si el producto ya existe en el inventario (por código)
            item_existente_idx = None
            item_existente = None
            for idx, item in enumerate(items_inventario):
                if item.get("codigo") == item_compra.codigo:
                    item_existente_idx = idx
                    item_existente = item
                    break
            
            if item_existente:
                # Producto existe: actualizar cantidad y costo
                print(f"[CREAR-COMPRA] Producto existente encontrado: {item_compra.codigo}, actualizando...")
                
                # Calcular nuevo costo unitario promedio (promedio ponderado)
                cantidad_anterior = item_existente.get("cantidad", 0)
                costo_anterior = item_existente.get("costo", 0)
                costo_unitario_anterior = item_existente.get("costo_unitario", 0)
                
                cantidad_total = cantidad_anterior + item_compra.cantidad
                costo_total_nuevo = costo_anterior + costo_item
                costo_unitario_promedio = costo_total_nuevo / cantidad_total if cantidad_total > 0 else item_compra.costo_unitario
                
                # Actualizar item existente
                items_inventario[item_existente_idx]["cantidad"] = cantidad_total
                items_inventario[item_existente_idx]["costo"] = costo_total_nuevo
                items_inventario[item_existente_idx]["costo_unitario"] = costo_unitario_promedio
                
                # Actualizar precio unitario si se proporciona uno nuevo
                if item_compra.precio_unitario:
                    items_inventario[item_existente_idx]["precio_unitario"] = item_compra.precio_unitario
                
                precio_unitario_final = items_inventario[item_existente_idx].get("precio_unitario", costo_unitario_promedio)
                items_inventario[item_existente_idx]["precio"] = precio_unitario_final * cantidad_total
                items_inventario[item_existente_idx]["utilidad_contable"] = (
                    precio_unitario_final - costo_unitario_promedio
                ) * cantidad_total if precio_unitario_final > 0 else 0
                
                # Manejar lotes: agregar a lotes existentes o crear nuevo array
                if item_compra.lote or item_compra.fecha_vencimiento:
                    lotes_existentes = items_inventario[item_existente_idx].get("lotes", [])
                    if not isinstance(lotes_existentes, list):
                        lotes_existentes = []
                    
                    nuevo_lote = {
                        "numero_lote": item_compra.lote or f"LOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "fecha_vencimiento": item_compra.fecha_vencimiento,
                        "cantidad": item_compra.cantidad,
                        "costo_unitario": item_compra.costo_unitario,
                        "precio_unitario": item_compra.precio_unitario or item_compra.costo_unitario
                    }
                    lotes_existentes.append(nuevo_lote)
                    items_inventario[item_existente_idx]["lotes"] = lotes_existentes
                    print(f"[CREAR-COMPRA] Lote agregado a producto existente: {nuevo_lote['numero_lote']}")
                
                # Actualizar referencia a compra
                compras_ids = items_inventario[item_existente_idx].get("compras_ids", [])
                if not isinstance(compras_ids, list):
                    compras_ids = []
                if compra_id not in compras_ids:
                    compras_ids.append(compra_id)
                items_inventario[item_existente_idx]["compras_ids"] = compras_ids
                
            else:
                # Producto no existe: crear nuevo item
                print(f"[CREAR-COMPRA] Producto nuevo: {item_compra.codigo}, creando...")
                
                item_inventario = {
                    "item_id": str(ObjectId()),  # Generar ID único
                    "codigo": item_compra.codigo,
                    "nombre": item_compra.nombre,
                    "descripcion": item_compra.descripcion or item_compra.nombre,
                    "cantidad": item_compra.cantidad,
                    "costo_unitario": item_compra.costo_unitario,
                    "precio_unitario": item_compra.precio_unitario or item_compra.costo_unitario,
                    "costo": costo_item,
                    "precio": (item_compra.precio_unitario or item_compra.costo_unitario) * item_compra.cantidad,
                    "utilidad_contable": (
                        (item_compra.precio_unitario or item_compra.costo_unitario) - item_compra.costo_unitario
                    ) * item_compra.cantidad if item_compra.precio_unitario else 0,
                    "inventario_id": inventario_id,
                    "compra_id": compra_id,  # Referencia a la compra
                    "compras_ids": [compra_id]
                }
                
                # Agregar lotes si se proporcionan
                if item_compra.lote or item_compra.fecha_vencimiento:
                    lotes = []
                    lote = {
                        "numero_lote": item_compra.lote or f"LOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "fecha_vencimiento": item_compra.fecha_vencimiento,
                        "cantidad": item_compra.cantidad,
                        "costo_unitario": item_compra.costo_unitario,
                        "precio_unitario": item_compra.precio_unitario or item_compra.costo_unitario
                    }
                    lotes.append(lote)
                    item_inventario["lotes"] = lotes
                
                nuevos_items.append(item_inventario)
                items_inventario.append(item_inventario)
            
            # Crear o actualizar producto en la colección PRODUCTOS
            try:
                producto_existente = await productos_collection.find_one({
                    "codigo": item_compra.codigo,
                    "estado": "activo"
                })
                
                if producto_existente:
                    # Actualizar producto existente
                    precio_unitario_final = item_compra.precio_unitario or item_compra.costo_unitario
                    stock_actual = producto_existente.get("stock", 0) or 0
                    stock_nuevo = stock_actual + item_compra.cantidad
                    
                    # Actualizar stock por sucursal si hay sucursal
                    stock_sucursal = producto_existente.get("stock_sucursal", {})
                    if not isinstance(stock_sucursal, dict):
                        stock_sucursal = {}
                    
                    if compra.sucursal:
                        stock_anterior_sucursal = stock_sucursal.get(compra.sucursal, 0) or 0
                        stock_sucursal[compra.sucursal] = stock_anterior_sucursal + item_compra.cantidad
                    
                    # Actualizar sucursales
                    sucursales = producto_existente.get("sucursales", [])
                    if not isinstance(sucursales, list):
                        sucursales = []
                    if compra.sucursal and compra.sucursal not in sucursales:
                        sucursales.append(compra.sucursal)
                    
                    await productos_collection.update_one(
                        {"_id": producto_existente["_id"]},
                        {
                            "$set": {
                                "nombre": item_compra.nombre,
                                "precio": precio_unitario_final,
                                "costo": item_compra.costo_unitario,
                                "stock": stock_nuevo,
                                "stock_sucursal": stock_sucursal,
                                "sucursal": compra.sucursal or producto_existente.get("sucursal"),
                                "sucursales": sucursales,
                                "fecha_actualizacion": datetime.now().isoformat(),
                                "usuario_actualizacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
                            }
                        }
                    )
                    productos_actualizados.append(item_compra.codigo)
                    print(f"[CREAR-COMPRA] Producto actualizado en PRODUCTOS: {item_compra.codigo}")
                else:
                    # Crear nuevo producto
                    precio_unitario_final = item_compra.precio_unitario or item_compra.costo_unitario
                    stock_sucursal = {}
                    if compra.sucursal:
                        stock_sucursal[compra.sucursal] = item_compra.cantidad
                    
                    nuevo_producto = {
                        "codigo": item_compra.codigo,
                        "nombre": item_compra.nombre,
                        "descripcion": item_compra.descripcion or item_compra.nombre,
                        "precio": precio_unitario_final,
                        "costo": item_compra.costo_unitario,
                        "stock": item_compra.cantidad,
                        "stock_sucursal": stock_sucursal,
                        "sucursal": compra.sucursal,
                        "sucursales": [compra.sucursal] if compra.sucursal else [],
                        "estado": "activo",
                        "fecha_creacion": datetime.now().isoformat(),
                        "usuario_creacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
                    }
                    
                    await productos_collection.insert_one(nuevo_producto)
                    productos_actualizados.append(item_compra.codigo)
                    print(f"[CREAR-COMPRA] Nuevo producto creado en PRODUCTOS: {item_compra.codigo}")
            except Exception as e:
                # Si falla la actualización de PRODUCTOS, continuar (no es crítico)
                print(f"[CREAR-COMPRA] Advertencia: Error al actualizar PRODUCTOS para {item_compra.codigo}: {str(e)}")
        
        # Actualizar inventario con los nuevos items y costo total
        costo_total_inventario += costo_total_compra
        
        update_inventario = {
            "$set": {
                "items": items_inventario,
                "costo": costo_total_inventario,
                "fecha_actualizacion": datetime.now()
            }
        }
        
        await inventarios_collection.update_one(
            {"_id": ObjectId(inventario_id)},
            update_inventario
        )
        
        print(f"[CREAR-COMPRA] Inventario actualizado: {inventario_id}, {len(nuevos_items)} items nuevos, {len(productos_actualizados)} productos procesados")
        
        # Obtener la compra creada para retornarla
        compra_creada = await compras_collection.find_one({"_id": ObjectId(compra_id)})
        compra_creada["_id"] = str(compra_creada["_id"])
        
        return CompraResponse(**compra_creada)
        
    except HTTPException:
        raise
    except InvalidId as e:
        raise HTTPException(
            status_code=400,
            detail=f"ID inválido: {str(e)}"
        )
    except Exception as e:
        print(f"[CREAR-COMPRA] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear compra: {str(e)}"
        )

