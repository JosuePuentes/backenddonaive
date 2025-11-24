from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongo import get_collection, db
from app.core.get_current_user import get_current_user
from app.schemas.punto_venta import (
    TasaCambioResponse,
    ProductoItem,
    VentaRequest,
    VentaResponse,
    VentasUsuarioResponse,
    MetodoPago,
    DevolucionRequest,
    ClienteVentaResponse
)
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Optional
from datetime import datetime
import re
import pytz

router = APIRouter()


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


async def devolver_stock_a_inventario(
    codigo_producto: str,
    cantidad: int,
    sucursal_id: str
):
    """
    Devuelve stock a un inventario activo de la sucursal.
    Si hay lotes, agrega a lotes existentes o crea nuevos.
    Si no hay lotes, suma a la cantidad del item.
    """
    try:
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Buscar inventarios activos de la sucursal
        inventarios = await inventarios_collection.find({
            "sucursal": sucursal_id,
            "estado": "activo"
        }).sort("fecha_creacion", -1).to_list(length=10)
        
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
            print(f"[DEVOLVER-STOCK] Advertencia: No se encontró item con código {codigo_producto} en inventarios de sucursal {sucursal_id}")
            return False
        
        # Obtener índice del item en el inventario
        items = inventario_encontrado.get("items", []) or inventario_encontrado.get("items_inventario", [])
        item_index = None
        for idx, item in enumerate(items):
            item_codigo = item.get("codigo")
            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                item_index = idx
                break
        
        if item_index is None:
            print(f"[DEVOLVER-STOCK] ERROR: No se encontró índice del item")
            return False
        
        # Devolver stock
        lotes = item_encontrado.get("lotes", [])
        
        if lotes:
            # Si hay lotes, agregar a un lote existente o crear uno nuevo
            # Por simplicidad, agregar a un lote existente sin fecha o crear uno nuevo
            lote_encontrado = None
            lote_index = None
            for idx, lote in enumerate(lotes):
                if not lote.get("fecha_vencimiento"):
                    lote_encontrado = lote
                    lote_index = idx
                    break
            
            if lote_encontrado:
                # Agregar cantidad a lote existente
                cantidad_actual = lote_encontrado.get("cantidad", 0) or 0
                nueva_cantidad = cantidad_actual + cantidad
                await inventarios_collection.update_one(
                    {"_id": inventario_encontrado["_id"]},
                    {"$set": {f"items.{item_index}.lotes.{lote_index}.cantidad": nueva_cantidad}}
                )
                print(f"[DEVOLVER-STOCK] Stock devuelto a lote existente: {cantidad} unidades")
            else:
                # Crear nuevo lote
                nuevo_lote = {
                    "numero_lote": f"DEV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "fecha_vencimiento": None,
                    "cantidad": cantidad
                }
                lotes.append(nuevo_lote)
                await inventarios_collection.update_one(
                    {"_id": inventario_encontrado["_id"]},
                    {"$set": {f"items.{item_index}.lotes": lotes}}
                )
                print(f"[DEVOLVER-STOCK] Nuevo lote creado para devolución: {cantidad} unidades")
            
            # Recalcular cantidad total del item (suma de lotes)
            inventario_actualizado = await inventarios_collection.find_one({"_id": inventario_encontrado["_id"]})
            items_actualizados = inventario_actualizado.get("items", []) or inventario_actualizado.get("items_inventario", [])
            item_actualizado = items_actualizados[item_index]
            lotes_actualizados = item_actualizado.get("lotes", [])
            cantidad_total_lotes = sum(l.get("cantidad", 0) or 0 for l in lotes_actualizados)
            
            await inventarios_collection.update_one(
                {"_id": inventario_encontrado["_id"]},
                {"$set": {f"items.{item_index}.cantidad": cantidad_total_lotes}}
            )
        else:
            # No hay lotes, sumar a la cantidad del item
            cantidad_actual = item_encontrado.get("cantidad", 0) or 0
            nueva_cantidad = cantidad_actual + cantidad
            await inventarios_collection.update_one(
                {"_id": inventario_encontrado["_id"]},
                {"$set": {f"items.{item_index}.cantidad": nueva_cantidad}}
            )
            print(f"[DEVOLVER-STOCK] Stock devuelto: {cantidad_actual} + {cantidad} = {nueva_cantidad}")
        
        # Recalcular totales del inventario
        inventario_actualizado = await inventarios_collection.find_one({"_id": inventario_encontrado["_id"]})
        items_actualizados = inventario_actualizado.get("items", []) or inventario_actualizado.get("items_inventario", [])
        
        costo_total_inventario = 0.0
        total_existencias = 0
        
        for item_inv in items_actualizados:
            cantidad_item = item_inv.get("cantidad", 0) or 0
            costo_unitario_item = item_inv.get("costo_unitario", 0) or 0
            costo_total_inventario += costo_unitario_item * cantidad_item
            total_existencias += cantidad_item
        
        await inventarios_collection.update_one(
            {"_id": inventario_encontrado["_id"]},
            {"$set": {
                "costo": costo_total_inventario,
                "total_items": total_existencias
            }}
        )
        
        print(f"[DEVOLVER-STOCK] Stock devuelto exitosamente: {cantidad} unidades de {codigo_producto}")
        return True
        
    except Exception as e:
        print(f"[DEVOLVER-STOCK] Error al devolver stock: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False


async def actualizar_saldos_bancarios(
    metodos_pago: List[MetodoPago],
    vuelto: Optional[List[MetodoPago]],
    numero_factura: str,
    venta_id: str,
    usuario: dict
):
    """
    Actualiza los saldos bancarios cuando se registra una venta.
    
    Para métodos de pago con banco_id:
    - Suma el monto al saldo del banco
    - Crea un movimiento tipo "venta"
    
    Para vuelto con banco_id:
    - Resta el monto del saldo del banco
    - Valida que haya saldo suficiente
    - Crea un movimiento tipo "vuelto"
    """
    try:
        bancos_collection = get_collection("BANCOS")
        movimientos_collection = get_collection("MOVIMIENTOS_BANCOS")
        
        # Procesar métodos de pago con banco_id
        for metodo in metodos_pago:
            if metodo.banco_id and metodo.tipo == "banco":
                try:
                    banco_id = metodo.banco_id
                    monto = metodo.monto
                    divisa = metodo.divisa.upper() if metodo.divisa else "USD"
                    
                    print(f"[ACTUALIZAR-SALDOS-BANCOS] Procesando pago: banco_id={banco_id}, monto={monto}, divisa={divisa}")
                    
                    # Validar que el banco existe y está activo
                    try:
                        banco_oid = ObjectId(banco_id)
                    except InvalidId:
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: ID de banco inválido: {banco_id}")
                        continue
                    
                    banco = await bancos_collection.find_one({"_id": banco_oid})
                    if not banco:
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: Banco no encontrado: {banco_id}")
                        continue
                    
                    if not banco.get("activo", True):
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: Banco inactivo: {banco_id}")
                        continue
                    
                    # Obtener saldo actual y divisa del banco
                    saldo_actual = float(banco.get("saldo", 0) or 0)
                    divisa_banco = banco.get("divisa", "USD")
                    
                    # Convertir monto a la divisa del banco si es necesario
                    monto_a_sumar = monto
                    if divisa != divisa_banco:
                        # Si el monto está en una divisa diferente, necesitaríamos la tasa
                        # Por ahora, asumimos que el frontend envía en la divisa correcta
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] Advertencia: Divisa del pago ({divisa}) diferente de divisa del banco ({divisa_banco})")
                    
                    # Actualizar saldo (sumar)
                    nuevo_saldo = saldo_actual + monto_a_sumar
                    await bancos_collection.update_one(
                        {"_id": banco_oid},
                        {"$set": {"saldo": nuevo_saldo}}
                    )
                    
                    print(f"[ACTUALIZAR-SALDOS-BANCOS] Saldo actualizado: {saldo_actual} -> {nuevo_saldo} ({divisa_banco})")
                    
                    # Crear movimiento tipo "venta"
                    movimiento = {
                        "banco_id": banco_id,
                        "tipo": "venta",
                        "monto": monto_a_sumar,
                        "divisa": divisa_banco,
                        "numero_factura": numero_factura,
                        "venta_id": venta_id,
                        "fecha": datetime.now().isoformat(),
                        "usuario": usuario.get("correo", usuario.get("usuarioCorreo", "")),
                        "descripcion": f"Pago de venta {numero_factura}",
                        "saldo_anterior": saldo_actual,
                        "saldo_nuevo": nuevo_saldo
                    }
                    
                    await movimientos_collection.insert_one(movimiento)
                    print(f"[ACTUALIZAR-SALDOS-BANCOS] Movimiento creado para banco {banco_id}")
                    
                except Exception as e:
                    print(f"[ACTUALIZAR-SALDOS-BANCOS] Error al procesar método de pago: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    continue
        
        # Procesar vuelto con banco_id
        if vuelto:
            for metodo_vuelto in vuelto:
                if metodo_vuelto.banco_id and metodo_vuelto.tipo == "banco":
                    try:
                        banco_id = metodo_vuelto.banco_id
                        monto = metodo_vuelto.monto
                        divisa = metodo_vuelto.divisa.upper() if metodo_vuelto.divisa else "USD"
                        
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] Procesando vuelto: banco_id={banco_id}, monto={monto}, divisa={divisa}")
                        
                        # Validar que el banco existe y está activo
                        try:
                            banco_oid = ObjectId(banco_id)
                        except InvalidId:
                            print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: ID de banco inválido: {banco_id}")
                            continue
                        
                        banco = await bancos_collection.find_one({"_id": banco_oid})
                        if not banco:
                            print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: Banco no encontrado: {banco_id}")
                            continue
                        
                        if not banco.get("activo", True):
                            print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: Banco inactivo: {banco_id}")
                            continue
                        
                        # Obtener saldo actual y divisa del banco
                        saldo_actual = float(banco.get("saldo", 0) or 0)
                        divisa_banco = banco.get("divisa", "USD")
                        
                        # Convertir monto a la divisa del banco si es necesario
                        monto_a_restar = monto
                        if divisa != divisa_banco:
                            print(f"[ACTUALIZAR-SALDOS-BANCOS] Advertencia: Divisa del vuelto ({divisa}) diferente de divisa del banco ({divisa_banco})")
                        
                        # Validar que haya saldo suficiente
                        if saldo_actual < monto_a_restar:
                            print(f"[ACTUALIZAR-SALDOS-BANCOS] ERROR: Saldo insuficiente en banco {banco_id}. Saldo: {saldo_actual}, Vuelto: {monto_a_restar}")
                            # No fallar la venta, solo registrar el error
                            continue
                        
                        # Actualizar saldo (restar)
                        nuevo_saldo = saldo_actual - monto_a_restar
                        await bancos_collection.update_one(
                            {"_id": banco_oid},
                            {"$set": {"saldo": nuevo_saldo}}
                        )
                        
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] Saldo actualizado (vuelto): {saldo_actual} -> {nuevo_saldo} ({divisa_banco})")
                        
                        # Crear movimiento tipo "vuelto"
                        movimiento = {
                            "banco_id": banco_id,
                            "tipo": "vuelto",
                            "monto": -monto_a_restar,  # Negativo para indicar salida
                            "divisa": divisa_banco,
                            "numero_factura": numero_factura,
                            "venta_id": venta_id,
                            "fecha": datetime.now().isoformat(),
                            "usuario": usuario.get("correo", usuario.get("usuarioCorreo", "")),
                            "descripcion": f"Vuelto de venta {numero_factura}",
                            "saldo_anterior": saldo_actual,
                            "saldo_nuevo": nuevo_saldo
                        }
                        
                        await movimientos_collection.insert_one(movimiento)
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] Movimiento de vuelto creado para banco {banco_id}")
                        
                    except Exception as e:
                        print(f"[ACTUALIZAR-SALDOS-BANCOS] Error al procesar vuelto: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                        continue
        
        print(f"[ACTUALIZAR-SALDOS-BANCOS] Procesamiento de saldos bancarios completado")
        
    except Exception as e:
        print(f"[ACTUALIZAR-SALDOS-BANCOS] Error crítico: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # No lanzar excepción para no fallar la venta


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
        
        # Actualizar saldos bancarios (después de registrar la venta exitosamente)
        try:
            await actualizar_saldos_bancarios(
                metodos_pago=venta.metodos_pago,
                vuelto=venta.vuelto,
                numero_factura=numero_factura,
                venta_id=str(result.inserted_id),
                usuario=usuario
            )
        except Exception as e:
            # No fallar la venta si hay error al actualizar saldos bancarios
            print(f"[REGISTRAR-VENTA] Advertencia: Error al actualizar saldos bancarios: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        # Retornar respuesta
        venta_doc["_id"] = str(result.inserted_id)
        # Procesar cliente antes de retornar
        venta_doc = await procesar_cliente_en_venta(venta_doc)
        return VentaResponse(**venta_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar la venta: {str(e)}"
        )


@router.get("/ventas/resumen")
async def obtener_resumen_ventas(
    fecha_inicio: str = Query(..., description="Fecha de inicio en formato YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha de fin en formato YYYY-MM-DD"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal (opcional)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene un resumen de ventas por sucursal con desglose de métodos de pago.
    Requiere autenticación.
    
    Clasifica métodos de pago según tipo_metodo del banco:
    - Efectivo USD: bancos con tipo_metodo == "efectivo" en USD
    - Zelle USD: bancos con tipo_metodo == "zelle" en USD
    - Vales USD: bancos con tipo_metodo == "vales" en USD
    - Pago Móvil Bs: bancos con tipo_metodo == "pago_movil" en Bs
    - Efectivo Bs: bancos con tipo_metodo == "efectivo" en Bs
    - Tarjeta Débito Bs: bancos con tipo_metodo == "tarjeta_debit" en Bs
    - Tarjeta Crédito Bs: bancos con tipo_metodo == "tarjeta_credito" en Bs
    """
    try:
        # Validar formato de fechas
        try:
            datetime.strptime(fecha_inicio, "%Y-%m-%d")
            datetime.strptime(fecha_fin, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de fecha inválido. Use YYYY-MM-DD"
            )
        
        # Obtener colecciones
        ventas_collection = get_collection("VENTAS")
        bancos_collection = get_collection("BANCOS")
        inventarios_collection = get_collection("INVENTARIOS")
        
        # Construir filtro de fechas
        filtro = {
            "$or": [
                {"fecha": {"$gte": fecha_inicio, "$lte": fecha_fin}},
                {"fecha_hora": {"$gte": fecha_inicio, "$lte": fecha_fin + "T23:59:59"}}
            ]
        }
        
        # Si se especifica sucursal, agregar al filtro
        if sucursal:
            filtro["sucursal"] = sucursal
        
        # Buscar ventas
        ventas = await ventas_collection.find(filtro).to_list(length=None)
        
        print(f"[RESUMEN-VENTAS] Encontradas {len(ventas)} ventas para rango {fecha_inicio} - {fecha_fin}")
        
        # Estructura para acumular datos por sucursal
        resumen_por_sucursal = {}
        
        # Procesar cada venta
        for venta in ventas:
            sucursal_id = venta.get("sucursal", "sin_sucursal")
            
            # Inicializar sucursal si no existe
            if sucursal_id not in resumen_por_sucursal:
                resumen_por_sucursal[sucursal_id] = {
                    "total_efectivo_usd": 0.0,
                    "total_zelle_usd": 0.0,
                    "total_usd_recibido": 0.0,
                    "total_vales_usd": 0.0,
                    "total_bs": 0.0,
                    "desglose_bs": {
                        "pago_movil": 0.0,
                        "efectivo": 0.0,
                        "tarjeta_debit": 0.0,
                        "tarjeta_credito": 0.0,
                        "recargas": 0.0,
                        "devoluciones": 0.0
                    },
                    "total_costo_inventario": 0.0,
                    "total_ventas": 0
                }
            
            resumen = resumen_por_sucursal[sucursal_id]
            resumen["total_ventas"] += 1
            
            # Procesar métodos de pago
            metodos_pago = venta.get("metodos_pago", [])
            tasa_dia = venta.get("tasa_dia", 1)
            
            for metodo in metodos_pago:
                tipo = metodo.get("tipo", "").lower()
                monto = float(metodo.get("monto", 0) or 0)
                divisa = metodo.get("divisa", "BS").upper()
                banco_id = metodo.get("banco_id")
                
                # Si es devolución (monto negativo)
                if monto < 0:
                    monto_abs = abs(monto)
                    if divisa == "BS":
                        resumen["desglose_bs"]["devoluciones"] += monto_abs
                    continue
                
                # Si es tipo "banco" y tiene banco_id, buscar tipo_metodo del banco
                if tipo == "banco" and banco_id:
                    try:
                        banco_oid = ObjectId(banco_id)
                        banco = await bancos_collection.find_one({"_id": banco_oid})
                        
                        if banco:
                            tipo_metodo = banco.get("tipo_metodo", "pago_movil")
                            
                            # Clasificar según tipo_metodo y divisa
                            if divisa == "USD":
                                if tipo_metodo == "efectivo":
                                    resumen["total_efectivo_usd"] += monto
                                    resumen["total_usd_recibido"] += monto
                                elif tipo_metodo == "zelle":
                                    resumen["total_zelle_usd"] += monto
                                    resumen["total_usd_recibido"] += monto
                                elif tipo_metodo == "vales":
                                    resumen["total_vales_usd"] += monto
                                    resumen["total_usd_recibido"] += monto
                            else:  # BS
                                if tipo_metodo == "pago_movil":
                                    resumen["desglose_bs"]["pago_movil"] += monto
                                    resumen["total_bs"] += monto
                                elif tipo_metodo == "efectivo":
                                    resumen["desglose_bs"]["efectivo"] += monto
                                    resumen["total_bs"] += monto
                                elif tipo_metodo == "tarjeta_debit":
                                    resumen["desglose_bs"]["tarjeta_debit"] += monto
                                    resumen["total_bs"] += monto
                                elif tipo_metodo == "tarjeta_credito":
                                    resumen["desglose_bs"]["tarjeta_credito"] += monto
                                    resumen["total_bs"] += monto
                                elif tipo_metodo == "recargas":
                                    resumen["desglose_bs"]["recargas"] += monto
                                    resumen["total_bs"] += monto
                    except (InvalidId, ValueError):
                        # Si el banco_id no es válido, tratar como método de pago genérico
                        if divisa == "BS":
                            resumen["total_bs"] += monto
                        elif divisa == "USD":
                            resumen["total_usd_recibido"] += monto
                else:
                    # Métodos de pago tradicionales (sin banco_id)
                    if tipo == "efectivo":
                        if divisa == "USD":
                            resumen["total_efectivo_usd"] += monto
                            resumen["total_usd_recibido"] += monto
                        else:  # BS
                            resumen["desglose_bs"]["efectivo"] += monto
                            resumen["total_bs"] += monto
                    elif tipo == "zelle":
                        if divisa == "USD":
                            resumen["total_zelle_usd"] += monto
                            resumen["total_usd_recibido"] += monto
                    elif tipo == "transferencia":
                        if divisa == "BS":
                            resumen["desglose_bs"]["pago_movil"] += monto
                            resumen["total_bs"] += monto
                    elif tipo == "tarjeta":
                        if divisa == "BS":
                            # Por defecto, tarjeta se considera débito
                            resumen["desglose_bs"]["tarjeta_debit"] += monto
                            resumen["total_bs"] += monto
                    elif tipo == "vales":
                        if divisa == "USD":
                            resumen["total_vales_usd"] += monto
                            resumen["total_usd_recibido"] += monto
            
            # Calcular costo de inventario de los items de esta venta
            items = venta.get("items", [])
            for item in items:
                codigo_producto = item.get("codigo")
                cantidad = item.get("cantidad", 0) or 0
                
                if not codigo_producto or cantidad == 0:
                    continue
                
                # Buscar costo_unitario en inventarios activos de la sucursal
                try:
                    if sucursal_id and sucursal_id != "sin_sucursal":
                        inventarios = await inventarios_collection.find({
                            "sucursal": sucursal_id,
                            "estado": "activo"
                        }).sort("fecha_creacion", -1).to_list(length=10)
                        
                        costo_unitario = None
                        for inventario in inventarios:
                            items_inv = inventario.get("items", []) or inventario.get("items_inventario", [])
                            for item_inv in items_inv:
                                if str(item_inv.get("codigo", "")).strip() == str(codigo_producto).strip():
                                    costo_unitario = float(item_inv.get("costo_unitario", 0) or 0)
                                    break
                            if costo_unitario is not None:
                                break
                        
                        if costo_unitario:
                            costo_total_item = costo_unitario * cantidad
                            resumen["total_costo_inventario"] += costo_total_item
                except Exception as e:
                    print(f"[RESUMEN-VENTAS] Error al calcular costo para {codigo_producto}: {str(e)}")
                    continue
        
        # Formatear respuesta
        resultado = {
            "ventas_por_sucursal": {}
        }
        
        for sucursal_id, datos in resumen_por_sucursal.items():
            resultado["ventas_por_sucursal"][sucursal_id] = {
                "total_efectivo_usd": round(datos["total_efectivo_usd"], 2),
                "total_zelle_usd": round(datos["total_zelle_usd"], 2),
                "total_usd_recibido": round(datos["total_usd_recibido"], 2),
                "total_vales_usd": round(datos["total_vales_usd"], 2),
                "total_bs": round(datos["total_bs"], 2),
                "desglose_bs": {
                    "pago_movil": round(datos["desglose_bs"]["pago_movil"], 2),
                    "efectivo": round(datos["desglose_bs"]["efectivo"], 2),
                    "tarjeta_debit": round(datos["desglose_bs"]["tarjeta_debit"], 2),
                    "tarjeta_credito": round(datos["desglose_bs"]["tarjeta_credito"], 2),
                    "recargas": round(datos["desglose_bs"]["recargas"], 2),
                    "devoluciones": round(datos["desglose_bs"]["devoluciones"], 2)
                },
                "total_costo_inventario": round(datos["total_costo_inventario"], 2),
                "total_ventas": datos["total_ventas"]
            }
        
        print(f"[RESUMEN-VENTAS] Resumen generado para {len(resultado['ventas_por_sucursal'])} sucursales")
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RESUMEN-VENTAS] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener resumen de ventas: {str(e)}"
        )


@router.get("/ventas", response_model=List[VentaResponse])
async def obtener_ventas_del_dia(
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal (opcional)"),
    cajero: Optional[str] = Query(None, description="Correo del usuario o nombre del cajero (opcional)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene todas las ventas del día para una fecha específica.
    Filtra por rango completo del día (00:00:00 a 23:59:59).
    Opcionalmente filtra por sucursal y/o cajero.
    Requiere autenticación.
    NO usa caché - siempre devuelve datos en tiempo real.
    """
    try:
        # Validar formato de fecha
        try:
            fecha_parsed = datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de fecha inválido. Use YYYY-MM-DD"
            )
        
        # Calcular rango del día completo (00:00:00 a 23:59:59)
        inicio_dia = fecha_parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dia = fecha_parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convertir a ISO format para comparación con fecha_hora
        inicio_dia_iso = inicio_dia.isoformat()
        fin_dia_iso = fin_dia.isoformat()
        
        print(f"[OBTENER-VENTAS] Filtrando ventas del día {fecha} (rango: {inicio_dia_iso} a {fin_dia_iso})")
        
        # Obtener colección de ventas (sin caché - siempre consulta directa)
        ventas_collection = get_collection("VENTAS")
        
        # Construir filtro con rango de fecha completo
        # Buscar por campo 'fecha' (string) O por 'fecha_hora' (datetime) dentro del rango
        condiciones_fecha = [
            # Filtro por campo 'fecha' (string) - exacto
            {"fecha": fecha}
        ]
        
        # Agregar filtro por fecha_hora (puede ser string ISO o datetime)
        # Intentar con datetime primero (más común en MongoDB)
        condiciones_fecha.append({
            "fecha_hora": {
                "$gte": inicio_dia,
                "$lte": fin_dia
            }
        })
        
        # También considerar fecha_hora como string ISO
        condiciones_fecha.append({
            "fecha_hora": {
                "$gte": inicio_dia_iso,
                "$lte": fin_dia_iso
            }
        })
        
        # Construir condiciones adicionales (sucursal y cajero)
        condiciones_adicionales = []
        
        # Si se especifica sucursal, agregar al filtro
        if sucursal:
            # Intentar convertir a ObjectId si es posible, sino usar como string
            try:
                sucursal_oid = ObjectId(sucursal)
                # Buscar por ObjectId o string
                filtro_sucursal = {
                    "$or": [
                        {"sucursal": sucursal_oid},
                        {"sucursal": sucursal}
                    ]
                }
            except (InvalidId, ValueError):
                # Si no es ObjectId válido, usar como string
                filtro_sucursal = {"sucursal": sucursal}
            
            condiciones_adicionales.append(filtro_sucursal)
        
        # Si se especifica cajero, agregar al filtro
        if cajero:
            # Buscar por campo 'cajero' o 'usuario_registro'
            filtro_cajero = {
                "$or": [
                    {"cajero": cajero},
                    {"usuario_registro": cajero}
                ]
            }
            condiciones_adicionales.append(filtro_cajero)
        
        # Construir filtro final
        if condiciones_adicionales:
            # Combinar filtro de fecha con filtros adicionales usando $and
            filtro = {
                "$and": [
                    {"$or": condiciones_fecha}
                ] + condiciones_adicionales
            }
        else:
            # Solo filtro de fecha
            filtro = {
                "$or": condiciones_fecha
            }
        
        print(f"[OBTENER-VENTAS] Filtro aplicado: {filtro}")
        
        # Buscar ventas (sin caché - consulta directa a la base de datos)
        ventas = await ventas_collection.find(filtro).sort("fecha_hora", -1).to_list(length=None)
        
        # Formatear resultados
        resultado = []
        for venta in ventas:
            venta["_id"] = str(venta["_id"])
            # Procesar cliente antes de agregar
            venta = await procesar_cliente_en_venta(venta)
            resultado.append(VentaResponse(**venta))
        
        filtros_aplicados = [f"fecha {fecha}"]
        if sucursal:
            filtros_aplicados.append(f"sucursal {sucursal}")
        if cajero:
            filtros_aplicados.append(f"cajero {cajero}")
        
        print(f"[OBTENER-VENTAS] Encontradas {len(resultado)} ventas para: {', '.join(filtros_aplicados)}")
        
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


@router.get("/ventas/usuario", response_model=VentasUsuarioResponse)
async def obtener_ventas_usuario(
    cajero: Optional[str] = Query(None, description="Correo del usuario o nombre del cajero"),
    sucursal: Optional[str] = Query(None, description="ID de la sucursal"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha de inicio en formato YYYY-MM-DD"),
    fecha_fin: Optional[str] = Query(None, description="Fecha de fin en formato YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a devolver"),
    offset: int = Query(0, ge=0, description="Número de registros a saltar (para paginación)"),
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene las ventas (facturas procesadas) con filtros opcionales.
    Permite filtrar por cajero, sucursal y rango de fechas.
    Requiere autenticación.
    
    Retorna un objeto con facturas, total, limit y offset.
    Las ventas están ordenadas por fecha_hora (más recientes primero).
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
            # Intentar convertir a ObjectId si es posible, sino usar como string
            try:
                filtro["sucursal"] = ObjectId(sucursal)
            except (InvalidId, ValueError):
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
        
        # Contar total de ventas que coinciden con el filtro
        total = await ventas_collection.count_documents(filtro)
        
        # Buscar ventas con paginación
        ventas = await ventas_collection.find(filtro).sort("fecha_hora", -1).skip(offset).limit(limit).to_list(length=limit)
        
        # Formatear resultados
        facturas = []
        for venta in ventas:
            venta["_id"] = str(venta["_id"])
            
            # Procesar cliente antes de agregar
            venta = await procesar_cliente_en_venta(venta)
            
            # Asegurar que todos los campos estén presentes
            facturas.append(VentaResponse(**venta))
        
        print(f"[OBTENER-VENTAS-USUARIO] Encontradas {len(facturas)} ventas de {total} totales")
        print(f"  - Filtros: cajero={cajero}, sucursal={sucursal}, fecha_inicio={fecha_inicio}, fecha_fin={fecha_fin}")
        print(f"  - Paginación: offset={offset}, limit={limit}")
        
        return VentasUsuarioResponse(
            facturas=facturas,
            total=total,
            limit=limit,
            offset=offset
        )
        
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


@router.post("/devolucion", response_model=VentaResponse)
async def procesar_devolucion(
    devolucion: DevolucionRequest,
    usuario: dict = Depends(get_current_user)
):
    """
    Procesa una devolución de compra.
    
    Pasos:
    1. Busca la venta original
    2. Marca la venta original como "devuelta"
    3. Devuelve stock de los items devueltos
    4. Descuenta stock de los items nuevos (si hay)
    5. Crea una nueva venta con los items nuevos
    6. Solo cobra la diferencia si el nuevo total es mayor
    """
    verificar_permiso(usuario, "agregar_cuadre")
    
    try:
        ventas_collection = get_collection("VENTAS")
        inventarios_collection = get_collection("INVENTARIOS")
        productos_collection = get_collection("PRODUCTOS")
        
        # 1. Buscar la venta original
        try:
            venta_original_oid = ObjectId(devolucion.venta_original_id)
        except InvalidId:
            raise HTTPException(
                status_code=400,
                detail="ID de venta original inválido"
            )
        
        venta_original = await ventas_collection.find_one({"_id": venta_original_oid})
        if not venta_original:
            raise HTTPException(
                status_code=404,
                detail="Venta original no encontrada"
            )
        
        # Verificar que la venta no esté ya devuelta
        if venta_original.get("estado") == "devuelta":
            raise HTTPException(
                status_code=400,
                detail="Esta venta ya fue devuelta anteriormente"
            )
        
        print(f"[DEVOLUCION] Procesando devolución de venta: {devolucion.venta_original_id}")
        
        # 2. Marcar venta original como "devuelta"
        await ventas_collection.update_one(
            {"_id": venta_original_oid},
            {
                "$set": {
                    "estado": "devuelta",
                    "fecha_devolucion": datetime.now().isoformat(),
                    "usuario_devolucion": usuario.get("correo", usuario.get("usuarioCorreo", ""))
                }
            }
        )
        print(f"[DEVOLUCION] Venta original marcada como devuelta")
        
        # 3. Devolver stock de los items devueltos
        sucursal_original = venta_original.get("sucursal", devolucion.sucursal)
        
        for item_devolver in devolucion.items_devolver:
            codigo_producto = item_devolver.codigo
            cantidad_devolver = item_devolver.cantidad
            
            if not codigo_producto:
                # Intentar obtener código del producto_id
                try:
                    producto = await productos_collection.find_one({"_id": ObjectId(item_devolver.producto_id)})
                    if producto:
                        codigo_producto = producto.get("codigo")
                except:
                    pass
            
            if codigo_producto:
                # Devolver stock al inventario
                await devolver_stock_a_inventario(
                    codigo_producto=codigo_producto,
                    cantidad=cantidad_devolver,
                    sucursal_id=sucursal_original
                )
                
                # También actualizar stock en PRODUCTOS como fallback
                try:
                    await productos_collection.update_one(
                        {"_id": ObjectId(item_devolver.producto_id)},
                        {"$inc": {"stock": cantidad_devolver}}
                    )
                except:
                    pass
        
        print(f"[DEVOLUCION] Stock devuelto para {len(devolucion.items_devolver)} items")
        
        # 4. Calcular totales de la devolución
        total_devolucion_bs = sum(item.subtotal for item in devolucion.items_devolver)
        total_devolucion_usd = sum(item.subtotal_usd or 0 for item in devolucion.items_devolver)
        
        total_nuevos_bs = sum(item.subtotal for item in devolucion.items_nuevos) if devolucion.items_nuevos else 0
        total_nuevos_usd = sum(item.subtotal_usd or 0 for item in devolucion.items_nuevos) if devolucion.items_nuevos else 0
        
        diferencia_bs = total_nuevos_bs - total_devolucion_bs
        diferencia_usd = total_nuevos_usd - total_devolucion_usd
        
        print(f"[DEVOLUCION] Totales - Devolución: {total_devolucion_bs} Bs, Nuevos: {total_nuevos_bs} Bs, Diferencia: {diferencia_bs} Bs")
        
        # 5. Si hay items nuevos, descontar stock y crear nueva venta
        if devolucion.items_nuevos and len(devolucion.items_nuevos) > 0:
            # Validar stock de items nuevos
            for item_nuevo in devolucion.items_nuevos:
                codigo_producto = item_nuevo.codigo
                cantidad_solicitada = item_nuevo.cantidad
                
                if not codigo_producto:
                    try:
                        producto = await productos_collection.find_one({"_id": ObjectId(item_nuevo.producto_id)})
                        if producto:
                            codigo_producto = producto.get("codigo")
                    except:
                        pass
                
                if codigo_producto:
                    # Validar stock disponible (usar la misma lógica que en registrar_venta)
                    inventarios = await inventarios_collection.find({
                        "sucursal": devolucion.sucursal,
                        "estado": "activo"
                    }).sort("fecha_creacion", -1).to_list(length=50)
                    
                    stock_disponible = 0
                    for inventario in inventarios:
                        items = inventario.get("items", []) or inventario.get("items_inventario", [])
                        for item in items:
                            item_codigo = item.get("codigo")
                            if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                lotes = item.get("lotes", [])
                                if lotes:
                                    for lote in lotes:
                                        stock_disponible += lote.get("cantidad", 0) or 0
                                else:
                                    stock_disponible += item.get("cantidad", 0) or 0
                                break
                    
                    if stock_disponible < cantidad_solicitada:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Stock insuficiente para {item_nuevo.nombre} (código: {codigo_producto}). Stock disponible: {stock_disponible}, solicitado: {cantidad_solicitada}"
                        )
            
            # Descontar stock de items nuevos (usar la misma lógica que registrar_venta)
            for item_nuevo in devolucion.items_nuevos:
                codigo_producto = item_nuevo.codigo
                cantidad_a_descontar = item_nuevo.cantidad
                
                if not codigo_producto:
                    try:
                        producto = await productos_collection.find_one({"_id": ObjectId(item_nuevo.producto_id)})
                        if producto:
                            codigo_producto = producto.get("codigo")
                    except:
                        pass
                
                if codigo_producto:
                    # Buscar inventarios activos
                    inventarios = await inventarios_collection.find({
                        "sucursal": devolucion.sucursal,
                        "estado": "activo"
                    }).sort("fecha_creacion", -1).to_list(length=50)
                    
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
                    
                    if item_encontrado and inventario_encontrado:
                        # Descontar stock usando FIFO (misma lógica que registrar_venta)
                        cantidad_restante = cantidad_a_descontar
                        lotes = item_encontrado.get("lotes", [])
                        
                        if lotes:
                            # Ordenar lotes por fecha de vencimiento (más antiguos primero)
                            def ordenar_lotes_fifo(lote):
                                fecha = lote.get("fecha_vencimiento")
                                if fecha:
                                    try:
                                        if isinstance(fecha, str):
                                            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
                                        else:
                                            fecha_dt = fecha
                                        return (0, fecha_dt)
                                    except:
                                        return (1, datetime.max)
                                return (2, datetime.max)
                            
                            lotes_ordenados = sorted(lotes, key=ordenar_lotes_fifo)
                            lotes_actualizados = []
                            
                            for lote in lotes_ordenados:
                                if cantidad_restante <= 0:
                                    lotes_actualizados.append(lote)
                                    continue
                                
                                cantidad_lote = lote.get("cantidad", 0) or 0
                                
                                if cantidad_lote <= cantidad_restante:
                                    cantidad_restante -= cantidad_lote
                                    # No agregar el lote si queda en 0
                                else:
                                    lote["cantidad"] = cantidad_lote - cantidad_restante
                                    cantidad_restante = 0
                                    lotes_actualizados.append(lote)
                            
                            # Actualizar lotes
                            items = inventario_encontrado.get("items", []) or inventario_encontrado.get("items_inventario", [])
                            for idx, item in enumerate(items):
                                item_codigo = item.get("codigo")
                                if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                    items[idx]["lotes"] = lotes_actualizados
                                    cantidad_total_lotes = sum(l.get("cantidad", 0) or 0 for l in lotes_actualizados)
                                    items[idx]["cantidad"] = cantidad_total_lotes
                                    break
                            
                            inventario_encontrado["items"] = items
                            await inventarios_collection.replace_one(
                                {"_id": inventario_encontrado["_id"]},
                                inventario_encontrado
                            )
                        else:
                            # No hay lotes, descontar de la cantidad del item
                            cantidad_actual = item_encontrado.get("cantidad", 0) or 0
                            nueva_cantidad = cantidad_actual - cantidad_a_descontar
                            
                            items = inventario_encontrado.get("items", []) or inventario_encontrado.get("items_inventario", [])
                            for idx, item in enumerate(items):
                                item_codigo = item.get("codigo")
                                if item_codigo and str(item_codigo).strip() == str(codigo_producto).strip():
                                    items[idx]["cantidad"] = nueva_cantidad
                                    break
                            
                            inventario_encontrado["items"] = items
                            await inventarios_collection.replace_one(
                                {"_id": inventario_encontrado["_id"]},
                                inventario_encontrado
                            )
            
            # 6. Crear nueva venta solo si hay diferencia a favor (nuevo total > devolución)
            if diferencia_bs > 0.01:  # Tolerancia para decimales
                # Validar métodos de pago si se proporcionan
                if not devolucion.metodos_pago or len(devolucion.metodos_pago) == 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Debe especificar métodos de pago. Diferencia a pagar: {diferencia_bs:.2f} Bs"
                    )
                
                # Validar que los métodos de pago cubran la diferencia
                suma_metodos_usd = 0.0
                for mp in devolucion.metodos_pago:
                    monto = mp.monto
                    divisa = mp.divisa.upper() if mp.divisa else "BS"
                    
                    if divisa == "USD":
                        suma_metodos_usd += monto
                    else:
                        suma_metodos_usd += monto / devolucion.tasa_dia if devolucion.tasa_dia > 0 else 0
                
                diferencia_usd_calculada = diferencia_bs / devolucion.tasa_dia if devolucion.tasa_dia > 0 else 0
                
                if suma_metodos_usd < diferencia_usd_calculada - 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Pago insuficiente. Diferencia: ${diferencia_usd_calculada:.2f} USD, Pagado: ${suma_metodos_usd:.2f} USD"
                    )
                
                # Generar número de factura para la nueva venta
                fecha_actual = datetime.now().strftime("%Y-%m-%d")
                ventas_hoy = await ventas_collection.count_documents({"fecha": fecha_actual})
                numero_factura = f"FAC-{fecha_actual.replace('-', '')}-{ventas_hoy + 1:04d}"
                
                # Crear nueva venta
                nueva_venta_doc = {
                    "numero_factura": numero_factura,
                    "fecha": fecha_actual,
                    "fecha_hora": datetime.now().isoformat(),
                    "items": [item.dict() for item in devolucion.items_nuevos],
                    "metodos_pago": [mp.dict() for mp in devolucion.metodos_pago],
                    "total_bs": diferencia_bs,
                    "total_usd": diferencia_usd_calculada,
                    "tasa_dia": devolucion.tasa_dia,
                    "sucursal": devolucion.sucursal,
                    "cajero": devolucion.cajero or usuario.get("correo", usuario.get("usuarioCorreo")),
                    "cliente": devolucion.cliente or venta_original.get("cliente"),
                    "notas": f"Devolución de venta {venta_original.get('numero_factura', devolucion.venta_original_id)}. {devolucion.notas or ''}",
                    "usuario_registro": usuario.get("correo", usuario.get("usuarioCorreo")),
                    "venta_devolucion_id": str(venta_original_oid),
                    "tipo": "devolucion"
                }
                
                result = await ventas_collection.insert_one(nueva_venta_doc)
                nueva_venta_id = str(result.inserted_id)
                
                print(f"[DEVOLUCION] Nueva venta creada: {numero_factura} (ID: {nueva_venta_id})")
                
                # Actualizar cuadre y saldos bancarios (usar las mismas funciones que registrar_venta)
                try:
                    await actualizar_cuadre_con_venta(
                        sucursal_id=devolucion.sucursal,
                        metodos_pago=devolucion.metodos_pago,
                        total_bs=diferencia_bs,
                        total_usd=diferencia_usd_calculada,
                        tasa_dia=devolucion.tasa_dia
                    )
                except Exception as e:
                    print(f"[DEVOLUCION] Advertencia: Error al actualizar cuadre: {str(e)}")
                
                try:
                    await actualizar_saldos_bancarios(
                        metodos_pago=devolucion.metodos_pago,
                        vuelto=None,
                        numero_factura=numero_factura,
                        venta_id=nueva_venta_id,
                        usuario=usuario
                    )
                except Exception as e:
                    print(f"[DEVOLUCION] Advertencia: Error al actualizar saldos bancarios: {str(e)}")
                
                # Retornar la nueva venta
                nueva_venta_doc["_id"] = nueva_venta_id
                nueva_venta_doc = await procesar_cliente_en_venta(nueva_venta_doc)
                return VentaResponse(**nueva_venta_doc)
            else:
                # No hay diferencia a favor, solo devolver confirmación
                print(f"[DEVOLUCION] No hay diferencia a favor. Devolución completada sin nueva venta.")
                # Retornar respuesta con la venta original marcada como devuelta
                venta_original["_id"] = str(venta_original_oid)
                venta_original["estado"] = "devuelta"
                venta_original = await procesar_cliente_en_venta(venta_original)
                return VentaResponse(**venta_original)
        else:
            # No hay items nuevos, solo devolución
            print(f"[DEVOLUCION] Solo devolución, sin items nuevos")
            # Retornar respuesta con la venta original marcada como devuelta
            venta_original["_id"] = str(venta_original_oid)
            venta_original["estado"] = "devuelta"
            venta_original = await procesar_cliente_en_venta(venta_original)
            return VentaResponse(**venta_original)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEVOLUCION] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar devolución: {str(e)}"
        )
