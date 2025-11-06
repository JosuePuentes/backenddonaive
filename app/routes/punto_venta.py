from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongo import get_collection, db
from app.core.get_current_user import get_current_user
from app.schemas.punto_venta import (
    TasaCambioResponse,
    ProductoItem,
    VentaRequest,
    VentaResponse
)
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime
import re

router = APIRouter()


def verificar_permiso(usuario: dict, permiso: str):
    """Verifica si el usuario tiene un permiso específico"""
    permisos = usuario.get("permisos", [])
    if permiso not in permisos:
        raise HTTPException(
            status_code=403,
            detail=f"No tienes permisos para realizar esta acción. Se requiere: {permiso}"
        )


@router.get("/tasa-del-dia", response_model=TasaCambioResponse)
async def obtener_tasa_del_dia(
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene la tasa de cambio del día (Bs/USD) para una fecha específica.
    Requiere permiso: agregar_cuadre
    """
    verificar_permiso(usuario, "agregar_cuadre")
    
    try:
        # Validar formato de fecha
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    
    try:
        # Primero intentar buscar en colección TASAS si existe
        try:
            tasas_collection = get_collection("TASAS")
            # Buscar tasa por fecha exacta
            tasa_doc = await tasas_collection.find_one({"fecha": fecha})
            if tasa_doc and tasa_doc.get("tasa"):
                return TasaCambioResponse(
                    fecha=fecha,
                    tasa=float(tasa_doc.get("tasa", 1.0)),
                    divisa="Bs/USD"
                )
        except:
            pass
        
        # Buscar en CUADRES (donde se almacenan las tasas del día)
        colecciones = [f"CUADRES-0{i}" for i in range(1, 8)]
        
        # Primero buscar por fecha exacta
        for nombre in colecciones:
            collection = db[nombre]
            cuadre = await collection.find_one({"dia": fecha})
            if cuadre and cuadre.get("tasa"):
                return TasaCambioResponse(
                    fecha=fecha,
                    tasa=float(cuadre.get("tasa", 1.0)),
                    divisa="Bs/USD"
                )
        
        # Si no hay tasa para esa fecha exacta, buscar la más reciente anterior
        for nombre in colecciones:
            collection = db[nombre]
            cuadre = await collection.find_one(
                {"dia": {"$lte": fecha}, "tasa": {"$exists": True, "$ne": None}},
                sort=[("dia", -1)]
            )
            if cuadre and cuadre.get("tasa"):
                return TasaCambioResponse(
                    fecha=cuadre.get("dia", fecha),
                    tasa=float(cuadre.get("tasa", 1.0)),
                    divisa="Bs/USD"
                )
        
        # Si no se encuentra ninguna tasa, retornar error
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró tasa de cambio para la fecha {fecha}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener la tasa del día: {str(e)}"
        )


@router.get("/productos", response_model=List[ProductoItem])
async def obtener_productos(
    sucursal: Optional[str] = Query(None, description="ID de la sucursal"),
    todos: bool = Query(False, description="Si es true, devuelve todos los productos sin límite"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene todos los productos de una sucursal.
    Útil para cargar todos los productos de una vez en modales o listas.
    
    Parámetros:
    - sucursal: ID de la sucursal (requerido si todos=true)
    - todos: Si es true, devuelve todos los productos sin límite
    """
    verificar_permiso(usuario, "agregar_cuadre")
    
    if todos and not sucursal:
        raise HTTPException(
            status_code=400,
            detail="El parámetro 'sucursal' es requerido cuando 'todos=true'"
        )
    
    try:
        productos_collection = get_collection("PRODUCTOS")
        
        # Si no existe PRODUCTOS, usar INVENTARIOS
        try:
            await productos_collection.find_one({})
        except:
            productos_collection = get_collection("INVENTARIOS")
        
        # Construir query
        query = {
            "estado": "activo"
        }
        
        # Filtrar por sucursal si se proporciona
        if sucursal:
            filtro_sucursal = {
                "$or": [
                    {"sucursal": sucursal},
                    {"sucursales": {"$in": [sucursal]}},
                    {f"stock_sucursal.{sucursal}": {"$exists": True}}
                ]
            }
            query = {
                "$and": [query, filtro_sucursal]
            }
        
        # Obtener productos (sin límite si todos=true)
        if todos:
            productos = await productos_collection.find(query).to_list(length=None)
        else:
            # Si no es "todos", usar el endpoint de búsqueda
            raise HTTPException(
                status_code=400,
                detail="Use el endpoint /productos/buscar para búsquedas específicas o pase todos=true para obtener todos los productos"
            )
        
        # Transformar resultados
        resultado = []
        for producto in productos:
            stock = producto.get("stock", 0)
            precio = producto.get("precio", producto.get("costo", 0))
            
            # Obtener stock de la sucursal específica
            if sucursal:
                stock_sucursal = producto.get("stock_sucursal", {})
                if isinstance(stock_sucursal, dict):
                    stock = stock_sucursal.get(sucursal, stock)
                elif isinstance(stock_sucursal, list):
                    for item in stock_sucursal:
                        if item.get("sucursal") == sucursal:
                            stock = item.get("stock", stock)
                            break
            
            resultado.append(ProductoItem(
                id=str(producto["_id"]),
                nombre=producto.get("nombre", producto.get("farmacia", "Sin nombre")),
                codigo=producto.get("codigo"),
                precio=float(precio),
                precio_usd=None,
                stock=int(stock),
                sucursal=sucursal or producto.get("sucursal")
            ))
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener productos: {str(e)}"
        )


@router.get("/productos/buscar", response_model=List[ProductoItem])
async def buscar_productos(
    q: str = Query(..., description="Query de búsqueda (nombre o código)"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal"),
    usuario: dict = Depends(get_current_user)
):
    """
    Busca productos por nombre o código en tiempo real.
    Requiere permiso: agregar_cuadre
    """
    verificar_permiso(usuario, "agregar_cuadre")
    
    # Si la búsqueda tiene menos de 1 carácter, devolver array vacío
    if not q or len(q.strip()) < 1:
        return []
    
    try:
        # Buscar en la colección de productos/inventarios
        # Asumiendo que los productos están en INVENTARIOS o en una colección PRODUCTOS
        productos_collection = get_collection("PRODUCTOS")
        
        # Si no existe PRODUCTOS, buscar en INVENTARIOS
        try:
            await productos_collection.find_one({})
        except:
            productos_collection = get_collection("INVENTARIOS")
        
        # Construir query de búsqueda base
        query_base = {
            "$or": [
                {"nombre": {"$regex": q, "$options": "i"}},
                {"codigo": {"$regex": q, "$options": "i"}},
                {"farmacia": {"$regex": q, "$options": "i"}}
            ],
            "estado": "activo"
        }
        
        # Filtrar por sucursal si se proporciona
        if sucursal:
            # Buscar productos que estén en la sucursal especificada
            filtro_sucursal = {
                "$or": [
                    {"sucursal": sucursal},
                    {"sucursales": {"$in": [sucursal]}},
                    {f"stock_sucursal.{sucursal}": {"$exists": True}}
                ]
            }
            query = {
                "$and": [query_base, filtro_sucursal]
            }
        else:
            query = query_base
        
        # Buscar productos (limitado a 20 resultados para rendimiento)
        productos = await productos_collection.find(query).limit(20).to_list(length=20)
        
        # Transformar resultados
        resultado = []
        for producto in productos:
            # Obtener stock actual de la sucursal
            stock = producto.get("stock", 0)
            precio = producto.get("precio", producto.get("costo", 0))
            
            # Si hay sucursal específica, buscar stock por sucursal
            if sucursal:
                stock_sucursal = producto.get("stock_sucursal", {})
                if isinstance(stock_sucursal, dict):
                    stock = stock_sucursal.get(sucursal, stock)
                elif isinstance(stock_sucursal, list):
                    for item in stock_sucursal:
                        if item.get("sucursal") == sucursal:
                            stock = item.get("stock", stock)
                            break
            
            resultado.append(ProductoItem(
                id=str(producto["_id"]),
                nombre=producto.get("nombre", producto.get("farmacia", "Sin nombre")),
                codigo=producto.get("codigo"),
                precio=float(precio),
                precio_usd=None,  # Se calculará en el frontend
                stock=int(stock),
                sucursal=sucursal or producto.get("sucursal")
            ))
        
        return resultado
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar productos: {str(e)}"
        )


@router.post("/ventas", response_model=VentaResponse)
async def registrar_venta(
    venta: VentaRequest,
    usuario: dict = Depends(get_current_user)
):
    """
    Registra una nueva venta en el sistema.
    Requiere permiso: agregar_cuadre
    """
    verificar_permiso(usuario, "agregar_cuadre")
    
    try:
        # Validaciones básicas
        if not venta.items or len(venta.items) == 0:
            raise HTTPException(
                status_code=400,
                detail="La venta debe tener al menos un item"
            )
        
        if not venta.metodos_pago or len(venta.metodos_pago) == 0:
            raise HTTPException(
                status_code=400,
                detail="Debe especificar al menos un método de pago"
            )
        
        # Validar que la suma de métodos de pago coincida con el total
        suma_metodos = sum(mp.monto for mp in venta.metodos_pago)
        if abs(suma_metodos - venta.total_bs) > 0.01:  # Tolerancia para decimales
            raise HTTPException(
                status_code=400,
                detail=f"La suma de métodos de pago ({suma_metodos}) no coincide con el total ({venta.total_bs})"
            )
        
        # Validar stock de productos
        productos_collection = get_collection("PRODUCTOS")
        try:
            await productos_collection.find_one({})
        except:
            productos_collection = get_collection("INVENTARIOS")
        
        for item in venta.items:
            try:
                producto = await productos_collection.find_one({"_id": ObjectId(item.producto_id)})
                if not producto:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Producto {item.producto_id} no encontrado"
                    )
                
                # Verificar stock
                stock = producto.get("stock", 0)
                if venta.sucursal:
                    stock_sucursal = producto.get("stock_sucursal", {})
                    if isinstance(stock_sucursal, dict):
                        stock = stock_sucursal.get(venta.sucursal, stock)
                
                if stock < item.cantidad:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para {item.nombre}. Stock disponible: {stock}, solicitado: {item.cantidad}"
                    )
            except InvalidId:
                raise HTTPException(
                    status_code=400,
                    detail=f"ID de producto inválido: {item.producto_id}"
                )
        
        # Generar número de factura
        ventas_collection = get_collection("VENTAS")
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        # Contar ventas del día para generar número de factura
        ventas_hoy = await ventas_collection.count_documents({"fecha": fecha_actual})
        numero_factura = f"FAC-{fecha_actual.replace('-', '')}-{ventas_hoy + 1:04d}"
        
        # Preparar documento de venta
        venta_doc = {
            "numero_factura": numero_factura,
            "fecha": fecha_actual,
            "fecha_hora": datetime.now().isoformat(),
            "items": [item.dict() for item in venta.items],
            "metodos_pago": [mp.dict() for mp in venta.metodos_pago],
            "total_bs": venta.total_bs,
            "total_usd": venta.total_usd,
            "tasa_dia": venta.tasa_dia,
            "sucursal": venta.sucursal,
            "cajero": venta.cajero or usuario.get("correo", usuario.get("usuarioCorreo")),
            "cliente": venta.cliente,
            "notas": venta.notas,
            "usuario_registro": usuario.get("correo", usuario.get("usuarioCorreo"))
        }
        
        # Insertar venta
        result = await ventas_collection.insert_one(venta_doc)
        
        # Actualizar stock de productos
        for item in venta.items:
            try:
                producto = await productos_collection.find_one({"_id": ObjectId(item.producto_id)})
                nuevo_stock = producto.get("stock", 0) - item.cantidad
                
                if venta.sucursal:
                    # Actualizar stock por sucursal
                    stock_sucursal = producto.get("stock_sucursal", {})
                    if isinstance(stock_sucursal, dict):
                        stock_actual = stock_sucursal.get(venta.sucursal, producto.get("stock", 0))
                        stock_sucursal[venta.sucursal] = stock_actual - item.cantidad
                        await productos_collection.update_one(
                            {"_id": ObjectId(item.producto_id)},
                            {"$set": {"stock_sucursal": stock_sucursal, "stock": nuevo_stock}}
                        )
                    else:
                        await productos_collection.update_one(
                            {"_id": ObjectId(item.producto_id)},
                            {"$inc": {"stock": -item.cantidad}}
                        )
                else:
                    await productos_collection.update_one(
                        {"_id": ObjectId(item.producto_id)},
                        {"$inc": {"stock": -item.cantidad}}
                    )
            except Exception as e:
                # Log del error pero no fallar la venta
                print(f"Error al actualizar stock del producto {item.producto_id}: {str(e)}")
        
        # Retornar respuesta
        venta_doc["_id"] = str(result.inserted_id)
        return VentaResponse(**venta_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar la venta: {str(e)}"
        )
