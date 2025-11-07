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


async def obtener_nombre_sucursal(sucursal_id) -> str:
    """
    Función helper para obtener el nombre de una sucursal por su ID.
    Intenta buscar en SUCURSALES y FARMACIAS, usando ObjectId o string.
    """
    if not sucursal_id:
        return str(sucursal_id) if sucursal_id else "Sin nombre"
    
    sucursal_id_str = str(sucursal_id)
    
    try:
        sucursales_collection = get_collection("SUCURSALES")
        # Intentar buscar por ObjectId
        try:
            sucursal_doc = await sucursales_collection.find_one({"_id": ObjectId(sucursal_id)})
            if sucursal_doc:
                return sucursal_doc.get("nombre") or sucursal_doc.get("farmacia") or sucursal_id_str
        except (InvalidId, ValueError):
            # Si no es ObjectId válido, buscar por string
            try:
                sucursal_doc = await sucursales_collection.find_one({"_id": sucursal_id_str})
                if sucursal_doc:
                    return sucursal_doc.get("nombre") or sucursal_doc.get("farmacia") or sucursal_id_str
            except:
                pass
        
        # Si no se encuentra en SUCURSALES, intentar en FARMACIAS
        farmacias_collection = get_collection("FARMACIAS")
        try:
            farmacia_doc = await farmacias_collection.find_one({"_id": ObjectId(sucursal_id)})
            if farmacia_doc:
                return farmacia_doc.get("nombre") or farmacia_doc.get("farmacia") or sucursal_id_str
        except (InvalidId, ValueError):
            try:
                farmacia_doc = await farmacias_collection.find_one({"_id": sucursal_id_str})
                if farmacia_doc:
                    return farmacia_doc.get("nombre") or farmacia_doc.get("farmacia") or sucursal_id_str
            except:
                pass
    except Exception as e:
        print(f"[OBTENER-NOMBRE-SUCURSAL] Error al obtener nombre de sucursal {sucursal_id_str}: {str(e)}")
    
    return sucursal_id_str


async def obtener_stock_por_sucursal(codigo_producto: str) -> List[dict]:
    """
    Función helper para obtener el stock de un producto en todas las sucursales.
    Busca el producto por código en todos los inventarios activos.
    
    Retorna una lista con el stock por cada sucursal, incluyendo sucursales con stock 0.
    """
    try:
        inventarios_collection = get_collection("INVENTARIOS")
        sucursales_collection = get_collection("SUCURSALES")
        farmacias_collection = get_collection("FARMACIAS")
        
        # Obtener todas las sucursales para asegurar que todas estén en la respuesta
        sucursales_dict = {}
        try:
            sucursales = await sucursales_collection.find({}).to_list(length=None)
            for suc in sucursales:
                suc_id = str(suc.get("_id", ""))
                suc_nombre = suc.get("nombre") or suc.get("farmacia")
                if not suc_nombre:
                    # Si no tiene nombre, buscar usando la función helper
                    suc_nombre = await obtener_nombre_sucursal(suc.get("_id"))
                sucursales_dict[suc_id] = suc_nombre
        except Exception as e:
            print(f"[OBTENER-STOCK] Error al obtener sucursales: {str(e)}")
        
        # Si no hay sucursales en SUCURSALES, intentar desde FARMACIAS
        if not sucursales_dict:
            try:
                farmacias = await farmacias_collection.find({}).to_list(length=None)
                for farm in farmacias:
                    farm_id = str(farm.get("_id", ""))
                    farm_nombre = farm.get("nombre") or farm.get("farmacia")
                    if not farm_nombre:
                        farm_nombre = await obtener_nombre_sucursal(farm.get("_id"))
                    sucursales_dict[farm_id] = farm_nombre
            except Exception as e:
                print(f"[OBTENER-STOCK] Error al obtener farmacias: {str(e)}")
        
        # Inicializar stock por sucursal (todas con 0)
        stock_por_sucursal = {}
        for suc_id, suc_nombre in sucursales_dict.items():
            stock_por_sucursal[suc_id] = {
                "sucursal_id": suc_id,
                "sucursal_nombre": suc_nombre,
                "cantidad": 0,
                "stock": 0
            }
        
        # Buscar el producto en todos los inventarios activos
        inventarios = await inventarios_collection.find({
            "estado": "activo"
        }).to_list(length=None)
        
        # Primero, agregar todas las sucursales que tienen inventarios activos
        # (aunque no estén en la colección SUCURSALES) y obtener sus nombres correctamente
        for inventario in inventarios:
            sucursal_id = inventario.get("sucursal")
            if not sucursal_id:
                continue
            
            sucursal_id_str = str(sucursal_id)
            if sucursal_id_str not in stock_por_sucursal:
                # Obtener nombre de la sucursal usando la función helper
                sucursal_nombre = await obtener_nombre_sucursal(sucursal_id)
                # Si el inventario tiene un nombre, usarlo como fallback
                if sucursal_nombre == sucursal_id_str:
                    sucursal_nombre = inventario.get("sucursal_nombre") or inventario.get("farmacia") or sucursal_id_str
                
                stock_por_sucursal[sucursal_id_str] = {
                    "sucursal_id": sucursal_id_str,
                    "sucursal_nombre": sucursal_nombre,
                    "cantidad": 0,
                    "stock": 0
                }
            else:
                # Actualizar el nombre si no está bien definido
                if stock_por_sucursal[sucursal_id_str]["sucursal_nombre"] == sucursal_id_str:
                    sucursal_nombre = await obtener_nombre_sucursal(sucursal_id)
                    if sucursal_nombre != sucursal_id_str:
                        stock_por_sucursal[sucursal_id_str]["sucursal_nombre"] = sucursal_nombre
        
        # Buscar items con este código en los inventarios
        for inventario in inventarios:
            sucursal_id = inventario.get("sucursal")
            if not sucursal_id:
                continue
            
            sucursal_id_str = str(sucursal_id)
            items = inventario.get("items", []) or inventario.get("items_inventario", [])
            
            for item in items:
                item_codigo = item.get("codigo")
                # Comparar códigos (pueden ser string o número)
                if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                    # Calcular stock de este item (suma de lotes si existen)
                    cantidad_item = 0
                    item_lotes = item.get("lotes", [])
                    
                    if item_lotes:
                        # Sumar cantidades de lotes
                        for lote in item_lotes:
                            cantidad_lote = lote.get("cantidad", 0) or 0
                            cantidad_item += cantidad_lote
                    else:
                        # Si no hay lotes, usar cantidad del item
                        cantidad_item = item.get("cantidad", 0) or 0
                    
                    # Asegurar que la sucursal esté en el diccionario con nombre correcto
                    if sucursal_id_str not in stock_por_sucursal:
                        sucursal_nombre = await obtener_nombre_sucursal(sucursal_id)
                        if sucursal_nombre == sucursal_id_str:
                            sucursal_nombre = inventario.get("sucursal_nombre") or inventario.get("farmacia") or sucursal_id_str
                        stock_por_sucursal[sucursal_id_str] = {
                            "sucursal_id": sucursal_id_str,
                            "sucursal_nombre": sucursal_nombre,
                            "cantidad": 0,
                            "stock": 0
                        }
                    
                    # Sumar el stock de este item al total de la sucursal
                    stock_por_sucursal[sucursal_id_str]["cantidad"] += cantidad_item
                    stock_por_sucursal[sucursal_id_str]["stock"] += cantidad_item
                    break  # Ya encontramos el item, no buscar más en este inventario
        
        # Convertir a lista y asegurar que todas las sucursales estén incluidas
        resultado = list(stock_por_sucursal.values())
        
        return resultado
        
    except Exception as e:
        print(f"[OBTENER-STOCK] Error al obtener stock por sucursal: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return []


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
        
        # Obtener colección de inventarios para buscar lotes
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Transformar resultados
        resultado = []
        for producto in productos:
            stock = producto.get("stock", 0)
            precio = producto.get("precio", producto.get("costo", 0))
            codigo_producto = producto.get("codigo")
            
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
            
            # CRÍTICO: Buscar lotes en inventarios de la sucursal
            lotes_encontrados = []
            cantidad_total_lotes = 0
            
            if codigo_producto and sucursal:
                try:
                    # Buscar inventarios activos de la sucursal que contengan items con este código
                    inventarios = await inventarios_collection.find({
                        "sucursal": sucursal,
                        "estado": "activo"
                    }).to_list(length=50)  # Limitar a 50 inventarios recientes
                    
                    # Buscar items con este código en los inventarios
                    for inventario in inventarios:
                        items = inventario.get("items", [])
                        for item in items:
                            item_codigo = item.get("codigo")
                            # Comparar códigos (pueden ser string o número)
                            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                # Encontrar lotes en este item
                                item_lotes = item.get("lotes", [])
                                if item_lotes:
                                    for lote in item_lotes:
                                        # Formatear lote para la respuesta
                                        fecha_vencimiento = lote.get("fecha_vencimiento")
                                        # Formatear fecha si es datetime
                                        if fecha_vencimiento:
                                            if isinstance(fecha_vencimiento, datetime):
                                                fecha_vencimiento = fecha_vencimiento.strftime("%Y-%m-%d")
                                            elif isinstance(fecha_vencimiento, str):
                                                # Ya está en formato string
                                                pass
                                        
                                        lote_formateado = {
                                            "lote": lote.get("numero_lote") or lote.get("lote"),
                                            "fecha_vencimiento": fecha_vencimiento,
                                            "cantidad": lote.get("cantidad", 0) or 0
                                        }
                                        # Solo agregar si tiene lote o cantidad
                                        if lote_formateado["lote"] or lote_formateado["cantidad"] > 0:
                                            lotes_encontrados.append(lote_formateado)
                                            cantidad_total_lotes += lote_formateado["cantidad"]
                                break  # Ya encontramos el item, no buscar más en este inventario
                except Exception as e:
                    print(f"[OBTENER-PRODUCTOS] Error al buscar lotes: {str(e)}")
                    # Continuar sin lotes si hay error
            
            # Ordenar lotes por fecha de vencimiento (más cercana primero, luego sin fecha)
            def ordenar_lotes(lote):
                fecha = lote.get("fecha_vencimiento")
                if fecha:
                    try:
                        # Convertir a datetime para ordenar
                        if isinstance(fecha, str):
                            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
                        else:
                            fecha_dt = fecha
                        return (0, fecha_dt)  # Prioridad 0 = tiene fecha
                    except:
                        return (1, datetime.max)  # Prioridad 1 = fecha inválida
                return (2, datetime.max)  # Prioridad 2 = sin fecha
            
            lotes_encontrados.sort(key=ordenar_lotes)
            
            # Calcular cantidad total: usar suma de lotes si existen, sino usar stock
            cantidad_final = cantidad_total_lotes if lotes_encontrados else int(stock)
            
            # Obtener stock por sucursal usando la función helper
            stock_por_sucursal_list = []
            if codigo_producto:
                try:
                    stock_por_sucursal_list = await obtener_stock_por_sucursal(codigo_producto)
                except Exception as e:
                    print(f"[OBTENER-PRODUCTOS] Error al obtener stock por sucursal: {str(e)}")
                    # Continuar sin stock por sucursal si hay error
            
            resultado.append(ProductoItem(
                id=str(producto["_id"]),
                nombre=producto.get("nombre", producto.get("farmacia", "Sin nombre")),
                codigo=codigo_producto,
                precio=float(precio),
                precio_usd=None,
                stock=int(stock),  # Mantener para compatibilidad
                cantidad=cantidad_final,  # Stock total (suma de lotes si existen)
                stock_por_sucursal=stock_por_sucursal_list,  # REQUERIDO: Stock en todas las sucursales
                lotes=lotes_encontrados if lotes_encontrados else [],  # Array de lotes ordenado
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
        
        # Obtener colección de inventarios para buscar lotes
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Transformar resultados
        resultado = []
        for producto in productos:
            # Obtener stock actual de la sucursal
            stock = producto.get("stock", 0)
            precio = producto.get("precio", producto.get("costo", 0))
            codigo_producto = producto.get("codigo")
            
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
            
            # CRÍTICO: Buscar lotes en inventarios de la sucursal
            lotes_encontrados = []
            cantidad_total_lotes = 0
            
            if codigo_producto and sucursal:
                try:
                    # Buscar inventarios activos de la sucursal que contengan items con este código
                    inventarios = await inventarios_collection.find({
                        "sucursal": sucursal,
                        "estado": "activo"
                    }).to_list(length=50)  # Limitar a 50 inventarios recientes
                    
                    # Buscar items con este código en los inventarios
                    for inventario in inventarios:
                        items = inventario.get("items", [])
                        for item in items:
                            item_codigo = item.get("codigo")
                            # Comparar códigos (pueden ser string o número)
                            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                # Encontrar lotes en este item
                                item_lotes = item.get("lotes", [])
                                if item_lotes:
                                    for lote in item_lotes:
                                        # Formatear lote para la respuesta
                                        fecha_vencimiento = lote.get("fecha_vencimiento")
                                        # Formatear fecha si es datetime
                                        if fecha_vencimiento:
                                            if isinstance(fecha_vencimiento, datetime):
                                                fecha_vencimiento = fecha_vencimiento.strftime("%Y-%m-%d")
                                            elif isinstance(fecha_vencimiento, str):
                                                # Ya está en formato string
                                                pass
                                        
                                        lote_formateado = {
                                            "lote": lote.get("numero_lote") or lote.get("lote"),
                                            "fecha_vencimiento": fecha_vencimiento,
                                            "cantidad": lote.get("cantidad", 0) or 0
                                        }
                                        # Solo agregar si tiene lote o cantidad
                                        if lote_formateado["lote"] or lote_formateado["cantidad"] > 0:
                                            lotes_encontrados.append(lote_formateado)
                                            cantidad_total_lotes += lote_formateado["cantidad"]
                                break  # Ya encontramos el item, no buscar más en este inventario
                except Exception as e:
                    print(f"[BUSCAR-PRODUCTOS] Error al buscar lotes: {str(e)}")
                    # Continuar sin lotes si hay error
            
            # Ordenar lotes por fecha de vencimiento (más cercana primero, luego sin fecha)
            def ordenar_lotes(lote):
                fecha = lote.get("fecha_vencimiento")
                if fecha:
                    try:
                        # Convertir a datetime para ordenar
                        if isinstance(fecha, str):
                            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
                        else:
                            fecha_dt = fecha
                        return (0, fecha_dt)  # Prioridad 0 = tiene fecha
                    except:
                        return (1, datetime.max)  # Prioridad 1 = fecha inválida
                return (2, datetime.max)  # Prioridad 2 = sin fecha
            
            lotes_encontrados.sort(key=ordenar_lotes)
            
            # Calcular cantidad total: usar suma de lotes si existen, sino usar stock
            cantidad_final = cantidad_total_lotes if lotes_encontrados else int(stock)
            
            # Obtener stock por sucursal usando la función helper
            stock_por_sucursal_list = []
            if codigo_producto:
                try:
                    stock_por_sucursal_list = await obtener_stock_por_sucursal(codigo_producto)
                except Exception as e:
                    print(f"[BUSCAR-PRODUCTOS] Error al obtener stock por sucursal: {str(e)}")
                    # Continuar sin stock por sucursal si hay error
            
            resultado.append(ProductoItem(
                id=str(producto["_id"]),
                nombre=producto.get("nombre", producto.get("farmacia", "Sin nombre")),
                codigo=codigo_producto,
                precio=float(precio),
                precio_usd=None,  # Se calculará en el frontend
                stock=int(stock),  # Mantener para compatibilidad
                cantidad=cantidad_final,  # Stock total (suma de lotes si existen)
                stock_por_sucursal=stock_por_sucursal_list,  # REQUERIDO: Stock en todas las sucursales
                lotes=lotes_encontrados if lotes_encontrados else [],  # Array de lotes ordenado
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
        
        # Validar consistencia de descuentos (opcional, solo si se proporcionan)
        if venta.porcentaje_descuento is not None:
            # Verificar que los descuentos en items sean consistentes con el descuento de la venta
            for item in venta.items:
                if item.descuento_aplicado is not None:
                    # Permitir pequeñas diferencias por redondeo (0.1%)
                    if abs(item.descuento_aplicado - venta.porcentaje_descuento) > 0.1:
                        print(f"[REGISTRAR-VENTA] Advertencia: Descuento en item ({item.descuento_aplicado}%) no coincide con descuento de venta ({venta.porcentaje_descuento}%)")
        
        # Preparar documento de venta
        venta_doc = {
            "numero_factura": numero_factura,
            "fecha": fecha_actual,
            "fecha_hora": datetime.now().isoformat(),
            "items": [item.dict() for item in venta.items],  # Incluye todos los campos de descuento
            "metodos_pago": [mp.dict() for mp in venta.metodos_pago],
            "total_bs": venta.total_bs,
            "total_usd": venta.total_usd,
            "tasa_dia": venta.tasa_dia,
            "sucursal": venta.sucursal,
            "cajero": venta.cajero or usuario.get("correo", usuario.get("usuarioCorreo")),
            "cliente": venta.cliente,
            "porcentaje_descuento": venta.porcentaje_descuento,  # Almacenar descuento a nivel de venta
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
