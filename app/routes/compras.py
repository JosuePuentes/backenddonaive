from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import ValidationError
from app.db.mongo import get_collection
from app.core.get_current_user import get_current_user
from app.schemas.compras import (
    ProveedorCreate, 
    ProveedorResponse, 
    CompraCreate, 
    CompraResponse,
    PagoCompraCreate,
    PagoCompraResponse
)
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime, timedelta

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
        
        # Contar total de proveedores antes de filtrar
        total_proveedores = await proveedores_collection.count_documents({})
        total_proveedores_filtrados = await proveedores_collection.count_documents(query)
        print(f"[LISTAR-PROVEEDORES] Total en BD: {total_proveedores}, Filtrados por query: {total_proveedores_filtrados}, Query: {query}")
        
        # Obtener proveedores con paginación
        proveedores = await proveedores_collection.find(query).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
        print(f"[LISTAR-PROVEEDORES] Proveedores encontrados después de paginación: {len(proveedores)}")
        
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
        print(f"[CREAR-PROVEEDOR] ✅ Proveedor insertado en MongoDB con ID: {proveedor_id}")
        print(f"[CREAR-PROVEEDOR] ✅ inserted_id confirmado: {result.inserted_id}")
        
        # Verificar que el proveedor se guardó correctamente
        proveedor_verificado = await proveedores_collection.find_one({"_id": ObjectId(proveedor_id)})
        if not proveedor_verificado:
            raise HTTPException(
                status_code=500,
                detail="Error: El proveedor no se pudo verificar después de la inserción"
            )
        print(f"[CREAR-PROVEEDOR] ✅ Proveedor verificado en MongoDB: {proveedor_verificado.get('nombre')}")
        
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
    request: Request,
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
        # Obtener datos del body como dict para mayor flexibilidad
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error al parsear el body JSON: {str(e)}"
            )
        
        print(f"[CREAR-COMPRA] Datos recibidos (raw): {data}")
        
        # Validar campos requeridos y aplicar valores por defecto
        if "proveedor_id" not in data:
            raise HTTPException(status_code=400, detail="El campo 'proveedor_id' es requerido")
        
        # Aplicar valores por defecto para campos opcionales
        if "farmacia" not in data or not data["farmacia"]:
            # Intentar obtener farmacia desde sucursal si existe
            if "sucursal_id" in data and data["sucursal_id"]:
                # Aquí podrías buscar la farmacia desde la sucursal
                data["farmacia"] = "01"  # Valor por defecto temporal
                print(f"[CREAR-COMPRA] Farmacia no proporcionada, usando valor por defecto: {data['farmacia']}")
            else:
                raise HTTPException(status_code=400, detail="El campo 'farmacia' es requerido")
        
        if "fecha_compra" not in data or not data["fecha_compra"]:
            data["fecha_compra"] = datetime.now().strftime("%Y-%m-%d")
            print(f"[CREAR-COMPRA] Fecha de compra no proporcionada, usando fecha actual: {data['fecha_compra']}")
        
        if "divisa" not in data or not data["divisa"]:
            data["divisa"] = "USD"  # Valor por defecto
            print(f"[CREAR-COMPRA] Divisa no proporcionada, usando USD por defecto")
        
        # Validar y normalizar items
        if "items" not in data or not data["items"] or len(data["items"]) == 0:
            raise HTTPException(status_code=400, detail="La compra debe tener al menos un item")
        
        # Normalizar items: asegurar que tengan los campos requeridos
        for idx, item in enumerate(data["items"]):
            if "codigo" not in item or not item["codigo"]:
                raise HTTPException(status_code=400, detail=f"El item {idx} debe tener un 'codigo'")
            if "nombre" not in item or not item["nombre"]:
                # Intentar usar descripcion o codigo como nombre
                item["nombre"] = item.get("descripcion") or item.get("codigo") or f"Producto {item['codigo']}"
                print(f"[CREAR-COMPRA] Item {idx} sin nombre, usando: {item['nombre']}")
            if "cantidad" not in item or item["cantidad"] is None:
                raise HTTPException(status_code=400, detail=f"El item {idx} debe tener una 'cantidad'")
            if "costo_unitario" not in item or item["costo_unitario"] is None:
                # Intentar calcular desde precio_unitario o usar 0
                if "precio_unitario" in item and item["precio_unitario"]:
                    item["costo_unitario"] = item["precio_unitario"]
                else:
                    raise HTTPException(status_code=400, detail=f"El item {idx} debe tener un 'costo_unitario'")
        
        # Calcular total si no viene
        if "total" not in data or not data["total"]:
            total_calculado = 0.0
            for item in data["items"]:
                cantidad = float(item.get("cantidad", 0))
                costo_unitario = float(item.get("costo_unitario", 0))
                total_calculado += cantidad * costo_unitario
            data["total"] = total_calculado
            print(f"[CREAR-COMPRA] Total no proporcionado, calculado: {data['total']}")
        
        # Validar con Pydantic después de normalizar
        try:
            compra = CompraCreate(**data)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = " -> ".join(str(x) for x in error.get("loc", []))
                msg = error.get("msg", "Error de validación")
                errors.append(f"{field}: {msg}")
            error_msg = f"Error de validación después de normalización: {'; '.join(errors)}"
            print(f"[CREAR-COMPRA] {error_msg}")
            raise HTTPException(status_code=422, detail=error_msg)
        
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
        
        # Validar tasa si la divisa es BS
        if compra.divisa == "BS" and (not compra.tasa or compra.tasa <= 0):
            raise HTTPException(
                status_code=400,
                detail="La tasa de cambio es requerida cuando la divisa es BS"
            )
        
        # Normalizar fecha_compra: usar la fecha actual si no se proporciona
        fecha_compra_final = compra.fecha_compra
        if not fecha_compra_final:
            fecha_compra_final = datetime.now().strftime("%Y-%m-%d")
            print(f"[CREAR-COMPRA] Fecha de compra no proporcionada, usando fecha actual: {fecha_compra_final}")
        
        # Normalizar sucursal_id y sucursal (usar sucursal_id si viene, sino sucursal)
        sucursal_final = compra.sucursal_id or compra.sucursal
        
        # Calcular IVA si lleva_iva es True
        iva_calculado = 0.0
        total_con_iva = compra.total
        if compra.lleva_iva:
            # IVA = 16% sobre el total (costo ajustado)
            iva_calculado = compra.total * 0.16
            total_con_iva = compra.total + iva_calculado
            print(f"[CREAR-COMPRA] IVA calculado: {iva_calculado} (16% de {compra.total})")
        
        # Obtener días de crédito del proveedor
        dias_credito_proveedor = proveedor.get("dias_credito", 0) or 0
        
        # Calcular fecha_vencimiento_factura si no viene y hay días de crédito
        fecha_vencimiento = compra.fecha_vencimiento_factura
        if not fecha_vencimiento and dias_credito_proveedor > 0:
            fecha_compra_obj = datetime.strptime(fecha_compra_final, "%Y-%m-%d")
            fecha_vencimiento = (fecha_compra_obj + timedelta(days=dias_credito_proveedor)).strftime("%Y-%m-%d")
            print(f"[CREAR-COMPRA] Fecha vencimiento calculada: {fecha_vencimiento} (días crédito: {dias_credito_proveedor})")
        
        # Crear registro de compra
        compras_collection = get_collection("COMPRAS")
        compra_dict = compra.dict()
        compra_dict["proveedor_nombre"] = proveedor_nombre
        compra_dict["sucursal"] = sucursal_final
        compra_dict["sucursal_id"] = sucursal_final
        compra_dict["lleva_iva"] = compra.lleva_iva or False
        compra_dict["iva"] = iva_calculado
        compra_dict["total_con_iva"] = total_con_iva
        compra_dict["fecha_compra"] = fecha_compra_final
        compra_dict["fecha_vencimiento_factura"] = fecha_vencimiento
        compra_dict["dias_credito"] = dias_credito_proveedor
        compra_dict["usuario_creacion"] = usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
        compra_dict["fecha_creacion"] = datetime.now().isoformat()
        compra_dict["estado"] = "activa"
        compra_dict["estado_pago"] = "sin_pago"
        compra_dict["monto_pagado"] = 0.0
        compra_dict["monto_pendiente"] = total_con_iva
        
        # Convertir items a dict para guardar
        items_dict = []
        for item in compra.items:
            item_dict = item.dict()
            items_dict.append(item_dict)
        compra_dict["items"] = items_dict
        
        # Insertar compra
        result_compra = await compras_collection.insert_one(compra_dict)
        compra_id = str(result_compra.inserted_id)
        print(f"[CREAR-COMPRA] ✅ Compra insertada en MongoDB con ID: {compra_id}")
        print(f"[CREAR-COMPRA] ✅ inserted_id confirmado: {result_compra.inserted_id}")
        
        # Verificar que la compra se guardó correctamente
        compra_verificada = await compras_collection.find_one({"_id": ObjectId(compra_id)})
        if not compra_verificada:
            raise HTTPException(
                status_code=500,
                detail="Error: La compra no se pudo verificar después de la inserción"
            )
        print(f"[CREAR-COMPRA] ✅ Compra verificada en MongoDB: Total={compra_verificada.get('total')}, Items={len(compra_verificada.get('items', []))}")
        
        # Buscar o crear inventario activo para la farmacia/sucursal
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Construir query para buscar inventario activo
        query_inventario = {
            "farmacia": compra.farmacia,
            "estado": "activo"
        }
        if sucursal_final:
            query_inventario["sucursal"] = sucursal_final
        
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
                "sucursal": sucursal_final,
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
                
                # SUMAR cantidad (no reemplazar)
                cantidad_anterior = item_existente.get("cantidad", 0)
                costo_anterior = item_existente.get("costo", 0)
                costo_unitario_anterior = item_existente.get("costo_unitario", 0)
                
                cantidad_total = cantidad_anterior + item_compra.cantidad
                costo_total_nuevo = costo_anterior + costo_item
                
                # Calcular costo_ajustado (promedio ponderado del costo ajustado)
                # El costo_unitario que viene ya es el costo ajustado (incluye ajuste de dólar negro)
                costo_ajustado = costo_total_nuevo / cantidad_total if cantidad_total > 0 else item_compra.costo_unitario
                
                # Actualizar item existente
                items_inventario[item_existente_idx]["cantidad"] = cantidad_total
                items_inventario[item_existente_idx]["costo"] = costo_total_nuevo
                items_inventario[item_existente_idx]["costo_unitario"] = costo_ajustado  # Usar costo ajustado
                
                # Actualizar precio unitario si se proporciona uno nuevo
                if item_compra.precio_unitario:
                    items_inventario[item_existente_idx]["precio_unitario"] = item_compra.precio_unitario
                
                precio_unitario_final = items_inventario[item_existente_idx].get("precio_unitario", costo_ajustado)
                items_inventario[item_existente_idx]["precio"] = precio_unitario_final * cantidad_total
                
                # Calcular utilidad como porcentaje
                if precio_unitario_final > 0 and costo_ajustado > 0:
                    utilidad_porcentaje = ((precio_unitario_final - costo_ajustado) / costo_ajustado) * 100
                    items_inventario[item_existente_idx]["utilidad"] = round(utilidad_porcentaje, 2)
                    items_inventario[item_existente_idx]["utilidad_contable"] = (
                        precio_unitario_final - costo_ajustado
                    ) * cantidad_total
                else:
                    items_inventario[item_existente_idx]["utilidad"] = 0
                    items_inventario[item_existente_idx]["utilidad_contable"] = 0
                
                # Actualizar marca si viene en la compra
                if item_compra.marca:
                    items_inventario[item_existente_idx]["marca"] = item_compra.marca
                
                # Actualizar utilidad si viene como porcentaje
                if item_compra.utilidad is not None:
                    items_inventario[item_existente_idx]["utilidad"] = item_compra.utilidad
                    # Recalcular precio basado en utilidad si no viene precio_unitario
                    if not item_compra.precio_unitario:
                        nuevo_precio = costo_ajustado * (1 + item_compra.utilidad / 100)
                        items_inventario[item_existente_idx]["precio_unitario"] = nuevo_precio
                        items_inventario[item_existente_idx]["precio"] = nuevo_precio * cantidad_total
                        precio_unitario_final = nuevo_precio
                
                # Manejar lotes: sumar cantidad si existe, crear si no existe
                if item_compra.lote or item_compra.fecha_vencimiento:
                    lotes_existentes = items_inventario[item_existente_idx].get("lotes", [])
                    if not isinstance(lotes_existentes, list):
                        lotes_existentes = []
                    
                    numero_lote = item_compra.lote or f"LOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # Buscar si el lote ya existe
                    lote_existente_idx = None
                    for idx, lote in enumerate(lotes_existentes):
                        if lote.get("numero_lote") == numero_lote:
                            lote_existente_idx = idx
                            break
                    
                    if lote_existente_idx is not None:
                        # Lote existe: sumar cantidad
                        cantidad_lote_anterior = lotes_existentes[lote_existente_idx].get("cantidad", 0)
                        lotes_existentes[lote_existente_idx]["cantidad"] = cantidad_lote_anterior + item_compra.cantidad
                        # Actualizar costo y precio si cambian
                        if item_compra.costo_unitario:
                            lotes_existentes[lote_existente_idx]["costo_unitario"] = item_compra.costo_unitario
                        if item_compra.precio_unitario:
                            lotes_existentes[lote_existente_idx]["precio_unitario"] = item_compra.precio_unitario
                        if item_compra.fecha_vencimiento:
                            lotes_existentes[lote_existente_idx]["fecha_vencimiento"] = item_compra.fecha_vencimiento
                        print(f"[CREAR-COMPRA] Cantidad sumada a lote existente: {numero_lote}")
                    else:
                        # Lote no existe: crear nuevo
                        nuevo_lote = {
                            "numero_lote": numero_lote,
                            "fecha_vencimiento": item_compra.fecha_vencimiento,
                            "cantidad": item_compra.cantidad,
                            "costo_unitario": item_compra.costo_unitario,
                            "precio_unitario": item_compra.precio_unitario or item_compra.costo_unitario
                        }
                        lotes_existentes.append(nuevo_lote)
                        print(f"[CREAR-COMPRA] Nuevo lote creado: {numero_lote}")
                    
                    items_inventario[item_existente_idx]["lotes"] = lotes_existentes
                
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
                
                # Calcular precio y utilidad
                precio_unitario_final = item_compra.precio_unitario
                utilidad_porcentaje = item_compra.utilidad
                
                # Si viene utilidad pero no precio, calcular precio desde utilidad
                if utilidad_porcentaje is not None and not precio_unitario_final:
                    precio_unitario_final = item_compra.costo_unitario * (1 + utilidad_porcentaje / 100)
                
                # Si no viene ni precio ni utilidad, usar costo como precio
                if not precio_unitario_final:
                    precio_unitario_final = item_compra.costo_unitario
                
                # Calcular utilidad como porcentaje si no viene
                if utilidad_porcentaje is None and precio_unitario_final > 0 and item_compra.costo_unitario > 0:
                    utilidad_porcentaje = ((precio_unitario_final - item_compra.costo_unitario) / item_compra.costo_unitario) * 100
                
                item_inventario = {
                    "item_id": str(ObjectId()),  # Generar ID único
                    "codigo": item_compra.codigo,
                    "nombre": item_compra.nombre,
                    "descripcion": item_compra.descripcion or item_compra.nombre,
                    "cantidad": item_compra.cantidad,
                    "costo_unitario": item_compra.costo_unitario,  # Ya es costo ajustado
                    "precio_unitario": precio_unitario_final,
                    "costo": costo_item,
                    "precio": precio_unitario_final * item_compra.cantidad,
                    "utilidad": round(utilidad_porcentaje, 2) if utilidad_porcentaje is not None else 0,
                    "utilidad_contable": (
                        precio_unitario_final - item_compra.costo_unitario
                    ) * item_compra.cantidad if precio_unitario_final > 0 else 0,
                    "inventario_id": inventario_id,
                    "compra_id": compra_id,  # Referencia a la compra
                    "compras_ids": [compra_id]
                }
                
                # Agregar marca si viene
                if item_compra.marca:
                    item_inventario["marca"] = item_compra.marca
                
                # Agregar lotes si se proporcionan
                if item_compra.lote or item_compra.fecha_vencimiento:
                    lotes = []
                    lote = {
                        "numero_lote": item_compra.lote or f"LOTE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "fecha_vencimiento": item_compra.fecha_vencimiento,
                        "cantidad": item_compra.cantidad,
                        "costo_unitario": item_compra.costo_unitario,
                        "precio_unitario": precio_unitario_final
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
                    # Calcular precio y utilidad
                    precio_unitario_final = item_compra.precio_unitario
                    utilidad_porcentaje = item_compra.utilidad
                    
                    # Si viene utilidad pero no precio, calcular precio desde utilidad
                    if utilidad_porcentaje is not None and not precio_unitario_final:
                        precio_unitario_final = item_compra.costo_unitario * (1 + utilidad_porcentaje / 100)
                    
                    # Si no viene ni precio ni utilidad, usar costo como precio
                    if not precio_unitario_final:
                        precio_unitario_final = item_compra.precio_unitario or item_compra.costo_unitario
                    
                    # SUMAR stock (no reemplazar)
                    stock_actual = producto_existente.get("stock", 0) or 0
                    stock_nuevo = stock_actual + item_compra.cantidad
                    
                    # Actualizar stock por sucursal si hay sucursal (usar sucursal_id de la compra)
                    stock_sucursal = producto_existente.get("stock_sucursal", {})
                    if not isinstance(stock_sucursal, dict):
                        stock_sucursal = {}
                    
                    sucursal_para_stock = sucursal_final or compra.sucursal
                    if sucursal_para_stock:
                        stock_anterior_sucursal = stock_sucursal.get(sucursal_para_stock, 0) or 0
                        stock_sucursal[sucursal_para_stock] = stock_anterior_sucursal + item_compra.cantidad
                    
                    # Actualizar sucursales
                    sucursales = producto_existente.get("sucursales", [])
                    if not isinstance(sucursales, list):
                        sucursales = []
                    if sucursal_para_stock and sucursal_para_stock not in sucursales:
                        sucursales.append(sucursal_para_stock)
                    
                    # Preparar actualización
                    update_data = {
                        "nombre": item_compra.nombre,
                        "precio": precio_unitario_final,
                        "costo": item_compra.costo_unitario,  # Usar costo ajustado
                        "stock": stock_nuevo,
                        "stock_sucursal": stock_sucursal,
                        "sucursal": sucursal_para_stock or producto_existente.get("sucursal"),
                        "sucursales": sucursales,
                        "fecha_actualizacion": datetime.now().isoformat(),
                        "usuario_actualizacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
                    }
                    
                    # Actualizar marca si viene
                    if item_compra.marca:
                        update_data["marca"] = item_compra.marca
                    
                    # Actualizar utilidad si viene
                    if utilidad_porcentaje is not None:
                        update_data["utilidad"] = round(utilidad_porcentaje, 2)
                    elif precio_unitario_final > 0 and item_compra.costo_unitario > 0:
                        # Calcular utilidad si no viene
                        utilidad_calculada = ((precio_unitario_final - item_compra.costo_unitario) / item_compra.costo_unitario) * 100
                        update_data["utilidad"] = round(utilidad_calculada, 2)
                    
                    await productos_collection.update_one(
                        {"_id": producto_existente["_id"]},
                        {"$set": update_data}
                    )
                    productos_actualizados.append(item_compra.codigo)
                    print(f"[CREAR-COMPRA] Producto actualizado en PRODUCTOS: {item_compra.codigo}")
                else:
                    # Crear nuevo producto
                    # Calcular precio y utilidad
                    precio_unitario_final = item_compra.precio_unitario
                    utilidad_porcentaje = item_compra.utilidad
                    
                    # Si viene utilidad pero no precio, calcular precio desde utilidad
                    if utilidad_porcentaje is not None and not precio_unitario_final:
                        precio_unitario_final = item_compra.costo_unitario * (1 + utilidad_porcentaje / 100)
                    
                    # Si no viene ni precio ni utilidad, usar costo como precio
                    if not precio_unitario_final:
                        precio_unitario_final = item_compra.costo_unitario
                    
                    # Calcular utilidad como porcentaje si no viene
                    if utilidad_porcentaje is None and precio_unitario_final > 0 and item_compra.costo_unitario > 0:
                        utilidad_porcentaje = ((precio_unitario_final - item_compra.costo_unitario) / item_compra.costo_unitario) * 100
                    
                    stock_sucursal = {}
                    sucursal_para_stock = sucursal_final or compra.sucursal
                    if sucursal_para_stock:
                        stock_sucursal[sucursal_para_stock] = item_compra.cantidad
                    
                    nuevo_producto = {
                        "codigo": item_compra.codigo,
                        "nombre": item_compra.nombre,
                        "descripcion": item_compra.descripcion or item_compra.nombre,
                        "precio": precio_unitario_final,
                        "costo": item_compra.costo_unitario,  # Ya es costo ajustado
                        "stock": item_compra.cantidad,
                        "stock_sucursal": stock_sucursal,
                        "sucursal": sucursal_para_stock,
                        "sucursales": [sucursal_para_stock] if sucursal_para_stock else [],
                        "estado": "activo",
                        "fecha_creacion": datetime.now().isoformat(),
                        "usuario_creacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
                    }
                    
                    # Agregar marca si viene
                    if item_compra.marca:
                        nuevo_producto["marca"] = item_compra.marca
                    
                    # Agregar utilidad como porcentaje
                    if utilidad_porcentaje is not None:
                        nuevo_producto["utilidad"] = round(utilidad_porcentaje, 2)
                    
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
        
        # Calcular días de crédito y mora
        dias_credito, dias_mora = calcular_dias_credito_y_mora(
            compra_creada.get("fecha_compra", ""),
            compra_creada.get("fecha_vencimiento_factura"),
            compra_creada.get("dias_credito", 0) or 0
        )
        compra_creada["dias_credito"] = dias_credito
        compra_creada["dias_mora"] = dias_mora
        
        # Asegurar que todos los campos numéricos estén presentes y normalizados
        compra_creada["lleva_iva"] = compra_creada.get("lleva_iva", False)
        compra_creada["iva"] = float(compra_creada.get("iva", 0) or 0)
        compra_creada["total"] = float(compra_creada.get("total", 0) or 0)
        compra_creada["total_con_iva"] = float(compra_creada.get("total_con_iva") or compra_creada.get("total", 0) or 0)
        compra_creada["sucursal_id"] = compra_creada.get("sucursal_id") or compra_creada.get("sucursal")
        compra_creada["estado_pago"] = compra_creada.get("estado_pago", "sin_pago")
        compra_creada["monto_pagado"] = float(compra_creada.get("monto_pagado", 0) or 0)
        compra_creada["monto_pendiente"] = float(compra_creada.get("monto_pendiente") or compra_creada["total_con_iva"] or 0)
        compra_creada["dias_credito"] = int(compra_creada.get("dias_credito", 0) or 0)
        compra_creada["dias_mora"] = int(compra_creada.get("dias_mora", 0) or 0)
        
        if compra_creada.get("fecha_creacion"):
            if isinstance(compra_creada["fecha_creacion"], datetime):
                compra_creada["fecha_creacion"] = compra_creada["fecha_creacion"].isoformat()
        
        return CompraResponse(**compra_creada)
        
    except ValidationError as e:
        # Error de validación de Pydantic - proporcionar mensaje más claro
        print(f"[CREAR-COMPRA] ERROR de validación Pydantic: {e}")
        errors = []
        for error in e.errors():
            field = " -> ".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "Error de validación")
            error_type = error.get("type", "unknown")
            errors.append(f"{field}: {msg} (tipo: {error_type})")
        error_msg = f"Error de validación: {'; '.join(errors)}"
        print(f"[CREAR-COMPRA] {error_msg}")
        raise HTTPException(
            status_code=422,
            detail=error_msg
        )
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


def calcular_estado_pago(monto_total: float, monto_pagado: float) -> str:
    """Calcula el estado de pago de una compra"""
    if monto_pagado <= 0:
        return "sin_pago"
    elif monto_pagado >= monto_total:
        return "pagada"
    else:
        return "abonado"


def calcular_dias_credito_y_mora(fecha_compra: str, fecha_vencimiento: Optional[str], dias_credito: int) -> tuple:
    """Calcula días de crédito y días de mora"""
    try:
        fecha_actual = datetime.now().date()
        fecha_compra_obj = datetime.strptime(fecha_compra, "%Y-%m-%d").date()
        
        if fecha_vencimiento:
            fecha_vencimiento_obj = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
        elif dias_credito > 0:
            fecha_vencimiento_obj = fecha_compra_obj + timedelta(days=dias_credito)
        else:
            return (0, 0)
        
        dias_mora = 0
        if fecha_actual > fecha_vencimiento_obj:
            dias_mora = (fecha_actual - fecha_vencimiento_obj).days
        
        return (dias_credito, dias_mora)
    except Exception as e:
        print(f"[CALCULAR-DIAS] Error: {str(e)}")
        return (0, 0)


@router.get("/compras", response_model=List[CompraResponse])
async def listar_compras(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(50, ge=1, le=100, description="Número máximo de registros a devolver"),
    sucursal_id: Optional[str] = Query(None, description="Filtrar por ID de sucursal"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (activa, cancelada)"),
    estado_pago: Optional[str] = Query(None, description="Filtrar por estado de pago (sin_pago, abonado, pagada)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Listar todas las compras con paginación y filtros.
    Requiere permiso: compras
    """
    verificar_permiso(usuario, "compras")
    
    try:
        compras_collection = get_collection("COMPRAS")
        
        # Construir query de filtrado
        query = {}
        if sucursal_id:
            query["$or"] = [
                {"sucursal_id": sucursal_id},
                {"sucursal": sucursal_id}
            ]
        if estado:
            query["estado"] = estado
        if estado_pago:
            query["estado_pago"] = estado_pago
        
        # Contar total de compras antes de filtrar
        total_compras = await compras_collection.count_documents({})
        total_compras_filtradas = await compras_collection.count_documents(query)
        print(f"[LISTAR-COMPRAS] Total en BD: {total_compras}, Filtradas por query: {total_compras_filtradas}, Query: {query}")
        
        # Obtener compras con paginación
        compras = await compras_collection.find(query).skip(skip).limit(limit).sort("fecha_creacion", -1).to_list(length=limit)
        print(f"[LISTAR-COMPRAS] Compras encontradas después de paginación: {len(compras)}")
        
        # Obtener colecciones necesarias
        proveedores_collection = get_collection("PROVEEDORES")
        pagos_collection = get_collection("PAGOS_COMPRAS")
        
        # Formatear resultados y calcular estados
        resultado = []
        for compra in compras:
            compra["_id"] = str(compra["_id"])
            
            # Poblar objeto proveedor completo
            proveedor_id = compra.get("proveedor_id")
            if proveedor_id:
                try:
                    proveedor_oid = ObjectId(proveedor_id)
                    proveedor_completo = await proveedores_collection.find_one({"_id": proveedor_oid})
                    
                    if proveedor_completo:
                        # Formatear objeto proveedor
                        proveedor_dict = {
                            "_id": str(proveedor_completo["_id"]),
                            "nombre": proveedor_completo.get("nombre", ""),
                            "rif": proveedor_completo.get("rif"),
                            "telefono": proveedor_completo.get("telefono"),
                            "email": proveedor_completo.get("email"),
                            "direccion": proveedor_completo.get("direccion"),
                            "contacto": proveedor_completo.get("contacto"),
                            "notas": proveedor_completo.get("notas"),
                            "dias_credito": int(proveedor_completo.get("dias_credito", 0) or 0),
                            "descuento_comercial": float(proveedor_completo.get("descuento_comercial", 0) or 0),
                            "descuento_pronto_pago": float(proveedor_completo.get("descuento_pronto_pago", 0) or 0),
                            "estado": proveedor_completo.get("estado", "activo")
                        }
                        
                        # Formatear fechas si existen
                        if proveedor_completo.get("fecha_creacion"):
                            if isinstance(proveedor_completo["fecha_creacion"], datetime):
                                proveedor_dict["fecha_creacion"] = proveedor_completo["fecha_creacion"].strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                proveedor_dict["fecha_creacion"] = proveedor_completo.get("fecha_creacion")
                        
                        if proveedor_completo.get("fecha_actualizacion"):
                            if isinstance(proveedor_completo["fecha_actualizacion"], datetime):
                                proveedor_dict["fecha_actualizacion"] = proveedor_completo["fecha_actualizacion"].strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                proveedor_dict["fecha_actualizacion"] = proveedor_completo.get("fecha_actualizacion")
                        
                        compra["proveedor"] = proveedor_dict
                        print(f"[LISTAR-COMPRAS] Proveedor poblado para compra {compra['_id']}: {proveedor_dict.get('nombre')}")
                    else:
                        # Si no se encuentra el proveedor, crear objeto mínimo
                        compra["proveedor"] = {
                            "_id": proveedor_id,
                            "nombre": compra.get("proveedor_nombre", "Proveedor no encontrado"),
                            "dias_credito": 0,
                            "descuento_comercial": 0.0,
                            "descuento_pronto_pago": 0.0,
                            "estado": "inactivo"
                        }
                        print(f"[LISTAR-COMPRAS] ⚠️ Proveedor no encontrado para compra {compra['_id']}, usando datos mínimos")
                except (InvalidId, Exception) as e:
                    # Si hay error al obtener el proveedor, crear objeto mínimo
                    compra["proveedor"] = {
                        "_id": proveedor_id,
                        "nombre": compra.get("proveedor_nombre", "Proveedor inválido"),
                        "dias_credito": 0,
                        "descuento_comercial": 0.0,
                        "descuento_pronto_pago": 0.0,
                        "estado": "inactivo"
                    }
                    print(f"[LISTAR-COMPRAS] ⚠️ Error al obtener proveedor {proveedor_id}: {str(e)}")
            else:
                # Si no hay proveedor_id, crear objeto vacío
                compra["proveedor"] = {
                    "nombre": compra.get("proveedor_nombre", "Sin proveedor"),
                    "dias_credito": 0,
                    "descuento_comercial": 0.0,
                    "descuento_pronto_pago": 0.0,
                    "estado": "inactivo"
                }
            
            # Obtener todos los pagos de esta compra
            compra_id_str = compra["_id"]
            pagos_compra = await pagos_collection.find({"compra_id": compra_id_str}).sort("fecha_creacion", 1).to_list(length=None)
            
            # Formatear pagos y calcular monto_abonado
            pagos_formateados = []
            monto_abonado = 0.0
            
            for pago in pagos_compra:
                pago_monto = float(pago.get("monto", 0) or 0)
                monto_abonado += pago_monto
                
                pago_dict = {
                    "_id": str(pago.get("_id", "")),
                    "compra_id": compra_id_str,
                    "monto": pago_monto,
                    "fecha_pago": pago.get("fecha_pago", ""),
                    "metodo_pago": pago.get("metodo_pago", ""),
                    "referencia": pago.get("referencia"),
                    "banco_id": pago.get("banco_id"),
                    "notas": pago.get("notas"),
                    "usuario_creacion": pago.get("usuario_creacion"),
                    "fecha_creacion": pago.get("fecha_creacion", "")
                }
                
                # Formatear fecha_creacion si es datetime
                if pago.get("fecha_creacion"):
                    if isinstance(pago["fecha_creacion"], datetime):
                        pago_dict["fecha_creacion"] = pago["fecha_creacion"].isoformat()
                
                pagos_formateados.append(pago_dict)
            
            # Calcular montos y estado
            monto_total = compra.get("total_con_iva") or compra.get("total", 0)
            monto_total = float(monto_total or 0)
            
            # Usar monto_abonado calculado desde los pagos, o el monto_pagado guardado como fallback
            if monto_abonado > 0:
                monto_pagado_calculado = monto_abonado
            else:
                monto_pagado_calculado = float(compra.get("monto_pagado", 0) or 0)
            
            monto_restante = monto_total - monto_pagado_calculado
            
            # Calcular estado según las reglas
            if monto_pagado_calculado >= monto_total:
                estado_pago_calculado = "pagada"
            elif monto_pagado_calculado > 0:
                estado_pago_calculado = "abonado"
            else:
                estado_pago_calculado = "sin_pago"
            
            # Actualizar compra con valores calculados
            compra["monto_pagado"] = monto_pagado_calculado
            compra["monto_abonado"] = monto_abonado  # Nuevo campo
            compra["monto_pendiente"] = monto_restante
            compra["monto_restante"] = monto_restante  # Alias para compatibilidad
            compra["estado_pago"] = estado_pago_calculado
            compra["pagos"] = pagos_formateados  # Array completo de pagos
            
            print(f"[LISTAR-COMPRAS] Compra {compra_id_str}: Total=${monto_total}, Abonado=${monto_abonado}, Restante=${monto_restante}, Estado={estado_pago_calculado}, Pagos={len(pagos_formateados)}")
            
            # Calcular días de crédito y mora (usar días de crédito del proveedor si está disponible)
            dias_credito_proveedor = compra.get("proveedor", {}).get("dias_credito", 0) or compra.get("dias_credito", 0) or 0
            dias_credito, dias_mora = calcular_dias_credito_y_mora(
                compra.get("fecha_compra", ""),
                compra.get("fecha_vencimiento_factura"),
                dias_credito_proveedor
            )
            compra["dias_credito"] = dias_credito
            compra["dias_mora"] = dias_mora
            
            # Normalizar campos numéricos - asegurar que siempre tengan valores por defecto
            compra["lleva_iva"] = compra.get("lleva_iva", False)
            compra["iva"] = float(compra.get("iva", 0) or 0)
            compra["total"] = float(compra.get("total", 0) or 0)
            compra["total_con_iva"] = float(compra.get("total_con_iva") or compra.get("total", 0) or 0)
            compra["monto_pagado"] = float(compra.get("monto_pagado", 0) or 0)
            compra["monto_pendiente"] = float(compra.get("monto_pendiente", 0) or 0)
            compra["dias_credito"] = int(compra.get("dias_credito", 0) or 0)
            compra["dias_mora"] = int(compra.get("dias_mora", 0) or 0)
            compra["tasa"] = float(compra.get("tasa", 0) or 0) if compra.get("tasa") else None
            compra["sucursal_id"] = compra.get("sucursal_id") or compra.get("sucursal")
            
            if compra.get("fecha_creacion"):
                if isinstance(compra["fecha_creacion"], datetime):
                    compra["fecha_creacion"] = compra["fecha_creacion"].isoformat()
            
            resultado.append(CompraResponse(**compra))
        
        return resultado
        
    except Exception as e:
        print(f"[LISTAR-COMPRAS] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar compras: {str(e)}"
        )


@router.post("/compras/{compra_id}/pagos", response_model=PagoCompraResponse, status_code=201)
async def crear_pago_compra(
    compra_id: str,
    request: Request,
    usuario: dict = Depends(get_current_user)
):
    """
    Crear un pago para una compra.
    Actualiza automáticamente el estado de pago de la compra.
    Si se proporciona banco_id, resta el saldo del banco.
    Requiere permiso: compras
    """
    verificar_permiso(usuario, "compras")
    
    try:
        # Obtener datos del request
        data = await request.json()
        
        # Normalizar campos opcionales
        monto = float(data.get("monto", 0) or 0)
        if monto <= 0:
            raise HTTPException(
                status_code=400,
                detail="El monto del pago debe ser mayor a 0"
            )
        
        fecha_pago = data.get("fecha_pago")
        if not fecha_pago:
            fecha_pago = datetime.now().strftime("%Y-%m-%d")
        
        metodo_pago = data.get("metodo_pago", "")
        if not metodo_pago:
            raise HTTPException(
                status_code=400,
                detail="El método de pago es requerido"
            )
        
        banco_id = data.get("banco_id")
        referencia = data.get("referencia")
        notas = data.get("notas")
        
        # Validar que la compra existe
        compras_collection = get_collection("COMPRAS")
        try:
            compra_oid = ObjectId(compra_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de compra inválido"
            )
        
        compra = await compras_collection.find_one({"_id": compra_oid})
        if not compra:
            raise HTTPException(
                status_code=404,
                detail="Compra no encontrada"
            )
        
        # Validar que la compra no esté cancelada
        if compra.get("estado") == "cancelada":
            raise HTTPException(
                status_code=400,
                detail="No se pueden registrar pagos para compras canceladas"
            )
        
        # Obtener montos
        monto_total = compra.get("total_con_iva") or compra.get("total", 0)
        monto_pagado_actual = compra.get("monto_pagado", 0) or 0
        nuevo_monto_pagado = monto_pagado_actual + monto
        
        # Validar que no se pague más del total
        if nuevo_monto_pagado > monto_total + 0.01:  # Tolerancia para decimales
            raise HTTPException(
                status_code=400,
                detail=f"El monto del pago excede el total pendiente. Total: {monto_total}, Pagado: {monto_pagado_actual}, Pendiente: {monto_total - monto_pagado_actual}"
            )
        
        # Variable para guardar el ID del movimiento si se crea
        movimiento_id_obj = None
        
        # Si se proporciona banco_id, validar y restar el saldo del banco
        if banco_id:
            bancos_collection = get_collection("BANCOS")
            try:
                banco_oid = ObjectId(banco_id)
            except InvalidId:
                raise HTTPException(
                    status_code=400,
                    detail="ID de banco inválido"
                )
            
            banco = await bancos_collection.find_one({"_id": banco_oid})
            if not banco:
                raise HTTPException(
                    status_code=404,
                    detail="Banco no encontrado"
                )
            
            # Verificar que el banco esté activo
            if not banco.get("activo", True):
                raise HTTPException(
                    status_code=400,
                    detail="El banco seleccionado no está activo"
                )
            
            # Obtener saldo actual del banco
            saldo_actual = float(banco.get("saldo", 0) or 0)
            
            # Verificar que el banco tenga suficiente saldo
            if saldo_actual < monto:
                raise HTTPException(
                    status_code=400,
                    detail=f"El banco no tiene suficiente saldo. Saldo disponible: {saldo_actual}, Monto requerido: {monto}"
                )
            
            # Restar el saldo del banco
            nuevo_saldo = saldo_actual - monto
            await bancos_collection.update_one(
                {"_id": banco_oid},
                {"$set": {"saldo": nuevo_saldo}}
            )
            
            print(f"[CREAR-PAGO-COMPRA] Saldo del banco actualizado: {saldo_actual} -> {nuevo_saldo} (restado: {monto})")
            
            # Obtener información del proveedor para la descripción
            proveedor_nombre = compra.get("proveedor_nombre", "Proveedor desconocido")
            proveedor_id = compra.get("proveedor_id")
            if proveedor_id:
                try:
                    proveedor_oid = ObjectId(proveedor_id)
                    proveedores_collection = get_collection("PROVEEDORES")
                    proveedor_completo = await proveedores_collection.find_one({"_id": proveedor_oid})
                    if proveedor_completo:
                        proveedor_nombre = proveedor_completo.get("nombre", proveedor_nombre)
                except Exception as e:
                    print(f"[CREAR-PAGO-COMPRA] Error al obtener proveedor para movimiento: {str(e)}")
            
            # Obtener información de la compra para la descripción
            numero_factura = compra.get("numero_factura", "")
            numero_factura_texto = f"Factura {numero_factura}" if numero_factura else "Compra"
            
            # Crear movimiento en el banco
            movimientos_collection = get_collection("MOVIMIENTOS_BANCOS")
            divisa_banco = banco.get("divisa", "USD")
            
            # Construir descripción
            descripcion = f"Pago Compra - {proveedor_nombre}"
            if numero_factura:
                descripcion += f" ({numero_factura_texto})"
            if referencia:
                descripcion += f" - Ref: {referencia}"
            
            movimiento = {
                "banco_id": banco_oid,  # Guardar como ObjectId, no como string
                "tipo": "pago_compra",
                "monto": -abs(monto),  # Negativo para indicar egreso (usar abs para asegurar que sea negativo)
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
            
            # Insertar movimiento (se actualizará el pago_id después)
            print(f"[CREAR-PAGO-COMPRA] 📝 Creando movimiento en banco {banco_id} (ObjectId: {banco_oid})")
            print(f"[CREAR-PAGO-COMPRA] 📝 Datos del movimiento: tipo={movimiento['tipo']}, monto={movimiento['monto']}, banco_id={type(banco_oid).__name__}")
            
            result_movimiento = await movimientos_collection.insert_one(movimiento)
            movimiento_id = str(result_movimiento.inserted_id)
            movimiento_id_obj = result_movimiento.inserted_id  # Guardar ObjectId para actualizar después
            
            print(f"[CREAR-PAGO-COMPRA] ✅ Movimiento creado exitosamente!")
            print(f"[CREAR-PAGO-COMPRA] ✅ ID del movimiento: {movimiento_id}")
            print(f"[CREAR-PAGO-COMPRA] ✅ Banco ID (ObjectId): {banco_oid}")
            print(f"[CREAR-PAGO-COMPRA] ✅ Tipo: {movimiento['tipo']}")
            print(f"[CREAR-PAGO-COMPRA] ✅ Monto: {movimiento['monto']} {movimiento['divisa']}")
            print(f"[CREAR-PAGO-COMPRA] ✅ Descripción: {movimiento['descripcion']}")
        
        # Crear registro de pago
        pagos_collection = get_collection("PAGOS_COMPRAS")
        pago_dict = {
            "compra_id": compra_id,
            "monto": monto,
            "fecha_pago": fecha_pago,
            "metodo_pago": metodo_pago,
            "referencia": referencia,
            "banco_id": banco_id,
            "notas": notas,
            "usuario_creacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown")),
            "fecha_creacion": datetime.now().isoformat()
        }
        
        result_pago = await pagos_collection.insert_one(pago_dict)
        pago_id = str(result_pago.inserted_id)
        
        print(f"[CREAR-PAGO-COMPRA] Pago creado con ID: {pago_id} para compra {compra_id}")
        
        # Si se creó un movimiento, actualizarlo con el pago_id
        if movimiento_id_obj:
            try:
                movimientos_collection = get_collection("MOVIMIENTOS_BANCOS")
                await movimientos_collection.update_one(
                    {"_id": movimiento_id_obj},
                    {"$set": {"pago_id": pago_id}}
                )
                print(f"[CREAR-PAGO-COMPRA] Movimiento actualizado con pago_id: {pago_id}")
            except Exception as e:
                print(f"[CREAR-PAGO-COMPRA] Error al actualizar movimiento con pago_id: {str(e)}")
        
        # Actualizar compra con nuevo monto pagado y estado
        nuevo_estado_pago = calcular_estado_pago(monto_total, nuevo_monto_pagado)
        monto_pendiente = monto_total - nuevo_monto_pagado
        
        await compras_collection.update_one(
            {"_id": compra_oid},
            {
                "$set": {
                    "monto_pagado": nuevo_monto_pagado,
                    "monto_pendiente": monto_pendiente,
                    "estado_pago": nuevo_estado_pago,
                    "fecha_ultimo_pago": datetime.now().isoformat()
                }
            }
        )
        
        print(f"[CREAR-PAGO-COMPRA] Compra actualizada: estado_pago={nuevo_estado_pago}, monto_pagado={nuevo_monto_pagado}")
        
        # Obtener el pago creado
        pago_creado = await pagos_collection.find_one({"_id": ObjectId(pago_id)})
        pago_creado["_id"] = str(pago_creado["_id"])
        
        if pago_creado.get("fecha_creacion"):
            if isinstance(pago_creado["fecha_creacion"], datetime):
                pago_creado["fecha_creacion"] = pago_creado["fecha_creacion"].isoformat()
        
        return PagoCompraResponse(**pago_creado)
        
    except HTTPException:
        raise
    except InvalidId as e:
        raise HTTPException(
            status_code=400,
            detail=f"ID inválido: {str(e)}"
        )
    except Exception as e:
        print(f"[CREAR-PAGO-COMPRA] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear pago: {str(e)}"
        )

