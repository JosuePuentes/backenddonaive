from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongo import get_collection, db
from app.core.get_current_user import get_current_user
from app.schemas.punto_venta import (
    TasaCambioResponse,
    ProductoItem,
    VentaRequest,
    VentaResponse,
    MetodoPago
)
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime
import re
import pytz

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


async def obtener_codigo_farmacia_desde_sucursal(sucursal_id: str) -> Optional[str]:
    """
    Obtiene el código de farmacia desde la sucursal.
    Busca en SUCURSALES y FARMACIAS para encontrar un campo 'codigo' o derivar el código.
    Retorna el código de farmacia (ej: "01", "02") o None si no se encuentra.
    """
    if not sucursal_id:
        return None
    
    try:
        # Intentar buscar en SUCURSALES
        sucursales_collection = get_collection("SUCURSALES")
        try:
            sucursal_doc = await sucursales_collection.find_one({"_id": ObjectId(sucursal_id)})
        except (InvalidId, ValueError):
            try:
                sucursal_doc = await sucursales_collection.find_one({"_id": sucursal_id})
            except:
                sucursal_doc = None
        
        if sucursal_doc:
            # Buscar campo 'codigo' o 'codigoFarmacia'
            codigo = sucursal_doc.get("codigo") or sucursal_doc.get("codigoFarmacia")
            if codigo:
                return str(codigo).zfill(2)  # Asegurar formato 01, 02, etc.
        
        # Intentar buscar en FARMACIAS
        farmacias_collection = get_collection("FARMACIAS")
        try:
            farmacia_doc = await farmacias_collection.find_one({"_id": ObjectId(sucursal_id)})
        except (InvalidId, ValueError):
            try:
                farmacia_doc = await farmacias_collection.find_one({"_id": sucursal_id})
            except:
                farmacia_doc = None
        
        if farmacia_doc:
            codigo = farmacia_doc.get("codigo") or farmacia_doc.get("codigoFarmacia")
            if codigo:
                return str(codigo).zfill(2)
        
        # Si no se encuentra código, retornar None
        return None
        
    except Exception as e:
        print(f"[OBTENER-CODIGO-FARMACIA] Error: {str(e)}")
        return None


async def actualizar_cuadre_con_venta(
    sucursal_id: str,
    metodos_pago: List[MetodoPago],
    total_bs: float,
    total_usd: Optional[float],
    tasa_dia: float
):
    """
    Actualiza o crea un cuadre con estado "wait" para la sucursal, sumando el total de la venta.
    
    Parámetros:
    - sucursal_id: ID de la sucursal
    - metodos_pago: Lista de métodos de pago de la venta
    - total_bs: Total de la venta en Bs
    - total_usd: Total de la venta en USD (opcional)
    - tasa_dia: Tasa de cambio del día
    
    Mapeo de métodos de pago:
    - efectivo USD -> efectivoUsd
    - efectivo Bs -> efectivoBs
    - zelle USD -> zelleUsd
    - transferencia Bs -> pagomovilBs
    - tarjeta Bs o USD -> puntosVenta[0].puntoDebito (convertir USD a Bs si es necesario)
    """
    try:
        print(f"[ACTUALIZAR-CUADRE] Iniciando actualización de cuadre para sucursal: {sucursal_id}")
        
        # Obtener código de farmacia
        codigo_farmacia = await obtener_codigo_farmacia_desde_sucursal(sucursal_id)
        
        # Obtener fecha actual (Venezuela)
        venezuela_tz = pytz.timezone("America/Caracas")
        now_ve = datetime.now(venezuela_tz)
        fecha_actual = now_ve.strftime("%Y-%m-%d")
        
        # Si no se encontró código de farmacia, buscar en todas las colecciones CUADRES-*
        if not codigo_farmacia:
            print(f"[ACTUALIZAR-CUADRE] No se encontró código de farmacia, buscando en todas las colecciones")
            # Buscar en todas las colecciones CUADRES-* (01-07)
            colecciones_posibles = [f"CUADRES-0{i}" for i in range(1, 8)]
            for codigo in colecciones_posibles:
                try:
                    collection = db[codigo]
                    # Buscar cuadre del día
                    cuadre_existente = await collection.find_one({"dia": fecha_actual})
                    if cuadre_existente:
                        codigo_farmacia = codigo.replace("CUADRES-", "")
                        print(f"[ACTUALIZAR-CUADRE] Encontrado cuadre en colección {codigo}")
                        break
                except:
                    continue
        
        # Si aún no hay código, usar "01" por defecto o crear en la primera colección disponible
        if not codigo_farmacia:
            codigo_farmacia = "01"
            print(f"[ACTUALIZAR-CUADRE] Usando código de farmacia por defecto: {codigo_farmacia}")
        
        nombre_coleccion = f"CUADRES-{codigo_farmacia}"
        collection = db[nombre_coleccion]
        
        # Buscar cuadre del día
        cuadre_existente = await collection.find_one({"dia": fecha_actual})
        
        # Preparar incrementos según métodos de pago
        incrementos = {
            "efectivoUsd": 0.0,
            "efectivoBs": 0.0,
            "zelleUsd": 0.0,
            "pagomovilBs": 0.0,
            "puntoDebito": 0.0,  # Para tarjetas
            "puntoCredito": 0.0  # Para tarjetas (si aplica)
        }
        
        # Mapear métodos de pago
        for metodo in metodos_pago:
            tipo = metodo.tipo.lower()
            monto = metodo.monto
            divisa = metodo.divisa.upper() if metodo.divisa else "BS"
            
            if tipo == "efectivo":
                if divisa == "USD":
                    incrementos["efectivoUsd"] += monto
                else:  # Bs
                    incrementos["efectivoBs"] += monto
            elif tipo == "zelle":
                if divisa == "USD":
                    incrementos["zelleUsd"] += monto
                elif divisa == "BS":
                    # Zelle en Bs se convierte a USD usando la tasa
                    incrementos["zelleUsd"] += monto / tasa_dia
            elif tipo == "transferencia":
                if divisa == "BS":
                    incrementos["pagomovilBs"] += monto
                elif divisa == "USD":
                    # Transferencia en USD se convierte a Bs
                    incrementos["pagomovilBs"] += monto * tasa_dia
            elif tipo == "tarjeta":
                if divisa == "BS":
                    incrementos["puntoDebito"] += monto
                elif divisa == "USD":
                    # Tarjeta en USD se convierte a Bs
                    incrementos["puntoDebito"] += monto * tasa_dia
        
        print(f"[ACTUALIZAR-CUADRE] Incrementos calculados: {incrementos}")
        
        # Preparar actualización
        update_data = {
            "$inc": {
                "efectivoUsd": incrementos["efectivoUsd"],
                "efectivoBs": incrementos["efectivoBs"],
                "zelleUsd": incrementos["zelleUsd"],
                "pagomovilBs": incrementos["pagomovilBs"]
            }
        }
        
        # Si hay tarjeta, actualizar puntosVenta
        if incrementos["puntoDebito"] > 0 or incrementos["puntoCredito"] > 0:
            if cuadre_existente:
                puntos_venta = cuadre_existente.get("puntosVenta", [])
                if puntos_venta and len(puntos_venta) > 0:
                    # Actualizar el primer punto de venta
                    punto_actual = puntos_venta[0]
                    punto_debito_actual = punto_actual.get("puntoDebito", 0) or 0
                    punto_credito_actual = punto_actual.get("puntoCredito", 0) or 0
                    
                    # Usar $set para actualizar el array
                    update_data["$set"] = update_data.get("$set", {})
                    update_data["$set"]["puntosVenta.0.puntoDebito"] = punto_debito_actual + incrementos["puntoDebito"]
                    update_data["$set"]["puntosVenta.0.puntoCredito"] = punto_credito_actual + incrementos["puntoCredito"]
                else:
                    # Crear nuevo punto de venta
                    update_data["$set"] = update_data.get("$set", {})
                    update_data["$set"]["puntosVenta"] = [{
                        "puntoDebito": incrementos["puntoDebito"],
                        "puntoCredito": incrementos["puntoCredito"]
                    }]
            else:
                # Si no existe cuadre, se creará con puntosVenta
                pass
        
        if cuadre_existente:
            # Actualizar cuadre existente
            estado_actual = cuadre_existente.get("estado", "wait")
            
            # Si está en "verified" o "denied", mantener el estado
            # Si está en "wait", mantener "wait"
            if estado_actual not in ["verified", "denied", "wait"]:
                estado_actual = "wait"
            
            # No cambiar el estado si ya está en "verified" o "denied"
            if estado_actual in ["verified", "denied"]:
                print(f"[ACTUALIZAR-CUADRE] Cuadre en estado '{estado_actual}', manteniendo estado y sumando montos")
            else:
                # Si está en "wait", asegurar que siga en "wait"
                update_data["$set"] = update_data.get("$set", {})
                update_data["$set"]["estado"] = "wait"
            
            # Actualizar totalCajaSistemaBs (suma de todos los montos en Bs)
            total_caja_actual = cuadre_existente.get("totalCajaSistemaBs", 0) or 0
            total_caja_nuevo = total_caja_actual + total_bs
            update_data["$set"] = update_data.get("$set", {})
            update_data["$set"]["totalCajaSistemaBs"] = total_caja_nuevo
            
            # Actualizar usando $inc y $set
            result = await collection.update_one(
                {"dia": fecha_actual},
                update_data
            )
            
            if result.modified_count == 0:
                print(f"[ACTUALIZAR-CUADRE] Advertencia: No se modificó el cuadre (puede que los valores sean idénticos)")
            else:
                print(f"[ACTUALIZAR-CUADRE] Cuadre actualizado exitosamente. Estado: {estado_actual}")
        else:
            # Crear nuevo cuadre con estado "wait"
            print(f"[ACTUALIZAR-CUADRE] Creando nuevo cuadre para fecha: {fecha_actual}")
            
            nuevo_cuadre = {
                "dia": fecha_actual,
                "cajaNumero": 1,  # Valor por defecto, puede ajustarse
                "tasa": tasa_dia,
                "turno": "mañana",  # Valor por defecto
                "cajero": "",  # Se puede obtener del usuario
                "cajeroId": None,
                "totalCajaSistemaBs": total_bs,
                "devolucionesBs": 0.0,
                "recargaBs": 0.0,
                "pagomovilBs": incrementos["pagomovilBs"],
                "puntosVenta": [{
                    "puntoDebito": incrementos["puntoDebito"],
                    "puntoCredito": incrementos["puntoCredito"]
                }] if (incrementos["puntoDebito"] > 0 or incrementos["puntoCredito"] > 0) else [],
                "efectivoBs": incrementos["efectivoBs"],
                "totalBs": incrementos["efectivoBs"] + incrementos["pagomovilBs"] + incrementos["puntoDebito"],
                "totalBsEnUsd": (incrementos["efectivoBs"] + incrementos["pagomovilBs"] + incrementos["puntoDebito"]) / tasa_dia if tasa_dia > 0 else 0,
                "efectivoUsd": incrementos["efectivoUsd"],
                "zelleUsd": incrementos["zelleUsd"],
                "totalGeneralUsd": incrementos["efectivoUsd"] + incrementos["zelleUsd"],
                "diferenciaUsd": 0.0,
                "sobranteUsd": 0.0,
                "faltanteUsd": 0.0,
                "delete": False,
                "estado": "wait",
                "nombreFarmacia": None,
                "costoInventario": 0.0,
                "fecha": fecha_actual,
                "hora": now_ve.strftime("%H:%M:%S"),
                "valesUsd": 0.0,
                "imagenesCuadre": []
            }
            
            result = await collection.insert_one(nuevo_cuadre)
            print(f"[ACTUALIZAR-CUADRE] Nuevo cuadre creado con ID: {result.inserted_id}")
        
        print(f"[ACTUALIZAR-CUADRE] Cuadre actualizado/creado exitosamente")
        
    except Exception as e:
        # No fallar la venta si hay error al actualizar el cuadre
        print(f"[ACTUALIZAR-CUADRE] ERROR al actualizar cuadre: {str(e)}")
        import traceback
        print(traceback.format_exc())


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
        
        # Validar que la suma de métodos de pago sea suficiente para cubrir el total
        # IMPORTANTE: La suma puede ser mayor que el total cuando hay vuelto
        # IMPORTANTE: Convertir todos los montos a USD para comparar
        suma_metodos_usd = 0.0
        for mp in venta.metodos_pago:
            monto = mp.monto
            divisa = mp.divisa.upper() if mp.divisa else "BS"
            
            # Convertir a USD si es necesario
            if divisa == "USD":
                suma_metodos_usd += monto
            else:  # Bs -> convertir a USD
                suma_metodos_usd += monto / venta.tasa_dia if venta.tasa_dia > 0 else 0
        
        # Convertir total_bs a USD para comparar
        total_usd_calculado = venta.total_bs / venta.tasa_dia if venta.tasa_dia > 0 else 0
        
        # Log para debugging
        print(f"[REGISTRAR-VENTA] Validación de métodos de pago:")
        print(f"  - Total Bs: {venta.total_bs}")
        print(f"  - Total USD (calculado): {total_usd_calculado}")
        print(f"  - Suma métodos de pago (USD): {suma_metodos_usd}")
        print(f"  - Tasa del día: {venta.tasa_dia}")
        for mp in venta.metodos_pago:
            print(f"  - Método: {mp.tipo}, Monto: {mp.monto}, Divisa: {mp.divisa}")
        
        # Validar que el pago sea suficiente (puede ser mayor cuando hay vuelto)
        if suma_metodos_usd < total_usd_calculado - 0.01:  # Tolerancia para decimales
            vuelto = suma_metodos_usd - total_usd_calculado if suma_metodos_usd > total_usd_calculado else 0
            raise HTTPException(
                status_code=400,
                detail=f"Pago insuficiente. Total: ${total_usd_calculado:.2f} USD, Pagado: ${suma_metodos_usd:.2f} USD. Faltan ${(total_usd_calculado - suma_metodos_usd):.2f} USD."
            )
        
        # Log si hay vuelto
        if suma_metodos_usd > total_usd_calculado + 0.01:
            vuelto = suma_metodos_usd - total_usd_calculado
            print(f"[REGISTRAR-VENTA] Vuelto calculado: ${vuelto:.2f} USD (Total: ${total_usd_calculado:.2f}, Pagado: ${suma_metodos_usd:.2f})")
        
        # Validar stock de productos en inventarios
        inventarios_collection = get_collection("INVENTARIOS")
        
        for item_venta in venta.items:
            try:
                codigo_producto = item_venta.codigo
                if not codigo_producto:
                    # Si no hay código, intentar obtenerlo del producto
                    try:
                        productos_collection = get_collection("PRODUCTOS")
                        producto = await productos_collection.find_one({"_id": ObjectId(item_venta.producto_id)})
                        if producto:
                            codigo_producto = producto.get("codigo")
                    except:
                        pass
                
                if not codigo_producto:
                    print(f"[REGISTRAR-VENTA] Advertencia: No se encontró código para producto {item_venta.producto_id}")
                    # Continuar sin validar stock si no hay código (se validará más adelante)
                    continue
                
                cantidad_solicitada = item_venta.cantidad
                stock_disponible = 0
                
                # Buscar el item en inventarios activos de la sucursal
                if venta.sucursal:
                    inventarios = await inventarios_collection.find({
                        "sucursal": venta.sucursal,
                        "estado": "activo"
                    }).sort("fecha_creacion", -1).to_list(length=50)
                    
                    # Buscar el item en los inventarios
                    item_encontrado = None
                    
                    for inventario in inventarios:
                        items = inventario.get("items", []) or inventario.get("items_inventario", [])
                        for item in items:
                            item_codigo = item.get("codigo")
                            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                item_encontrado = item
                                break
                        if item_encontrado:
                            break
                    
                    if item_encontrado:
                        # Calcular stock disponible (suma de lotes si existen, o cantidad del item)
                        lotes = item_encontrado.get("lotes", [])
                        
                        if lotes:
                            # Sumar cantidades de lotes
                            for lote in lotes:
                                stock_disponible += lote.get("cantidad", 0) or 0
                        else:
                            # Si no hay lotes, usar cantidad del item
                            stock_disponible = item_encontrado.get("cantidad", 0) or 0
                        
                        print(f"[REGISTRAR-VENTA] Stock encontrado para {codigo_producto}: {stock_disponible} (lotes: {len(lotes) if lotes else 0})")
                    else:
                        print(f"[REGISTRAR-VENTA] Advertencia: No se encontró item con código {codigo_producto} en inventarios de sucursal {venta.sucursal}")
                        # Si no se encuentra en inventarios, intentar buscar en PRODUCTOS como fallback
                        try:
                            productos_collection = get_collection("PRODUCTOS")
                            producto = await productos_collection.find_one({"_id": ObjectId(item_venta.producto_id)})
                            if producto:
                                stock_disponible = producto.get("stock", 0)
                                if venta.sucursal:
                                    stock_sucursal = producto.get("stock_sucursal", {})
                                    if isinstance(stock_sucursal, dict):
                                        stock_disponible = stock_sucursal.get(venta.sucursal, stock_disponible)
                        except:
                            pass
                
                # Validar stock
                if stock_disponible < cantidad_solicitada:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para {item_venta.nombre} (código: {codigo_producto}). Stock disponible: {stock_disponible}, solicitado: {cantidad_solicitada}"
                    )
                
            except HTTPException:
                raise
            except InvalidId:
                raise HTTPException(
                    status_code=400,
                    detail=f"ID de producto inválido: {item_venta.producto_id}"
                )
            except Exception as e:
                print(f"[REGISTRAR-VENTA] Error al validar stock para {item_venta.nombre}: {str(e)}")
                import traceback
                print(traceback.format_exc())
                # Continuar con la validación para otros items
        
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
        
        # Actualizar stock de productos e inventarios con lógica FIFO para lotes
        inventarios_collection = get_collection("INVENTARIOS")
        
        for item_venta in venta.items:
            try:
                print(f"[REGISTRAR-VENTA] Procesando item: {item_venta.codigo}, cantidad: {item_venta.cantidad}")
                
                # Obtener código del producto
                codigo_producto = item_venta.codigo
                if not codigo_producto:
                    # Si no hay código, intentar obtenerlo del producto
                    try:
                        producto = await productos_collection.find_one({"_id": ObjectId(item_venta.producto_id)})
                        if producto:
                            codigo_producto = producto.get("codigo")
                    except:
                        pass
                
                if not codigo_producto:
                    print(f"[REGISTRAR-VENTA] Advertencia: No se encontró código para producto {item_venta.producto_id}")
                    continue
                
                cantidad_a_descontar = item_venta.cantidad
                
                # Buscar inventarios activos de la sucursal
                if venta.sucursal:
                    inventarios = await inventarios_collection.find({
                        "sucursal": venta.sucursal,
                        "estado": "activo"
                    }).sort("fecha_creacion", -1).to_list(length=50)  # Buscar en los más recientes
                    
                    # Buscar el item en los inventarios
                    item_encontrado = None
                    inventario_encontrado = None
                    
                    for inventario in inventarios:
                        items = inventario.get("items", []) or inventario.get("items_inventario", [])
                        for item in items:
                            item_codigo = item.get("codigo")
                            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                item_encontrado = item
                                inventario_encontrado = inventario
                                break
                        if item_encontrado:
                            break
                    
                    if not item_encontrado or not inventario_encontrado:
                        print(f"[REGISTRAR-VENTA] Advertencia: No se encontró item con código {codigo_producto} en inventarios de sucursal {venta.sucursal}")
                        # Continuar con actualización de stock en PRODUCTOS como fallback
                        try:
                            producto = await productos_collection.find_one({"_id": ObjectId(item_venta.producto_id)})
                            if producto:
                                nuevo_stock = producto.get("stock", 0) - cantidad_a_descontar
                                await productos_collection.update_one(
                                    {"_id": ObjectId(item_venta.producto_id)},
                                    {"$inc": {"stock": -cantidad_a_descontar}}
                                )
                        except:
                            pass
                        continue
                    
                    # Verificar stock disponible
                    lotes = item_encontrado.get("lotes", [])
                    stock_disponible = 0
                    
                    if lotes:
                        # Calcular stock total de lotes
                        for lote in lotes:
                            stock_disponible += lote.get("cantidad", 0) or 0
                    else:
                        # Si no hay lotes, usar cantidad del item
                        stock_disponible = item_encontrado.get("cantidad", 0) or 0
                    
                    print(f"[REGISTRAR-VENTA] Stock disponible: {stock_disponible}, cantidad a descontar: {cantidad_a_descontar}")
                    
                    if stock_disponible < cantidad_a_descontar:
                        print(f"[REGISTRAR-VENTA] ERROR: Stock insuficiente. Disponible: {stock_disponible}, Requerido: {cantidad_a_descontar}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stock insuficiente para el producto {codigo_producto}. Disponible: {stock_disponible}, Requerido: {cantidad_a_descontar}"
                        )
                    
                    # Descontar stock usando FIFO (First In First Out)
                    cantidad_restante = cantidad_a_descontar
                    
                    if lotes:
                        # Ordenar lotes por fecha de vencimiento (más antiguos primero, luego sin fecha)
                        def ordenar_lotes_fifo(lote):
                            fecha = lote.get("fecha_vencimiento")
                            if fecha:
                                try:
                                    if isinstance(fecha, str):
                                        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
                                    else:
                                        fecha_dt = fecha
                                    return (0, fecha_dt)  # Prioridad 0 = tiene fecha
                                except:
                                    return (1, datetime.max)  # Prioridad 1 = fecha inválida
                            return (2, datetime.max)  # Prioridad 2 = sin fecha
                        
                        lotes_ordenados = sorted(lotes, key=ordenar_lotes_fifo)
                        
                        # Descontar de lotes (FIFO)
                        lotes_actualizados = []
                        for lote in lotes_ordenados:
                            if cantidad_restante <= 0:
                                # Ya se descontó todo, agregar el lote sin modificar
                                lotes_actualizados.append(lote)
                                continue
                            
                            cantidad_lote = lote.get("cantidad", 0) or 0
                            
                            if cantidad_lote <= cantidad_restante:
                                # Descontar todo el lote
                                cantidad_restante -= cantidad_lote
                                # No agregar el lote si queda en 0 (eliminarlo)
                                print(f"[REGISTRAR-VENTA] Descontando lote completo: {lote.get('numero_lote', 'N/A')}, cantidad: {cantidad_lote}")
                                # No agregar el lote a lotes_actualizados (se elimina)
                            else:
                                # Descontar parcialmente del lote
                                lote["cantidad"] = cantidad_lote - cantidad_restante
                                print(f"[REGISTRAR-VENTA] Descontando parcialmente lote: {lote.get('numero_lote', 'N/A')}, cantidad restante: {lote['cantidad']}")
                                cantidad_restante = 0
                                lotes_actualizados.append(lote)
                        
                        # Actualizar lotes del item
                        item_encontrado["lotes"] = lotes_actualizados
                        
                        # Recalcular cantidad total del item (suma de lotes)
                        cantidad_total_lotes = sum(l.get("cantidad", 0) or 0 for l in lotes_actualizados)
                        item_encontrado["cantidad"] = cantidad_total_lotes
                        
                        print(f"[REGISTRAR-VENTA] Cantidad total después de descontar lotes: {cantidad_total_lotes}")
                    else:
                        # No hay lotes, descontar de la cantidad del item
                        cantidad_actual = item_encontrado.get("cantidad", 0) or 0
                        item_encontrado["cantidad"] = cantidad_actual - cantidad_a_descontar
                        print(f"[REGISTRAR-VENTA] Descontando de cantidad del item: {cantidad_actual} - {cantidad_a_descontar} = {item_encontrado['cantidad']}")
                    
                    # Actualizar el item en el inventario
                    items = inventario_encontrado.get("items", []) or inventario_encontrado.get("items_inventario", [])
                    for idx, item in enumerate(items):
                        item_codigo = item.get("codigo")
                        if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                            items[idx] = item_encontrado
                            break
                    
                    inventario_encontrado["items"] = items
                    inventario_encontrado["items_inventario"] = items  # Mantener ambos por compatibilidad
                    
                    # Recalcular totales del inventario
                    costo_total_inventario = 0.0
                    total_existencias = 0
                    
                    for item_inv in items:
                        cantidad_item = item_inv.get("cantidad", 0) or 0
                        costo_unitario_item = item_inv.get("costo_unitario", 0) or 0
                        costo_total_inventario += costo_unitario_item * cantidad_item
                        total_existencias += cantidad_item
                    
                    # Actualizar inventario
                    await inventarios_collection.update_one(
                        {"_id": inventario_encontrado["_id"]},
                        {
                            "$set": {
                                "items": items,
                                "items_inventario": items,
                                "costo": costo_total_inventario,
                                "total_items": total_existencias
                            }
                        }
                    )
                    
                    print(f"[REGISTRAR-VENTA] Inventario actualizado. Costo total: {costo_total_inventario}, Total existencias: {total_existencias}")
                
                # También actualizar stock en PRODUCTOS como respaldo
                try:
                    producto = await productos_collection.find_one({"_id": ObjectId(item_venta.producto_id)})
                    if producto:
                        if venta.sucursal:
                            stock_sucursal = producto.get("stock_sucursal", {})
                            if isinstance(stock_sucursal, dict):
                                stock_actual = stock_sucursal.get(venta.sucursal, producto.get("stock", 0))
                                stock_sucursal[venta.sucursal] = stock_actual - cantidad_a_descontar
                                await productos_collection.update_one(
                                    {"_id": ObjectId(item_venta.producto_id)},
                                    {"$set": {"stock_sucursal": stock_sucursal}, "$inc": {"stock": -cantidad_a_descontar}}
                                )
                            else:
                                await productos_collection.update_one(
                                    {"_id": ObjectId(item_venta.producto_id)},
                                    {"$inc": {"stock": -cantidad_a_descontar}}
                                )
                        else:
                            await productos_collection.update_one(
                                {"_id": ObjectId(item_venta.producto_id)},
                                {"$inc": {"stock": -cantidad_a_descontar}}
                            )
                except Exception as e:
                    print(f"[REGISTRAR-VENTA] Advertencia: Error al actualizar stock en PRODUCTOS: {str(e)}")
                    
            except HTTPException:
                raise
            except Exception as e:
                # Log del error pero no fallar la venta si es un error menor
                print(f"[REGISTRAR-VENTA] Error al actualizar stock del item {item_venta.codigo}: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # Actualizar cuadre con la venta (después de registrar la venta exitosamente)
        try:
            await actualizar_cuadre_con_venta(
                sucursal_id=venta.sucursal,
                metodos_pago=venta.metodos_pago,
                total_bs=venta.total_bs,
                total_usd=venta.total_usd,
                tasa_dia=venta.tasa_dia
            )
        except Exception as e:
            # No fallar la venta si hay error al actualizar el cuadre
            print(f"[REGISTRAR-VENTA] Advertencia: Error al actualizar cuadre: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
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


@router.get("/ventas", response_model=List[VentaResponse])
async def obtener_ventas_del_dia(
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal (opcional)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene todas las ventas del día para una fecha específica.
    Opcionalmente filtra por sucursal.
    Requiere autenticación.
    """
    try:
        # Validar formato de fecha
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de fecha inválido. Use YYYY-MM-DD"
            )
        
        # Obtener colección de ventas
        ventas_collection = get_collection("VENTAS")
        
        # Construir filtro
        filtro = {"fecha": fecha}
        
        # Si se especifica sucursal, agregar al filtro
        if sucursal:
            filtro["sucursal"] = sucursal
        
        # Buscar ventas
        ventas = await ventas_collection.find(filtro).sort("fecha_hora", -1).to_list(length=None)
        
        # Formatear resultados
        resultado = []
        for venta in ventas:
            venta["_id"] = str(venta["_id"])
            resultado.append(VentaResponse(**venta))
        
        print(f"[OBTENER-VENTAS] Encontradas {len(resultado)} ventas para fecha {fecha}" + (f" y sucursal {sucursal}" if sucursal else ""))
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-VENTAS] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener ventas del día: {str(e)}"
        )


@router.get("/ventas/usuario", response_model=List[VentaResponse])
async def obtener_ventas_usuario(
    cajero: Optional[str] = Query(None, description="Correo o ID del cajero"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha de inicio en formato YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha de fin en formato YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=1000, description="Número máximo de registros a devolver"),
    offset: int = Query(0, ge=0, description="Número de registros a saltar (para paginación)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene las ventas (facturas procesadas) con filtros opcionales.
    Permite filtrar por cajero, sucursal y rango de fechas.
    Requiere autenticación.
    
    Retorna una lista de ventas ordenadas por fecha_hora (más recientes primero).
    """
    try:
        # Obtener colección de ventas
        ventas_collection = get_collection("VENTAS")
        
        # Construir filtro
        filtro = {}
        condiciones_and = []
        
        # Filtrar por cajero
        if cajero:
            # Buscar por campo 'cajero' o 'usuario_registro'
            condiciones_and.append({
                "$or": [
                    {"cajero": cajero},
                    {"usuario_registro": cajero}
                ]
            })
        
        # Filtrar por sucursal
        if sucursal:
            filtro["sucursal"] = sucursal
        
        # Filtrar por rango de fechas
        if fecha_inicio and fecha_fin:
            # Validar formato de fechas
            try:
                datetime.strptime(fecha_inicio, "%Y-%m-%d")
                datetime.strptime(fecha_fin, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de fecha inválido. Use YYYY-MM-DD"
                )
            
            # Filtrar por campo 'fecha' o 'fecha_hora'
            condiciones_and.append({
                "$or": [
                    {"fecha": {"$gte": fecha_inicio, "$lte": fecha_fin}},
                    {"fecha_hora": {"$gte": fecha_inicio, "$lte": fecha_fin + "T23:59:59"}}
                ]
            })
        elif fecha_inicio:
            # Solo fecha de inicio
            try:
                datetime.strptime(fecha_inicio, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de fecha inválido. Use YYYY-MM-DD"
                )
            condiciones_and.append({
                "$or": [
                    {"fecha": {"$gte": fecha_inicio}},
                    {"fecha_hora": {"$gte": fecha_inicio}}
                ]
            })
        elif fecha_fin:
            # Solo fecha de fin
            try:
                datetime.strptime(fecha_fin, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de fecha inválido. Use YYYY-MM-DD"
                )
            condiciones_and.append({
                "$or": [
                    {"fecha": {"$lte": fecha_fin}},
                    {"fecha_hora": {"$lte": fecha_fin + "T23:59:59"}}
                ]
            })
        
        # Combinar todas las condiciones con $and si hay múltiples
        if condiciones_and:
            if len(condiciones_and) == 1:
                # Si solo hay una condición $or, combinarla con el filtro base
                filtro.update(condiciones_and[0])
            else:
                # Si hay múltiples condiciones, usar $and
                filtro["$and"] = condiciones_and
        
        # Buscar ventas con paginación
        ventas = await ventas_collection.find(filtro).sort("fecha_hora", -1).skip(offset).limit(limit).to_list(length=limit)
        
        # Formatear resultados
        resultado = []
        for venta in ventas:
            venta["_id"] = str(venta["_id"])
            # Asegurar que todos los campos estén presentes
            resultado.append(VentaResponse(**venta))
        
        print(f"[OBTENER-VENTAS-USUARIO] Encontradas {len(resultado)} ventas")
        print(f"  - Filtros: cajero={cajero}, sucursal={sucursal}, fecha_inicio={fecha_inicio}, fecha_fin={fecha_fin}")
        print(f"  - Paginación: offset={offset}, limit={limit}")
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-VENTAS-USUARIO] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener ventas del usuario: {str(e)}"
        )
