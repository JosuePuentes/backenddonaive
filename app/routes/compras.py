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
            if proveedor.get("fecha_creacion"):
                if isinstance(proveedor["fecha_creacion"], datetime):
                    proveedor["fecha_creacion"] = proveedor["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
            if proveedor.get("fecha_actualizacion"):
                if isinstance(proveedor["fecha_actualizacion"], datetime):
                    proveedor["fecha_actualizacion"] = proveedor["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
            
            resultado.append(ProveedorResponse(**proveedor))
        
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
        proveedor_dict["fecha_creacion"] = datetime.now()
        proveedor_dict["fecha_actualizacion"] = datetime.now()
        proveedor_dict["estado"] = "activo"
        proveedor_dict["usuario_creacion"] = usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
        
        # Insertar proveedor
        result = await proveedores_collection.insert_one(proveedor_dict)
        proveedor_id = str(result.inserted_id)
        
        # Obtener el proveedor creado
        proveedor_creado = await proveedores_collection.find_one({"_id": ObjectId(proveedor_id)})
        proveedor_creado["_id"] = str(proveedor_creado["_id"])
        
        if proveedor_creado.get("fecha_creacion"):
            if isinstance(proveedor_creado["fecha_creacion"], datetime):
                proveedor_creado["fecha_creacion"] = proveedor_creado["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if proveedor_creado.get("fecha_actualizacion"):
            if isinstance(proveedor_creado["fecha_actualizacion"], datetime):
                proveedor_creado["fecha_actualizacion"] = proveedor_creado["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        
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


@router.post("/compras", response_model=CompraResponse, status_code=201)
async def crear_compra(
    compra: CompraCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Crear una nueva compra y actualizar el inventario.
    
    La compra:
    1. Valida que el proveedor exista
    2. Crea un registro de compra en la colección COMPRAS
    3. Busca o crea un inventario activo para la farmacia/sucursal
    4. Agrega los items de la compra al inventario
    5. Actualiza el costo total del inventario
    6. Maneja lotes si se proporcionan
    
    Requiere autenticación.
    """
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
        
        # Procesar items de la compra y agregarlos al inventario
        nuevos_items = []
        costo_total_compra = 0.0
        
        for item_compra in compra.items:
            # Calcular costo del item
            costo_item = item_compra.costo_unitario * item_compra.cantidad
            costo_total_compra += costo_item
            
            # Crear item de inventario
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
                "compra_id": compra_id  # Referencia a la compra
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
        
        print(f"[CREAR-COMPRA] Inventario actualizado: {inventario_id}, {len(nuevos_items)} items agregados")
        
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

