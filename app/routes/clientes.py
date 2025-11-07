from fastapi import APIRouter, HTTPException, Query, Depends, Body
from app.db.mongo import get_collection
from app.core.get_current_user import get_current_user
from app.schemas.clientes import ClienteCreate, ClienteResponse, ComprasTotalResponse, ItemCompraResponse
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime
import re

router = APIRouter()


@router.get("/clientes", response_model=List[ClienteResponse])
async def listar_clientes(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros a devolver"),
    usuario: dict = Depends(get_current_user)
):
    """
    Listar todos los clientes con paginación.
    Requiere autenticación.
    """
    try:
        clientes_collection = get_collection("CLIENTES")
        
        # Obtener clientes con paginación
        clientes = await clientes_collection.find({}).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
        
        # Formatear resultados
        resultado = []
        for cliente in clientes:
            cliente["_id"] = str(cliente["_id"])
            if cliente.get("fecha_creacion"):
                if isinstance(cliente["fecha_creacion"], datetime):
                    cliente["fecha_creacion"] = cliente["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
            if cliente.get("fecha_actualizacion"):
                if isinstance(cliente["fecha_actualizacion"], datetime):
                    cliente["fecha_actualizacion"] = cliente["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
            if cliente.get("fecha_nacimiento"):
                if isinstance(cliente["fecha_nacimiento"], datetime):
                    cliente["fecha_nacimiento"] = cliente["fecha_nacimiento"].strftime("%Y-%m-%d")
            
            resultado.append(ClienteResponse(**cliente))
        
        return resultado
        
    except Exception as e:
        print(f"[LISTAR-CLIENTES] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar clientes: {str(e)}"
        )


@router.post("/clientes", response_model=ClienteResponse, status_code=201)
async def crear_cliente(
    cliente: ClienteCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Crear un nuevo cliente.
    Requiere autenticación.
    """
    try:
        clientes_collection = get_collection("CLIENTES")
        
        # Validar que la cédula no esté vacía
        cedula = cliente.cedula.strip()
        if not cedula:
            raise HTTPException(
                status_code=400,
                detail="La cédula es requerida"
            )
        
        # Verificar que no exista un cliente con la misma cédula
        cliente_existente = await clientes_collection.find_one({
            "cedula": cedula
        })
        
        if cliente_existente:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un cliente con la cédula {cedula}"
            )
        
        # Validar formato de email si se proporciona
        if cliente.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, cliente.email):
                raise HTTPException(
                    status_code=400,
                    detail="El formato del email no es válido"
                )
        
        # Validar formato de fecha de nacimiento si se proporciona
        fecha_nacimiento = None
        if cliente.fecha_nacimiento:
            try:
                fecha_nacimiento = datetime.strptime(cliente.fecha_nacimiento, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="El formato de la fecha de nacimiento debe ser YYYY-MM-DD"
                )
        
        # Validar porcentaje de descuento si se proporciona
        porcentaje_descuento = cliente.porcentaje_descuento
        if porcentaje_descuento is not None:
            if porcentaje_descuento < 0 or porcentaje_descuento > 100:
                raise HTTPException(
                    status_code=400,
                    detail="El porcentaje de descuento debe estar entre 0 y 100"
                )
        
        # Preparar datos del nuevo cliente
        nuevo_cliente = {
            "cedula": cedula,
            "nombre": cliente.nombre.strip(),
            "telefono": cliente.telefono.strip() if cliente.telefono else None,
            "email": cliente.email.strip().lower() if cliente.email else None,
            "direccion": cliente.direccion.strip() if cliente.direccion else None,
            "fecha_nacimiento": cliente.fecha_nacimiento if cliente.fecha_nacimiento else None,
            "porcentaje_descuento": porcentaje_descuento,  # Guardar descuento del cliente
            "notas": cliente.notas.strip() if cliente.notas else None,
            "fecha_creacion": datetime.utcnow(),
            "fecha_actualizacion": datetime.utcnow()
        }
        
        # Insertar cliente
        result = await clientes_collection.insert_one(nuevo_cliente)
        
        # Obtener cliente creado
        cliente_creado = await clientes_collection.find_one(
            {"_id": result.inserted_id}
        )
        
        # Formatear respuesta
        cliente_creado["_id"] = str(cliente_creado["_id"])
        if cliente_creado.get("fecha_creacion"):
            cliente_creado["fecha_creacion"] = cliente_creado["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if cliente_creado.get("fecha_actualizacion"):
            cliente_creado["fecha_actualizacion"] = cliente_creado["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        
        return ClienteResponse(**cliente_creado)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREAR-CLIENTE] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear cliente: {str(e)}"
        )


@router.get("/clientes/buscar", response_model=List[ClienteResponse])
async def buscar_clientes(
    q: str = Query(..., description="Query de búsqueda (cédula o nombre)", min_length=1),
    usuario: dict = Depends(get_current_user)
):
    """
    Buscar clientes por cédula o nombre.
    Requiere autenticación.
    """
    try:
        # Si la búsqueda tiene menos de 1 carácter, devolver array vacío
        if not q or len(q.strip()) < 1:
            return []
        
        clientes_collection = get_collection("CLIENTES")
        
        # Construir query de búsqueda
        # Buscar por cédula (coincidencia exacta o parcial)
        # Buscar por nombre (coincidencia parcial, case-insensitive)
        query = {
            "$or": [
                {"cedula": {"$regex": q.strip(), "$options": "i"}},
                {"nombre": {"$regex": q.strip(), "$options": "i"}}
            ]
        }
        
        # Buscar clientes (limitado a 50 resultados para rendimiento)
        clientes = await clientes_collection.find(query).limit(50).to_list(length=50)
        
        # Formatear resultados
        resultado = []
        for cliente in clientes:
            cliente["_id"] = str(cliente["_id"])
            if cliente.get("fecha_creacion"):
                if isinstance(cliente["fecha_creacion"], datetime):
                    cliente["fecha_creacion"] = cliente["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
            if cliente.get("fecha_actualizacion"):
                if isinstance(cliente["fecha_actualizacion"], datetime):
                    cliente["fecha_actualizacion"] = cliente["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
            if cliente.get("fecha_nacimiento"):
                if isinstance(cliente["fecha_nacimiento"], datetime):
                    cliente["fecha_nacimiento"] = cliente["fecha_nacimiento"].strftime("%Y-%m-%d")
            
            resultado.append(ClienteResponse(**cliente))
        
        return resultado
        
    except Exception as e:
        print(f"[BUSCAR-CLIENTES] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar clientes: {str(e)}"
        )


@router.get("/clientes/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(
    cliente_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Obtener un cliente por su ID.
    Requiere autenticación.
    """
    try:
        clientes_collection = get_collection("CLIENTES")
        
        # Intentar convertir a ObjectId
        try:
            oid = ObjectId(cliente_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de cliente inválido"
            )
        
        # Buscar cliente
        cliente = await clientes_collection.find_one({"_id": oid})
        
        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )
        
        # Formatear respuesta
        cliente["_id"] = str(cliente["_id"])
        if cliente.get("fecha_creacion"):
            if isinstance(cliente["fecha_creacion"], datetime):
                cliente["fecha_creacion"] = cliente["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if cliente.get("fecha_actualizacion"):
            if isinstance(cliente["fecha_actualizacion"], datetime):
                cliente["fecha_actualizacion"] = cliente["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        if cliente.get("fecha_nacimiento"):
            if isinstance(cliente["fecha_nacimiento"], datetime):
                cliente["fecha_nacimiento"] = cliente["fecha_nacimiento"].strftime("%Y-%m-%d")
        
        return ClienteResponse(**cliente)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-CLIENTE] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener cliente: {str(e)}"
        )


@router.put("/clientes/{cliente_id}", response_model=ClienteResponse)
@router.patch("/clientes/{cliente_id}", response_model=ClienteResponse)
async def actualizar_cliente(
    cliente_id: str,
    cliente_data: ClienteCreate,
    usuario: dict = Depends(get_current_user)
):
    """
    Actualizar un cliente existente.
    Requiere autenticación.
    """
    try:
        clientes_collection = get_collection("CLIENTES")
        
        # Intentar convertir a ObjectId
        try:
            oid = ObjectId(cliente_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de cliente inválido"
            )
        
        # Verificar que el cliente existe
        cliente_existente = await clientes_collection.find_one({"_id": oid})
        if not cliente_existente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )
        
        # Validar que la cédula no esté duplicada (si se está cambiando)
        cedula = cliente_data.cedula.strip()
        if cedula and cedula != cliente_existente.get("cedula"):
            cliente_con_cedula = await clientes_collection.find_one({
                "cedula": cedula,
                "_id": {"$ne": oid}  # Excluir el cliente actual
            })
            if cliente_con_cedula:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe otro cliente con la cédula {cedula}"
                )
        
        # Validar formato de email si se proporciona
        if cliente_data.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, cliente_data.email):
                raise HTTPException(
                    status_code=400,
                    detail="El formato del email no es válido"
                )
        
        # Validar formato de fecha de nacimiento si se proporciona
        fecha_nacimiento = None
        if cliente_data.fecha_nacimiento:
            try:
                fecha_nacimiento = datetime.strptime(cliente_data.fecha_nacimiento, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="El formato de la fecha de nacimiento debe ser YYYY-MM-DD"
                )
        
        # Validar porcentaje de descuento si se proporciona
        porcentaje_descuento = cliente_data.porcentaje_descuento
        if porcentaje_descuento is not None:
            if porcentaje_descuento < 0 or porcentaje_descuento > 100:
                raise HTTPException(
                    status_code=400,
                    detail="El porcentaje de descuento debe estar entre 0 y 100"
                )
        
        # Preparar datos de actualización
        update_data = {
            "cedula": cedula if cedula else cliente_existente.get("cedula"),
            "nombre": cliente_data.nombre.strip() if cliente_data.nombre else cliente_existente.get("nombre"),
            "telefono": cliente_data.telefono.strip() if cliente_data.telefono else cliente_existente.get("telefono"),
            "email": cliente_data.email.strip().lower() if cliente_data.email else cliente_existente.get("email"),
            "direccion": cliente_data.direccion.strip() if cliente_data.direccion else cliente_existente.get("direccion"),
            "fecha_nacimiento": cliente_data.fecha_nacimiento if cliente_data.fecha_nacimiento else cliente_existente.get("fecha_nacimiento"),
            "porcentaje_descuento": porcentaje_descuento if porcentaje_descuento is not None else cliente_existente.get("porcentaje_descuento"),
            "notas": cliente_data.notas.strip() if cliente_data.notas else cliente_existente.get("notas"),
            "fecha_actualizacion": datetime.utcnow()
        }
        
        # Actualizar cliente
        result = await clientes_collection.update_one(
            {"_id": oid},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )
        
        # Obtener cliente actualizado
        cliente_actualizado = await clientes_collection.find_one({"_id": oid})
        
        # Formatear respuesta
        cliente_actualizado["_id"] = str(cliente_actualizado["_id"])
        if cliente_actualizado.get("fecha_creacion"):
            if isinstance(cliente_actualizado["fecha_creacion"], datetime):
                cliente_actualizado["fecha_creacion"] = cliente_actualizado["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
        if cliente_actualizado.get("fecha_actualizacion"):
            if isinstance(cliente_actualizado["fecha_actualizacion"], datetime):
                cliente_actualizado["fecha_actualizacion"] = cliente_actualizado["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
        if cliente_actualizado.get("fecha_nacimiento"):
            if isinstance(cliente_actualizado["fecha_nacimiento"], datetime):
                cliente_actualizado["fecha_nacimiento"] = cliente_actualizado["fecha_nacimiento"].strftime("%Y-%m-%d")
        
        return ClienteResponse(**cliente_actualizado)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ACTUALIZAR-CLIENTE] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar cliente: {str(e)}"
        )


@router.get("/clientes/{cliente_id}/compras/total", response_model=ComprasTotalResponse)
async def obtener_total_compras_cliente(
    cliente_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Obtener el total de compras de un cliente.
    Suma todas las ventas donde el campo 'cliente' coincide con cliente_id.
    Requiere autenticación.
    """
    try:
        # Validar que el cliente existe
        clientes_collection = get_collection("CLIENTES")
        try:
            oid = ObjectId(cliente_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de cliente inválido"
            )
        
        cliente = await clientes_collection.find_one({"_id": oid})
        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )
        
        # Buscar todas las ventas del cliente
        ventas_collection = get_collection("VENTAS")
        
        # Buscar ventas donde el campo 'cliente' coincide con cliente_id (puede ser ObjectId o string)
        ventas = await ventas_collection.find({
            "$or": [
                {"cliente": cliente_id},
                {"cliente": oid}
            ]
        }).to_list(length=None)
        
        # Calcular totales
        total_usd = 0.0
        total_bs = 0.0
        numero_ventas = len(ventas)
        
        for venta in ventas:
            total_bs += venta.get("total_bs", 0) or 0
            total_usd += venta.get("total_usd", 0) or 0
        
        return ComprasTotalResponse(
            cliente_id=cliente_id,
            total_usd=round(total_usd, 2),
            total_bs=round(total_bs, 2),
            numero_ventas=numero_ventas
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-TOTAL-COMPRAS] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener total de compras: {str(e)}"
        )


@router.get("/clientes/{cliente_id}/compras/items", response_model=List[ItemCompraResponse])
async def obtener_items_comprados_cliente(
    cliente_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Obtener todos los items comprados por un cliente.
    Retorna un array con todos los items de todas las ventas del cliente.
    Requiere autenticación.
    """
    try:
        # Validar que el cliente existe
        clientes_collection = get_collection("CLIENTES")
        try:
            oid = ObjectId(cliente_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de cliente inválido"
            )
        
        cliente = await clientes_collection.find_one({"_id": oid})
        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )
        
        # Buscar todas las ventas del cliente
        ventas_collection = get_collection("VENTAS")
        
        # Buscar ventas donde el campo 'cliente' coincide con cliente_id (puede ser ObjectId o string)
        ventas = await ventas_collection.find({
            "$or": [
                {"cliente": cliente_id},
                {"cliente": oid}
            ]
        }).sort("fecha_hora", -1).to_list(length=None)  # Ordenar por fecha más reciente primero
        
        # Extraer todos los items de todas las ventas
        items_comprados = []
        
        for venta in ventas:
            fecha_venta = venta.get("fecha_hora") or venta.get("fecha")
            numero_factura = venta.get("numero_factura")
            
            # Formatear fecha
            if isinstance(fecha_venta, datetime):
                fecha_venta_str = fecha_venta.isoformat()
            elif isinstance(fecha_venta, str):
                fecha_venta_str = fecha_venta
            else:
                fecha_venta_str = datetime.utcnow().isoformat()
            
            # Procesar items de esta venta
            items_venta = venta.get("items", [])
            for item in items_venta:
                items_comprados.append(ItemCompraResponse(
                    producto_id=str(item.get("producto_id", "")),
                    nombre=item.get("nombre", "Producto sin nombre"),
                    codigo=item.get("codigo"),
                    cantidad=item.get("cantidad", 0) or 0,
                    precio_unitario=float(item.get("precio_unitario", 0) or 0),
                    precio_unitario_usd=item.get("precio_unitario_usd"),
                    subtotal=float(item.get("subtotal", 0) or 0),
                    subtotal_usd=item.get("subtotal_usd"),
                    fecha_venta=fecha_venta_str,
                    numero_factura=numero_factura
                ))
        
        return items_comprados
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-ITEMS-COMPRADOS] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener items comprados: {str(e)}"
        )

