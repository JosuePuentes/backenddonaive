from fastapi import APIRouter, HTTPException, Body, Query, Depends
from app.schemas.auth import LoginInput, Cuadre
from app.services.users_service import login_y_token
from app.db.mongo import get_collection  # tu helper para acceder a la colección
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timedelta
import pytz
from pydantic import BaseModel
from typing import List, Optional
from fastapi import Depends
from app.core.get_current_user import get_current_user
import os
import boto3
from botocore.config import Config
from fastapi import Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pymongo import UpdateOne, InsertOne

load_dotenv()

# Configuración de Cloudflare R2 desde variables de entorno
R2_BUCKET = os.getenv("VITE_R2_BUCKET")
R2_ACCOUNT_ID = os.getenv("VITE_R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("VITE_R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("VITE_R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

s3_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
    config=Config(signature_version="s3v4")
)

router = APIRouter()

class Gasto(BaseModel):
    monto: float
    titulo: str
    descripcion: str
    localidad: str
    fecha: str  # Fecha de gasto (ej: "2025-06-23")
    tasa: Optional[float] = None
    divisa: Optional[str] = None
    fechaRegistro: Optional[datetime] = None  # Fecha de registro real (datetime)
    estado: str = "wait"
    imagenGasto: Optional[str] = None
    imagenesGasto: Optional[List[str]] = None

class CuentaPorPagar(BaseModel):
    fechaEmision: str
    fechaRecepcion: Optional[str] = None
    fechaVencimiento: Optional[str] = None  # Nuevo campo
    fechaRegistro: Optional[str] = None     # Nuevo campo
    diasCredito: int
    numeroFactura: str
    numeroControl: str
    proveedor: str
    descripcion: str
    monto: float
    retencion: Optional[float] = 0  # Nuevo campo retención
    divisa: str
    tasa: float
    estatus: str = "activa"
    usuarioCorreo: str
    farmacia: str
    imagenesCuentaPorPagar: List[str] = []  # <-- Añadir este campo

class Inventario(BaseModel):
    farmacia: str
    costo: float
    usuarioCorreo: str
    fecha: Optional[str] = None  # Ahora es opcional
    estado: str = "activo"  # Nuevo campo con valor por defecto


class Lote(BaseModel):
    """Modelo para un lote de un item"""
    numero_lote: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    cantidad: Optional[int] = None
    costo_unitario: Optional[float] = None
    precio_unitario: Optional[float] = None


class ItemInventarioUpdate(BaseModel):
    """Modelo para actualizar un item de inventario"""
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    cantidad: Optional[int] = None
    precio_unitario: Optional[float] = None
    costo_unitario: Optional[float] = None
    descripcion: Optional[str] = None
    utilidad_contable: Optional[float] = None  # Se calculará automáticamente si no se proporciona
    lotes: Optional[List[Lote]] = None  # Array de lotes


class ItemInventarioResponse(BaseModel):
    """Modelo de respuesta para un item de inventario"""
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    nombre: Optional[str] = None
    marca: Optional[str] = None
    costo: Optional[float] = None
    costo_unitario: Optional[float] = None
    precio: Optional[float] = None
    precio_unitario: Optional[float] = None
    cantidad: Optional[int] = None
    utilidad_contable: Optional[float] = None
    lotes: Optional[List[dict]] = None  # Array de lotes
    _id: Optional[str] = None
    
    class Config:
        extra = "allow"  # Permite campos adicionales que puedan existir en los items


class ProductoExcel(BaseModel):
    codigo: str
    nombre: str
    precio: float
    stock: int
    costo: Optional[float] = None
    descripcion: Optional[str] = None


class UploadExcelRequest(BaseModel):
    sucursal: str
    productos: List[ProductoExcel]


class UploadExcelResponse(BaseModel):
    message: str
    sucursal: str
    total_procesados: int
    productos_agregados: int
    productos_actualizados: int
    productos_con_error: int
    inventario_id: Optional[str] = None
    errores: Optional[List[str]] = None

@router.get("/")
async def root():
    return {"message": "API funcionando"}

@router.get("/usuarios")
async def obtener_usuarios(usuario_actual: dict = Depends(get_current_user)):
    """
    Endpoint para obtener todos los usuarios.
    Requiere autenticación.
    """
    try:
        collection = get_collection("USUARIOS")
        usuarios = await collection.find({}).to_list(length=None)
        
        # Convertir _id a string y limpiar datos sensibles
        usuarios_limpios = []
        for usuario in usuarios:
            usuario["_id"] = str(usuario["_id"])
            # Remover la contraseña por seguridad
            if "contraseña" in usuario:
                del usuario["contraseña"]
            usuarios_limpios.append(usuario)
        
        return usuarios_limpios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login")
async def login_user(data: LoginInput):
    """
    Login de usuario.
    Devuelve el token y el usuario con permisos actualizados desde la base de datos.
    """
    try:
        print(f"[LOGIN] Intento de login para correo: {data.correo}")
        
        # Intentar autenticar usuario
        resultado = await login_y_token(data.correo, data.contraseña, return_user=True)
        
        # Verificar que el resultado no sea None
        if resultado is None:
            print(f"[LOGIN] ERROR: Credenciales incorrectas para {data.correo}")
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        
        # Desempaquetar resultado
        usuario, token = resultado
        
        if not token or not usuario:
            print(f"[LOGIN] ERROR: Token o usuario vacío para {data.correo}")
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        
        print(f"[LOGIN] Usuario autenticado: {data.correo}, token generado: {token[:20]}...")
        
        # Asegurar que los permisos vengan desde la BD (ya vienen, pero lo verificamos)
        try:
            usuarios_collection = get_collection("USUARIOS")
            usuario_actualizado = await usuarios_collection.find_one(
                {"correo": data.correo},
                {"contraseña": 0}  # Excluir contraseña
            )
            
            if usuario_actualizado:
                # Usar el usuario actualizado desde la BD para tener permisos frescos
                usuario_actualizado["_id"] = str(usuario_actualizado["_id"])
                print(f"[LOGIN] Usuario actualizado encontrado, retornando respuesta")
                return {
                    "access_token": token,
                    "token_type": "bearer",
                    "usuario": usuario_actualizado
                }
        except Exception as e:
            print(f"[LOGIN] Advertencia: Error al obtener usuario actualizado: {str(e)}")
            # Continuar con el usuario original si hay error
        
        # Fallback al usuario original si no se encuentra actualizado
        if "_id" in usuario:
            usuario["_id"] = str(usuario["_id"])
        # Remover contraseña si está presente
        usuario.pop("contraseña", None)
        
        print(f"[LOGIN] Retornando respuesta con usuario original")
        return {
            "access_token": token,
            "token_type": "bearer",
            "usuario": usuario
        }
        
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        print(f"[LOGIN] ERROR CRÍTICO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor al procesar el login: {str(e)}"
        )


@router.get("/auth/me")
async def obtener_usuario_actual(usuario: dict = Depends(get_current_user)):
    """
    Obtener información del usuario actual autenticado.
    Devuelve el usuario completo con permisos actualizados desde la base de datos.
    Requiere autenticación (token JWT).
    """
    try:
        usuarios_collection = get_collection("USUARIOS")
        
        # Obtener usuario actualizado desde la BD para tener permisos frescos
        correo = usuario.get("correo")
        if not correo:
            raise HTTPException(
                status_code=401,
                detail="No se pudo identificar al usuario"
            )
        
        usuario_actualizado = await usuarios_collection.find_one(
            {"correo": correo},
            {"contraseña": 0}  # Excluir contraseña
        )
        
        if not usuario_actualizado:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado"
            )
        
        # Formatear respuesta
        usuario_actualizado["_id"] = str(usuario_actualizado["_id"])
        
        return usuario_actualizado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OBTENER-USUARIO-ACTUAL] Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener usuario actual: {str(e)}"
        )

@router.post("/admin/reset-password")
async def reset_admin_password(data: dict = Body(...)):
    """
    Endpoint para cambiar la contraseña del admin.
    Este endpoint es temporal para reseteo de contraseñas.
    """
    try:
        from app.core.auth import hashear_contraseña
        
        password = data.get("password")
        if not password:
            raise HTTPException(status_code=400, detail="La contraseña es requerida")
        
        usuarios_collection = get_collection("USUARIOS")
        
        # Buscar y actualizar el usuario admin
        hashed_password = hashear_contraseña(password)
        result = await usuarios_collection.update_one(
            {"correo": "admin@gmail.com"},
            {"$set": {"contraseña": hashed_password}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="No se encontró el usuario admin o no se realizaron cambios")
        
        return {
            "message": "Contraseña actualizada exitosamente",
            "correo": "admin@gmail.com",
            "nueva_contraseña": password
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cambiar la contraseña: {str(e)}")

@router.get("/cuadres")
async def obtener_cuadres(
    farmacia: Optional[str] = Query(None),
    fechaInicio: Optional[str] = Query(None),
    fechaFin: Optional[str] = Query(None)
):
    db = get_collection("CUADRES").database
    cuadres = []
    # Si no se especifica farmacia, buscar en todas las colecciones CUADRES-*
    if not farmacia:
        colecciones = await db.list_collection_names()
        for nombre in colecciones:
            if nombre.startswith("CUADRES-"):
                collection = db[nombre]
                filtro = {}
                if fechaInicio and fechaFin:
                    filtro["dia"] = {"$gte": fechaInicio, "$lte": fechaFin}
                docs = await collection.find(filtro).to_list(length=None)
                for r in docs:
                    r["_id"] = str(r["_id"])
                    r["codigoFarmacia"] = nombre.replace("CUADRES-", "")
                cuadres.extend(docs)
    else:
        nombre = f"CUADRES-{farmacia}"
        collection = db[nombre]
        filtro = {}
        if fechaInicio and fechaFin:
            filtro["dia"] = {"$gte": fechaInicio, "$lte": fechaFin}
        docs = await collection.find(filtro).to_list(length=None)
        for r in docs:
            r["_id"] = str(r["_id"])
            r["codigoFarmacia"] = farmacia
        cuadres.extend(docs)
    return cuadres

@router.get("/cuadres/all")
async def obtener_todos_los_cuadres():
    db = get_collection("CUADRES").database  # Obtener la instancia de la base de datos
    colecciones = await db.list_collection_names()
    cuadres = []
    for nombre in colecciones:
        if nombre.startswith("CUADRES-"):
            collection = db[nombre]
            docs = await collection.find({}).to_list(length=None)
            for r in docs:
                r["_id"] = str(r["_id"])
                # Extraer el código de farmacia del nombre de la colección
                r["codigoFarmacia"] = nombre.replace("CUADRES-", "")
            cuadres.extend(docs)
    return cuadres

@router.get("/cuadres/{farmacia_id}")
async def obtener_cuadres_farmacia(farmacia_id: str):
    try:
        collection = get_collection(f"CUADRES-{farmacia_id}")
        resultados = await collection.find({}).to_list(1000)
        for r in resultados:
            r["_id"] = str(r["_id"])
        return resultados
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agg/cuadre/{farmacia}")
async def agregar_cuadre(farmacia: str, cuadre: Cuadre):
    try:
        collection = get_collection(f"CUADRES-{farmacia}")
        cuadre_dict = cuadre.dict()
        # Forzar estado a 'wait' siempre
        cuadre_dict["estado"] = "wait"
        diferencia = cuadre_dict.get("diferenciaUsd", 0)
        cuadre_dict["sobranteUsd"] = diferencia if diferencia > 0 else 0
        cuadre_dict["faltanteUsd"] = abs(diferencia) if diferencia < 0 else 0
        cuadre_dict["cajeroId"] = cuadre.cajeroId
        # Agregar fecha y hora actual de Venezuela
        venezuela_tz = pytz.timezone("America/Caracas")
        now_ve = datetime.now(venezuela_tz)
        cuadre_dict["fecha"] = now_ve.strftime("%Y-%m-%d")
        cuadre_dict["hora"] = now_ve.strftime("%H:%M:%S")
        # Validar que valesUsd esté presente (si no, poner 0)
        if "valesUsd" not in cuadre_dict or cuadre_dict["valesUsd"] is None:
            cuadre_dict["valesUsd"] = 0
        # Eliminar campo imagenCuadre si existe (deprecated)
        if "imagenCuadre" in cuadre_dict:
            cuadre_dict.pop("imagenCuadre")
        # Limpieza robusta de imagenesCuadre antes de validar
        imagenes = cuadre_dict.get("imagenesCuadre", None)
        if isinstance(imagenes, list):
            imagenes = [x for x in imagenes if isinstance(x, str) and x.strip()]
            cuadre_dict["imagenesCuadre"] = imagenes
        if not isinstance(imagenes, list) or not (1 <= len(imagenes) <= 4):
            raise HTTPException(status_code=400, detail="El campo 'imagenesCuadre' debe ser un array de 1 a 3 strings no vacíos.")
        # ...existing code...
        result = collection.insert_one(cuadre_dict)
        return {"message": "Cuadre guardado", "result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cuadres")
async def agregar_cuadre(cuadre: Cuadre):
    try:
        collection = get_collection("CUADRES")
        cuadre_dict = cuadre.dict()
        # Si viene 'dia' del frontend, guárdalo como 'fechaCajero', pero NO como 'dia' del cuadre
        if hasattr(cuadre, 'dia') and cuadre.dia:
            cuadre_dict["fechaCajero"] = cuadre.dia
        else:
            cuadre_dict["fechaCajero"] = None
        # El campo 'dia' real del cuadre es la fecha actual de Venezuela
        venezuela_tz = pytz.timezone("America/Caracas")
        now_ve = datetime.now(venezuela_tz)
        cuadre_dict["dia"] = now_ve.strftime("%Y-%m-%d")
        # Hora
        if hasattr(cuadre, 'hora') and cuadre.hora:
            cuadre_dict["hora"] = cuadre.hora
        else:
            cuadre_dict["hora"] = now_ve.strftime("%H:%M:%S")
        cuadre_dict["estado"] = "wait"
        # Eliminar el campo 'fecha' si existe para evitar duplicidad
        if "fecha" in cuadre_dict:
            cuadre_dict.pop("fecha")
        # Eliminar campo imagenCuadre si existe (deprecated)
        if "imagenCuadre" in cuadre_dict:
            cuadre_dict.pop("imagenCuadre")
        # Limpieza robusta de imagenesCuadre antes de validar
        imagenes = cuadre_dict.get("imagenesCuadre", None)
        if isinstance(imagenes, list):
            imagenes = [x for x in imagenes if isinstance(x, str) and x.strip()]
            cuadre_dict["imagenesCuadre"] = imagenes
        if not isinstance(imagenes, list) or not (1 <= len(imagenes) <= 4):
            raise HTTPException(status_code=400, detail="El campo 'imagenesCuadre' debe ser un array de 1 a 4 strings no vacíos.")
        result = await collection.insert_one(cuadre_dict)
        return {"message": "Cuadre agregado exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/farmacias")
async def get_farmacias():
    collection = get_collection("FARMACIAS")
    # Obtener todos los documentos y construir un dict {id: nombre}
    docs = await collection.find({}, {"_id": 0}).to_list(length=None)
    # Si los docs son tipo [{id: '01', nombre: 'Santa Elena'}, ...], conviértelos a dict
    farmacias = {}
    for doc in docs:
        # Si el doc tiene 'id' y 'nombre', usa eso
        if 'id' in doc and 'nombre' in doc:
            farmacias[doc['id']] = doc['nombre']
        # Si el doc tiene otras claves, las agrega
        else:
            for k, v in doc.items():
                if k != '_id':
                    farmacias[k] = v
    return {"farmacias": farmacias}

@router.post("/cuadres/{farmacia_id}/{dia}/{cajaNumero}/estado")
async def actualizar_estado_cuadre(farmacia_id: str, dia: str, cajaNumero: int, estado: str = Body(..., embed=True)):
    try:
        collection = get_collection(f"CUADRES-{farmacia_id}")
        # Buscar por número (int) para cajaNumero
        result = await collection.update_one(
            {"dia": dia, "cajaNumero": int(cajaNumero)},
            {"$set": {"estado": estado}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Cuadre no encontrado o sin cambios")
        return {"message": f"Estado actualizado a {estado}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/cuadres/{farmacia_id}/{cuadre_id}/estado")
async def actualizar_estado_cuadre_por_id(farmacia_id: str, cuadre_id: str, data: dict = Body(...)):
    try:
        estado = data.get("estado")
        costo = data.get("costo", None)
        update_fields = {"estado": estado}
        if costo is not None:
            update_fields["costo"] = float(costo)
        collection = get_collection(f"CUADRES-{farmacia_id}")
        result = await collection.update_one(
            {"_id": ObjectId(cuadre_id)},
            {"$set": update_fields}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Cuadre no encontrado o sin cambios")
        return {"message": f"Estado actualizado a {estado}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/cuadres/{farmacia_id}/{dia}/{cajaNumero}/cajero")
async def actualizar_cajero_cuadre(farmacia_id: str, dia: str, cajaNumero: int, cajero: str = Body(..., embed=True)):
    try:
        collection = get_collection(f"CUADRES-{farmacia_id}")
        result = await collection.update_one(
            {"dia": dia, "cajaNumero": int(cajaNumero)},
            {"$set": {"cajero": cajero}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Cuadre no encontrado o sin cambios")
        return {"message": f"Cajero actualizado a {cajero}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cajeros")
async def get_cajeros():
    collection = get_collection("CAJERO")
    docs = await collection.find({}).to_list(length=None)
    # Convertir _id a string para el frontend
    for doc in docs:
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
    return docs

@router.post("/gastos")
async def agregar_gasto(gasto: Gasto):
    try:
        collection = get_collection("GASTOS")
        gasto_dict = gasto.dict()
        # Validación robusta de imagenesGasto
        imagenes = gasto_dict.get("imagenesGasto", None)
        if imagenes is not None:
            if isinstance(imagenes, list):
                imagenes = [x for x in imagenes if isinstance(x, str) and x.strip()]
            else:
                imagenes = []
            gasto_dict["imagenesGasto"] = imagenes
            if not (1 <= len(imagenes) <= 4):
                raise HTTPException(status_code=400, detail="El campo 'imagenesGasto' debe ser un array de 1 a 3 strings no vacíos.")
        else:
            gasto_dict["imagenesGasto"] = []
        # Guardar la fecha de registro (Venezuela) y la fecha enviada por el usuario
        venezuela_tz = pytz.timezone("America/Caracas")
        gasto_dict["fechaRegistro"] = datetime.now(venezuela_tz)
        # fecha ya viene como string ("2025-06-23")
        gasto_dict["estado"] = gasto_dict.get("estado", "wait")
        result = await collection.insert_one(gasto_dict)
        return {"message": "Gasto agregado exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gastos")
async def obtener_gastos(
    localidad: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    estado: Optional[str] = None
):
    try:
        collection = get_collection("GASTOS")
        filtro = {}
        if localidad:
            filtro["localidad"] = localidad
        if fecha_inicio and fecha_fin:
            filtro["fecha"] = {"$gte": fecha_inicio, "$lte": fecha_fin}
        if estado:
            filtro["estado"] = estado
        resultados = await collection.find(filtro).to_list(1000)
        for r in resultados:
            r["_id"] = str(r["_id"])
        return resultados
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/gastos/estado")
async def actualizar_estado_gasto(data: dict = Body(...)):
    try:
        try:
            gasto_id = ObjectId(data.get("id"))
        except InvalidId:
            raise HTTPException(status_code=400, detail="ID inválido")

        nuevo_estado = data.get("estado")

        if not nuevo_estado:
            raise HTTPException(status_code=400, detail="Faltan campos obligatorios: estado")

        collection = get_collection("GASTOS")
        result = await collection.update_one(
            {"_id": gasto_id},
            {"$set": {"estado": nuevo_estado}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Gasto no encontrado o sin cambios")

        return {"message": f"Estado del gasto actualizado a {nuevo_estado}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gastos/total")
async def obtener_total_gastos_por_farmacia():
    try:
        collection = get_collection("GASTOS")
        pipeline = [
            {"$match": {"monto": {"$gte": 0}}},  # Exclude negative values
            {"$group": {"_id": "$localidad", "totalGastos": {"$sum": "$monto"}}}
        ]
        resultados = await collection.aggregate(pipeline).to_list(length=None)
        # Convertir el resultado a un diccionario {localidad: totalGastos}
        gastos_por_farmacia = {r["_id"]: r["totalGastos"] for r in resultados}
        return gastos_por_farmacia
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cajeros")
async def crear_cajero(cajero: dict = Body(...)):
    try:
        collection = get_collection("CAJERO")
        # Procesar comision como float
        cajero["comision"] = float(cajero.get("comision", 0))  # Default commission
        cajero["estado"] = cajero.get("estado", "activo")  # Default state
        # Limpia tipocomision: elimina strings vacíos, pero si es lista vacía, la guarda como []
        if "tipocomision" in cajero:
            if isinstance(cajero["tipocomision"], list):
                cajero["tipocomision"] = [t for t in cajero["tipocomision"] if t]
                # Si queda vacía, se guarda como [] (no se elimina el campo)
            elif not cajero["tipocomision"]:
                cajero["tipocomision"] = []
        result = await collection.insert_one(cajero)
        return {"message": "Cajero creado exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/cajeros/{cajero_id}")
async def actualizar_cajero(cajero_id: str, cajero: dict = Body(...)):
    try:
        collection = get_collection("CAJERO")
        print(f"Actualizando cajero con ID: {cajero_id} con datos: {cajero}")

        # Convert _id to ObjectId
        try:
            cajero["_id"] = ObjectId(cajero["_id"])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid _id format")

        # Limpia tipocomision: elimina strings vacíos, pero si es lista vacía, la guarda como []
        if "tipocomision" in cajero:
            if isinstance(cajero["tipocomision"], list):
                cajero["tipocomision"] = [t for t in cajero["tipocomision"] if t]
                # Si queda vacía, se guarda como [] (no se elimina el campo)
            elif not cajero["tipocomision"]:
                cajero["tipocomision"] = []

        # Map field names to match database schema
        mapped_cajero = {
            "NOMBRE": cajero.get("nombre"),
            "ID": cajero.get("id"),
            "FARMACIAS": cajero.get("FARMACIAS"),
            "comision": float(cajero.get("comision", 0)),
            "estado": cajero.get("estado"),
            "tipocomision": cajero.get("tipocomision", None),
        }
        # Agrega campos extendidos si existen
        for campo in ["turno", "especial", "extra"]:
            if campo in cajero:
                mapped_cajero[campo] = cajero[campo]
        # Elimina campos None para no sobreescribir con null
        mapped_cajero = {k: v for k, v in mapped_cajero.items() if v is not None}

        # Perform the update
        result = await collection.update_one(
            {"_id": ObjectId(cajero_id)},
            {"$set": mapped_cajero}
        )
        print(f"Resultado de la actualización: {result.raw_result}")
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Cajero no encontrado o sin cambios")
        return {"message": "Cajero actualizado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comisiones")
async def obtener_comisiones_por_turno(
    startDate: str = Query(...),
    endDate: str = Query(...)
): 
    try:
        db = get_collection("CUADRES").database
        colecciones = await db.list_collection_names()
        colecciones_farmacias = [nombre for nombre in colecciones if nombre.startswith("CUADRES-")]

        comisiones_planas = []

        for nombre_coleccion in colecciones_farmacias:
            collection = db[nombre_coleccion]
            pipeline = [
                {
                    "$match": {
                        "dia": {"$gte": startDate, "$lte": endDate},
                        "estado": "verified"
                    }
                },
                {
                    "$lookup": {
                        "from": "CAJERO",
                        "localField": "cajeroId",
                        "foreignField": "ID",
                        "as": "cajeroInfo",
                    }
                },
                {"$unwind": "$cajeroInfo"},
                {
                    "$project": {
                        "turno": 1,
                        "dia": 1,
                        "totalVentas": {"$divide": ["$totalCajaSistemaBs", {"$ifNull": ["$tasa", 1]}]},
                        "nombre": "$cajeroInfo.NOMBRE",
                        "cajeroId": "$cajeroId",
                        "farmacias": "$cajeroInfo.FARMACIAS",
                        "comisionPorcentaje": "$cajeroInfo.comision",
                        "tipocomision": "$cajeroInfo.tipocomision",
                        "sobrante": {"$ifNull": ["$sobranteUsd", 0]},
                        "faltante": {"$ifNull": ["$faltanteUsd", 0]}
                    }
                }
            ]
            resultados = await collection.aggregate(pipeline).to_list(length=None)
            # Agrupar por (turno, dia) para sumar ventas y obtener cajeros únicos
            agrupados = {}
            for r in resultados:
                if r.get("tipocomision") and ("Turno" in r["tipocomision"] if isinstance(r["tipocomision"], list) else r["tipocomision"] == "Turno"):
                    key = (r["turno"], r["dia"])
                    if key not in agrupados:
                        agrupados[key] = {"totalVentas": 0, "cajeros": []}
                    agrupados[key]["totalVentas"] += r["totalVentas"]
                    agrupados[key]["cajeros"].append({
                        "NOMBRE": r.get("nombre"),
                        "cajeroId": r.get("cajeroId"),
                        "farmacias": r.get("farmacias"),
                        "comisionPorcentaje": r.get("comisionPorcentaje"),
                        "turno": r.get("turno"),
                        "dia": r.get("dia"),
                        "sobrante": r.get("sobrante", 0),
                        "faltante": r.get("faltante", 0)
                    })
            # Para cada grupo, calcular la venta total del turno y aplicar el porcentaje de comisión INDIVIDUAL de cada cajero
            for (turno, dia), data in agrupados.items():
                total_ventas = data["totalVentas"]
                for cajero in data["cajeros"]:
                    comision_porcentaje = float(cajero.get("comisionPorcentaje") or 0)
                    comision = (total_ventas * comision_porcentaje) / 100
                    comisiones_planas.append({
                        "NOMBRE": cajero["NOMBRE"],
                        "cajeroId": cajero["cajeroId"],
                        "farmacias": cajero["farmacias"],
                        "comisionPorcentaje": cajero["comisionPorcentaje"],
                        "turno": cajero["turno"],
                        "dia": cajero["dia"],
                        "totalVentas": total_ventas,
                        "comision": comision,
                        "sobrante": cajero.get("sobrante", 0),
                        "faltante": cajero.get("faltante", 0)
                    })
        return comisiones_planas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comisiones/especial")
async def obtener_total_ventas_especial(
    startDate: str = Query(...),
    endDate: str = Query(...)
):
    try:
        db = get_collection("CUADRES").database
        colecciones = await db.list_collection_names()
        colecciones_farmacias = [nombre for nombre in colecciones if nombre.startswith("CUADRES-")]

        # Obtener todos los cajeros y mapear por farmacia
        cajeros_collection = get_collection("CAJERO")
        cajeros = await cajeros_collection.find({}).to_list(length=None)
        # Mapeo: {codigo_farmacia: [cajero, ...]}
        farmacias_cajeros = {}
        for cajero in cajeros:
            farmacias = cajero.get("FARMACIAS", {})
            if isinstance(farmacias, dict):
                for cod in farmacias.keys():
                    if cod not in farmacias_cajeros:
                        farmacias_cajeros[cod] = []
                    farmacias_cajeros[cod].append(cajero)
            elif isinstance(farmacias, list):
                for cod in farmacias:
                    if cod not in farmacias_cajeros:
                        farmacias_cajeros[cod] = []
                    farmacias_cajeros[cod].append(cajero)

        cajeros_especiales = []
        total_ventas_especial = 0

        for nombre_coleccion in colecciones_farmacias:
            codigo_farmacia = nombre_coleccion.replace("CUADRES-", "")
            collection = db[nombre_coleccion]
            pipeline = [
                {
                    "$match": {
                        "dia": {"$gte": startDate, "$lte": endDate},
                        "estado": "verified"
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "totalVentas": {"$sum": {"$divide": ["$totalCajaSistemaBs", {"$ifNull": ["$tasa", 0]}]}},
                    }
                }
            ]
            resultados = await collection.aggregate(pipeline).to_list(length=None)
            total_farmacia = resultados[0]["totalVentas"] if resultados else 0
            total_ventas_especial += total_farmacia

            # Buscar TODOS los cajeros especiales para esta farmacia
            cajeros_farmacia = farmacias_cajeros.get(codigo_farmacia, [])
            cajeros_especiales_farmacia = [
                c for c in cajeros_farmacia if "Especial" in (c.get("tipocomision") or [])
            ]
            for cajero_especial in cajeros_especiales_farmacia:
                cajeros_especiales.append({
                    "cajero": cajero_especial.get("NOMBRE"),
                    "cajeroId": cajero_especial.get("ID"),
                    "farmacias": cajero_especial.get("FARMACIAS", {}),
                    "totalVentas": total_farmacia,
                    "comisionPorcentaje": cajero_especial.get("comision", 0)
                })

        return {
            "totalVentasEspecial": total_ventas_especial,
            "cajeros": cajeros_especiales
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cuentas-por-pagar")
async def agregar_cuenta_por_pagar(cuenta: CuentaPorPagar,usuario: dict = Depends(get_current_user)):
    try:
        collection = get_collection("CUENTAS_POR_PAGAR")
        cuenta_dict = cuenta.dict()
        # Convertir fechas a datetime si es necesario
        cuenta_dict["fechaEmision"] = datetime.strptime(cuenta.fechaEmision, "%Y-%m-%d")
        if cuenta.fechaRecepcion:
            cuenta_dict["fechaRecepcion"] = datetime.strptime(cuenta.fechaRecepcion, "%Y-%m-%d")
        if cuenta.fechaVencimiento:
            cuenta_dict["fechaVencimiento"] = datetime.strptime(cuenta.fechaVencimiento, "%Y-%m-%d")
        # Fecha de registro: si viene, úsala, si no, pon la actual
        if cuenta.fechaRegistro:
            cuenta_dict["fechaRegistro"] = datetime.strptime(cuenta.fechaRegistro, "%Y-%m-%d")
        else:
            venezuela_tz = pytz.timezone("America/Caracas")
            cuenta_dict["fechaRegistro"] = datetime.now(venezuela_tz)
        cuenta_dict["estatus"] = "wait"
        cuenta_dict["usuarioCorreo"] = usuario.get("correo", "")
        # Validación robusta de imagenesCuentaPorPagar
        imagenes = cuenta_dict.get("imagenesCuentaPorPagar", None)
        if imagenes is not None:
            if isinstance(imagenes, list):
                imagenes = [x for x in imagenes if isinstance(x, str) and x.strip()]
            else:
                imagenes = []
            if len(imagenes) > 3:
                raise HTTPException(status_code=400, detail="El campo 'imagenesCuentaPorPagar' debe tener máximo 3 imágenes.")
            cuenta_dict["imagenesCuentaPorPagar"] = imagenes
        else:
            cuenta_dict["imagenesCuentaPorPagar"] = []
        result = await collection.insert_one(cuenta_dict)
        return {"message": "Cuenta por pagar registrada exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cuentas-por-pagar")
async def listar_cuentas_por_pagar(usuario: dict = Depends(get_current_user)):
    print(usuario)
    try:
        collection = get_collection("CUENTAS_POR_PAGAR")
        cuentas = await collection.find({}).to_list(length=None)
        for c in cuentas:
            c["_id"] = str(c["_id"])
            if isinstance(c["fechaEmision"], datetime):
                c["fechaEmision"] = c["fechaEmision"].strftime("%Y-%m-%d")
            if "fechaRecepcion" in c and isinstance(c["fechaRecepcion"], datetime):
                c["fechaRecepcion"] = c["fechaRecepcion"].strftime("%Y-%m-%d")
            # Normaliza monto a USD
            if c.get("divisa") == "Bs":
                try:
                    tasa = float(c.get("tasa", 1)) or 1
                    c["montoUsd"] = float(c["monto"]) / tasa
                except Exception:
                    c["montoUsd"] = 0
            else:
                c["montoUsd"] = float(c["monto"])
        return cuentas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/cuentas-por-pagar/{id}/estatus")
async def actualizar_estatus_cuenta_por_pagar(id: str, data: dict = Body(...)):
    try:
        nuevo_estatus = data.get("estatus")
        if not nuevo_estatus:
            raise HTTPException(status_code=400, detail="Falta el campo 'estatus'")
        collection = get_collection("CUENTAS_POR_PAGAR")
        result = await collection.update_one({"_id": ObjectId(id)}, {"$set": {"estatus": nuevo_estatus}})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Cuenta por pagar no encontrada o sin cambios")
        return {"message": f"Estatus actualizado a {nuevo_estatus}"}
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/inventarios")
async def agregar_inventario(data: Inventario, usuario: dict = Depends(get_current_user)):
    print(f"Usuario actual: {usuario}")
    print(f"Datos del inventario: {data}")
    try:
        collection = get_collection("INVENTARIOS")
        inventario_dict = data.dict()
        inventario_dict["usuarioCorreo"] = usuario.get("usuarioCorreo", data.usuarioCorreo)
        inventario_dict["fecha"] = datetime.now().strftime("%Y-%m-%d")
        inventario_dict["estado"] = "activo"  # Siempre activo al crear
        
        # Insertar inventario primero
        result = await collection.insert_one(inventario_dict)
        inventario_id = str(result.inserted_id)
        
        # ✅ CRÍTICO: Agregar inventario_id a todos los items del inventario
        items = inventario_dict.get("items", [])
        if items:
            # Optimización: hacer un solo update con todos los campos
            update_fields = {}
            for idx in range(len(items)):
                update_fields[f"items.{idx}.inventario_id"] = inventario_id
            
            await collection.update_one(
                {"_id": ObjectId(inventario_id)},
                {"$set": update_fields}
            )
            print(f"[AGREGAR-INVENTARIO] inventario_id agregado a {len(items)} items")
        
        return {"message": "Inventario registrado exitosamente", "id": inventario_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inventarios")
async def listar_inventarios(
    usuario: dict = Depends(get_current_user),
    incluir_eliminados: bool = Query(False, description="Incluir inventarios eliminados")
):
    """
    Lista todos los inventarios.
    Por defecto, solo muestra inventarios activos (excluye los eliminados).
    Use incluir_eliminados=true para ver también los eliminados.
    """
    try:
        collection = get_collection("INVENTARIOS")
        
        # Construir query de filtrado
        query = {}
        if not incluir_eliminados:
            # Filtrar solo inventarios activos (no eliminados)
            query["estado"] = {"$ne": "eliminado"}
        
        inventarios = await collection.find(query).to_list(length=None)
        for inv in inventarios:
            inv["_id"] = str(inv["_id"])
        return inventarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/inventarios/upload-excel", response_model=UploadExcelResponse)
async def upload_excel_inventarios(
    data: dict = Body(...),
    usuario: dict = Depends(get_current_user)
):
    """
    Sube productos desde Excel y los crea o actualiza según código y sucursal.
    Asocia cada producto a la sucursal especificada.
    
    Formato esperado:
    {
      "sucursal": "01",
      "productos": [
        {
          "codigo": "PROD001",
          "nombre": "Producto ejemplo",
          "precio": 100.0,
          "stock": 50,
          "costo": 80.0,
          "descripcion": "Descripción opcional"
        }
      ]
    }
    """
    import sys
    try:
        # Log inicial para debugging
        print(f"[UPLOAD-EXCEL] Iniciando proceso. Tipo de data: {type(data)}")
        print(f"[UPLOAD-EXCEL] Keys en data: {list(data.keys()) if isinstance(data, dict) else 'No es dict'}")
        print(f"[UPLOAD-EXCEL] Tiene sucursal: {'sucursal' in data if isinstance(data, dict) else False}")
        print(f"[UPLOAD-EXCEL] Tiene productos: {'productos' in data if isinstance(data, dict) else False}")
        
        if isinstance(data, dict) and "productos" in data:
            productos_count = len(data.get("productos", []))
            print(f"[UPLOAD-EXCEL] Cantidad de productos: {productos_count}")
            if productos_count > 0:
                primer_producto = data["productos"][0]
                print(f"[UPLOAD-EXCEL] Primer producto keys: {list(primer_producto.keys()) if isinstance(primer_producto, dict) else 'No es dict'}")
        
        # Validar estructura básica
        if not isinstance(data, dict):
            print(f"[UPLOAD-EXCEL] ERROR: data no es dict, es {type(data)}")
            raise HTTPException(status_code=422, detail="Los datos deben ser un objeto JSON")
        
        # Validar campos requeridos
        if "sucursal" not in data or not data.get("sucursal"):
            print(f"[UPLOAD-EXCEL] ERROR: Falta campo 'sucursal'")
            raise HTTPException(status_code=422, detail="El campo 'sucursal' es requerido")
        
        if "productos" not in data:
            print(f"[UPLOAD-EXCEL] ERROR: Falta campo 'productos'")
            raise HTTPException(
                status_code=422, 
                detail="El campo 'productos' es requerido y debe ser un array"
            )
        
        if not isinstance(data.get("productos"), list):
            print(f"[UPLOAD-EXCEL] ERROR: 'productos' no es una lista, es {type(data.get('productos'))}")
            raise HTTPException(
                status_code=422, 
                detail="El campo 'productos' debe ser un array"
            )
        
        if len(data.get("productos", [])) == 0:
            print(f"[UPLOAD-EXCEL] ERROR: Array 'productos' está vacío")
            raise HTTPException(status_code=422, detail="El array 'productos' no puede estar vacío")
        
        # Convertir a modelo Pydantic para validación
        from pydantic import ValidationError
        try:
            print(f"[UPLOAD-EXCEL] Intentando validar con Pydantic...")
            request_data = UploadExcelRequest(**data)
            print(f"[UPLOAD-EXCEL] Validación Pydantic exitosa")
        except ValidationError as e:
            # Si falla la validación de Pydantic, proporcionar mensaje más claro
            print(f"[UPLOAD-EXCEL] ERROR de validación Pydantic: {e}")
            errors = []
            for error in e.errors():
                field = " -> ".join(str(x) for x in error.get("loc", []))
                msg = error.get("msg", "Error de validación")
                errors.append(f"{field}: {msg}")
            error_msg = f"Error de validación: {'; '.join(errors)}"
            print(f"[UPLOAD-EXCEL] {error_msg}")
            raise HTTPException(
                status_code=422,
                detail=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            print(f"[UPLOAD-EXCEL] ERROR inesperado en validación: {error_msg}")
            raise HTTPException(status_code=422, detail=f"Error de validación: {error_msg}")
        
        # Usar el modelo validado
        data = request_data
        productos_collection = get_collection("PRODUCTOS")
        
        # Si no existe PRODUCTOS, usar INVENTARIOS
        try:
            await productos_collection.find_one({})
        except Exception as e:
            print(f"Error accediendo a PRODUCTOS, usando INVENTARIOS: {str(e)}")
            productos_collection = get_collection("INVENTARIOS")
        
        productos_agregados = 0
        productos_actualizados = 0
        productos_con_error = 0
        errores = []
        
        # Lista para almacenar los items del inventario
        items_inventario = []
        costo_total_inventario = 0.0
        
        # OPTIMIZACIÓN: Obtener todos los productos existentes en una sola query
        codigos_productos = [p.codigo for p in data.productos]
        productos_existentes_query = {
            "codigo": {"$in": codigos_productos},
            "sucursal": data.sucursal
        }
        productos_existentes_cursor = productos_collection.find(productos_existentes_query)
        productos_existentes_dict = {}
        async for prod in productos_existentes_cursor:
            productos_existentes_dict[prod["codigo"]] = prod
        
        print(f"[UPLOAD-EXCEL] Productos existentes encontrados: {len(productos_existentes_dict)}")
        
        # Preparar operaciones bulk
        bulk_operations = []
        
        usuario_correo = usuario.get("correo", usuario.get("usuarioCorreo"))
        fecha_actual = datetime.now().isoformat()
        
        for producto_excel in data.productos:
            try:
                # Calcular costo unitario y precio unitario
                costo_unitario = producto_excel.costo or producto_excel.precio
                precio_unitario = producto_excel.precio
                cantidad = producto_excel.stock
                
                # Calcular costo total del item (costo_unitario * cantidad)
                costo_item = costo_unitario * cantidad
                costo_total_inventario += costo_item
                
                # Agregar item al inventario con item_id para facilitar la búsqueda posterior
                # Usamos item_id en lugar de _id porque MongoDB no preserva _id dentro de arrays anidados
                item_inventario = {
                    "item_id": str(ObjectId()),  # Generar ID único para cada item
                    "codigo": producto_excel.codigo,
                    "nombre": producto_excel.nombre,
                    "descripcion": producto_excel.descripcion,
                    "cantidad": cantidad,
                    "costo_unitario": costo_unitario,
                    "precio_unitario": precio_unitario,
                    "costo": costo_item,
                    "precio": precio_unitario * cantidad,
                    "utilidad_contable": (precio_unitario - costo_unitario) * cantidad if precio_unitario > 0 and costo_unitario > 0 else 0
                }
                items_inventario.append(item_inventario)
                
                producto_existente = productos_existentes_dict.get(producto_excel.codigo)
                
                if producto_existente:
                    # Actualizar producto existente
                    stock_sucursal = producto_existente.get("stock_sucursal", {})
                    if not isinstance(stock_sucursal, dict):
                        stock_sucursal = {}
                    
                    stock_sucursal[data.sucursal] = producto_excel.stock
                    stock_total = sum(stock_sucursal.values()) if stock_sucursal else producto_excel.stock
                    
                    sucursales = producto_existente.get("sucursales", [])
                    if not isinstance(sucursales, list):
                        sucursales = []
                    if data.sucursal not in sucursales:
                        sucursales.append(data.sucursal)
                    
                    # Preparar operación de actualización para bulk
                    update_data = {
                        "$set": {
                            "nombre": producto_excel.nombre,
                            "precio": producto_excel.precio,
                            "costo": producto_excel.costo or producto_existente.get("costo", producto_excel.precio),
                            "descripcion": producto_excel.descripcion,
                            "stock": stock_total,
                            "stock_sucursal": stock_sucursal,
                            "sucursal": data.sucursal,
                            "sucursales": sucursales,
                            "fecha_actualizacion": fecha_actual,
                            "usuario_actualizacion": usuario_correo
                        }
                    }
                    
                    bulk_operations.append(
                        UpdateOne(
                            {"codigo": producto_excel.codigo, "sucursal": data.sucursal},
                            update_data
                        )
                    )
                    productos_actualizados += 1
                else:
                    # Crear nuevo producto
                    nuevo_producto = {
                        "codigo": producto_excel.codigo,
                        "nombre": producto_excel.nombre,
                        "precio": producto_excel.precio,
                        "costo": producto_excel.costo or producto_excel.precio,
                        "stock": producto_excel.stock,
                        "stock_sucursal": {
                            data.sucursal: producto_excel.stock
                        },
                        "sucursal": data.sucursal,
                        "sucursales": [data.sucursal],
                        "descripcion": producto_excel.descripcion,
                        "estado": "activo",
                        "fecha_creacion": fecha_actual,
                        "usuario_creacion": usuario_correo
                    }
                    
                    bulk_operations.append(InsertOne(nuevo_producto))
                    productos_agregados += 1
                    
            except Exception as e:
                productos_con_error += 1
                error_msg = f"Error procesando producto {producto_excel.codigo}: {str(e)}"
                errores.append(error_msg)
                print(error_msg)
        
        # OPTIMIZACIÓN: Ejecutar todas las operaciones en batch
        if bulk_operations:
            print(f"[UPLOAD-EXCEL] Ejecutando {len(bulk_operations)} operaciones en batch...")
            try:
                resultado_bulk = await productos_collection.bulk_write(bulk_operations, ordered=False)
                print(f"[UPLOAD-EXCEL] Bulk write completado: {resultado_bulk.modified_count} actualizados, {resultado_bulk.inserted_count} insertados")
                # Ajustar contadores según el resultado real
                productos_actualizados = resultado_bulk.modified_count
                productos_agregados = resultado_bulk.inserted_count
            except Exception as e:
                print(f"[UPLOAD-EXCEL] Error en bulk write: {str(e)}")
                # Si falla el bulk, intentar operaciones individuales como fallback
                productos_actualizados = 0
                productos_agregados = 0
                for op in bulk_operations:
                    try:
                        if isinstance(op, UpdateOne):
                            await productos_collection.update_one(op._filter, op._doc)
                            productos_actualizados += 1
                        elif isinstance(op, InsertOne):
                            await productos_collection.insert_one(op._doc)
                            productos_agregados += 1
                    except Exception as e2:
                        productos_con_error += 1
                        print(f"[UPLOAD-EXCEL] Error en operación individual: {str(e2)}")
        
        # Crear registro de inventario en la colección INVENTARIOS
        inventario_id = None
        try:
            inventarios_collection = get_collection("INVENTARIOS")
            
            # Obtener nombre de la sucursal/farmacia desde la base de datos
            farmacia_nombre = data.sucursal
            
            # Intentar obtener el nombre desde la colección de sucursales
            try:
                sucursales_collection = get_collection("SUCURSALES")
                try:
                    sucursal_doc = await sucursales_collection.find_one({"_id": ObjectId(data.sucursal)})
                except (InvalidId, ValueError):
                    sucursal_doc = await sucursales_collection.find_one({"_id": data.sucursal})
                if sucursal_doc:
                    farmacia_nombre = sucursal_doc.get("nombre", sucursal_doc.get("farmacia", data.sucursal))
            except Exception as e:
                print(f"[UPLOAD-EXCEL] No se pudo obtener nombre de sucursal: {str(e)}")
                # Intentar obtener desde FARMACIAS como fallback
                try:
                    farmacias_collection = get_collection("FARMACIAS")
                    try:
                        farmacia_doc = await farmacias_collection.find_one({"_id": ObjectId(data.sucursal)})
                    except (InvalidId, ValueError):
                        farmacia_doc = await farmacias_collection.find_one({"_id": data.sucursal})
                    if farmacia_doc:
                        farmacia_nombre = farmacia_doc.get("nombre", farmacia_doc.get("farmacia", data.sucursal))
                except Exception as e2:
                    print(f"[UPLOAD-EXCEL] No se pudo obtener nombre de farmacia: {str(e2)}")
                    pass
            
            inventario_doc = {
                "farmacia": farmacia_nombre,
                "sucursal": data.sucursal,
                "costo": costo_total_inventario,
                "usuarioCorreo": usuario.get("correo", usuario.get("usuarioCorreo")),
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "estado": "activo",
                "items": items_inventario,
                "total_items": len(items_inventario),
                "fecha_creacion": datetime.now().isoformat(),
                "usuario_creacion": usuario.get("correo", usuario.get("usuarioCorreo"))
            }
            
            resultado_inventario = await inventarios_collection.insert_one(inventario_doc)
            inventario_id = str(resultado_inventario.inserted_id)
            print(f"[UPLOAD-EXCEL] Inventario creado con ID: {inventario_id}")
            
            # ✅ CRÍTICO: Agregar inventario_id a todos los items del inventario
            # Optimización: hacer un solo update con todos los campos
            if items_inventario:
                update_fields = {}
                for idx in range(len(items_inventario)):
                    update_fields[f"items.{idx}.inventario_id"] = inventario_id
                
                await inventarios_collection.update_one(
                    {"_id": ObjectId(inventario_id)},
                    {"$set": update_fields}
                )
                print(f"[UPLOAD-EXCEL] inventario_id agregado a {len(items_inventario)} items")
            
        except Exception as e:
            # Si falla la creación del inventario, registrar el error pero no fallar todo el proceso
            error_inventario = f"Error al crear el registro de inventario: {str(e)}"
            errores.append(error_inventario)
            print(f"[UPLOAD-EXCEL] {error_inventario}")
        
        total_procesados = len(data.productos)
        
        return UploadExcelResponse(
            message=f"Procesados {total_procesados} productos. {productos_agregados} agregados, {productos_actualizados} actualizados. Inventario creado.",
            sucursal=data.sucursal,
            total_procesados=total_procesados,
            productos_agregados=productos_agregados,
            productos_actualizados=productos_actualizados,
            productos_con_error=productos_con_error,
            inventario_id=inventario_id,
            errores=errores if errores else None
        )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        # Log del error completo para debugging
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error completo en upload_excel_inventarios: {error_trace}")
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje de error: {str(e)}")
        
        # Proporcionar mensaje más descriptivo
        error_detail = str(e)
        if "ObjectId" in error_detail:
            error_detail = "Error de formato en el ID de la base de datos"
        elif "connection" in error_detail.lower() or "network" in error_detail.lower():
            error_detail = "Error de conexión con la base de datos"
        elif "validation" in error_detail.lower():
            error_detail = f"Error de validación: {error_detail}"
        
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el archivo Excel: {error_detail}"
        )


@router.patch("/inventarios/{id}/estado")
async def actualizar_estado_inventario(id: str, data: dict = Body(...), usuario: dict = Depends(get_current_user)):
    try:
        nuevo_estado = data.get("estado")
        if not nuevo_estado:
            raise HTTPException(status_code=400, detail="Falta el campo 'estado'")
        collection = get_collection("INVENTARIOS")
        result = await collection.update_one({"_id": ObjectId(id)}, {"$set": {"estado": nuevo_estado}})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Inventario no encontrado o sin cambios")
        return {"message": f"Estado actualizado a {nuevo_estado}"}
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/inventarios/{id}")
async def eliminar_inventario(id: str, usuario: dict = Depends(get_current_user)):
    """
    Elimina un inventario usando Soft Delete (eliminación lógica).
    
    En lugar de eliminar físicamente el documento:
    - Cambia el estado a "eliminado"
    - Registra la fecha de eliminación
    - Registra el usuario que eliminó el inventario
    
    Ventajas:
    - Permite recuperar datos eliminados por error
    - Mantiene historial para auditoría
    - Permite generar reportes históricos
    - Evita problemas con referencias en otras colecciones
    """
    try:
        collection = get_collection("INVENTARIOS")
        
        # Verificar que el inventario existe y no está ya eliminado
        inventario = await collection.find_one({"_id": ObjectId(id)})
        if not inventario:
            raise HTTPException(status_code=404, detail="Inventario no encontrado")
        
        if inventario.get("estado") == "eliminado":
            raise HTTPException(status_code=400, detail="El inventario ya está eliminado")
        
        # Soft Delete: actualizar estado y agregar campos de auditoría
        update_data = {
            "$set": {
                "estado": "eliminado",
                "fecha_eliminacion": datetime.now().isoformat(),
                "usuario_eliminacion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
            }
        }
        
        result = await collection.update_one(
            {"_id": ObjectId(id)},
            update_data
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar el inventario")
        
        return {
            "message": "Inventario eliminado exitosamente (eliminación lógica)",
            "id": id,
            "fecha_eliminacion": datetime.now().isoformat(),
            "puede_recuperar": True,
            "nota": "El inventario puede ser recuperado cambiando su estado a 'activo'"
        }
        
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de inventario inválido")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar el inventario: {str(e)}"
        )


@router.get("/inventarios/{inventario_id}/items", response_model=List[ItemInventarioResponse])
async def obtener_items_inventario(
    inventario_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Obtiene todos los items detallados de un inventario.
    
    Retorna un array con todos los items del inventario, incluyendo:
    - codigo
    - descripcion/nombre
    - marca (si existe)
    - costo/costo_unitario
    - precio/precio_unitario
    - cantidad
    - utilidad_contable
    - y otros campos que puedan existir en el item
    """
    try:
        collection = get_collection("INVENTARIOS")
        
        # Verificar que el inventario existe
        inventario = await collection.find_one({"_id": ObjectId(inventario_id)})
        if not inventario:
            raise HTTPException(status_code=404, detail="Inventario no encontrado")
        
        # Obtener items del inventario
        items = inventario.get("items", [])
        
        if not items:
            return []  # Retornar array vacío si no hay items
        
        # Transformar items para la respuesta
        items_response = []
        for item in items:
            # Normalizar campos: algunos pueden tener diferentes nombres
            item_dict = dict(item)
            
            # Mapear campos comunes
            # Usar código como identificador principal si no hay item_id o _id
            item_codigo = item_dict.get("codigo")
            item_id_val = item_dict.get("item_id") or item_dict.get("_id")
            
            item_response = {
                "codigo": item_codigo,
                "descripcion": item_dict.get("descripcion") or item_dict.get("nombre"),
                "nombre": item_dict.get("nombre") or item_dict.get("descripcion"),
                "marca": item_dict.get("marca"),
                "costo": item_dict.get("costo"),
                "costo_unitario": item_dict.get("costo_unitario") or item_dict.get("costo"),
                "precio": item_dict.get("precio"),
                "precio_unitario": item_dict.get("precio_unitario") or item_dict.get("precio"),
                "cantidad": item_dict.get("cantidad"),
                "utilidad_contable": item_dict.get("utilidad_contable"),
                "lotes": item_dict.get("lotes", []),  # Devolver lotes si existen
                "_id": str(item_id_val) if item_id_val else (str(item_codigo) if item_codigo else None),
                "item_id": str(item_id_val) if item_id_val else (str(item_codigo) if item_codigo else None)
            }
            
            # Agregar cualquier otro campo que exista en el item
            for key, value in item_dict.items():
                if key not in item_response and key != "_id":
                    item_response[key] = value
            
            items_response.append(ItemInventarioResponse(**item_response))
        
        return items_response
        
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de inventario inválido")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los items del inventario: {str(e)}"
        )


@router.post("/inventarios/{id}/restaurar")
async def restaurar_inventario(id: str, usuario: dict = Depends(get_current_user)):
    """
    Restaura un inventario eliminado (cambia el estado de "eliminado" a "activo").
    
    Solo se puede restaurar inventarios que estén en estado "eliminado".
    """
    try:
        collection = get_collection("INVENTARIOS")
        
        # Verificar que el inventario existe
        inventario = await collection.find_one({"_id": ObjectId(id)})
        if not inventario:
            raise HTTPException(status_code=404, detail="Inventario no encontrado")
        
        # Verificar que el inventario está eliminado
        if inventario.get("estado") != "eliminado":
            raise HTTPException(
                status_code=400, 
                detail=f"El inventario no está eliminado. Estado actual: {inventario.get('estado', 'activo')}"
            )
        
        # Restaurar: cambiar estado a "activo" y limpiar campos de eliminación
        update_data = {
            "$set": {
                "estado": "activo",
                "fecha_restauracion": datetime.now().isoformat(),
                "usuario_restauracion": usuario.get("correo", usuario.get("usuarioCorreo", "unknown"))
            },
            "$unset": {
                "fecha_eliminacion": "",
                "usuario_eliminacion": ""
            }
        }
        
        result = await collection.update_one(
            {"_id": ObjectId(id)},
            update_data
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="No se pudo restaurar el inventario")
        
        return {
            "message": "Inventario restaurado exitosamente",
            "id": id,
            "fecha_restauracion": datetime.now().isoformat(),
            "estado": "activo"
        }
        
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de inventario inválido")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al restaurar el inventario: {str(e)}"
        )


@router.patch("/inventarios/{inventario_id}/items/{item_id}")
async def modificar_item_inventario(
    inventario_id: str,
    item_id: str,
    data: ItemInventarioUpdate,
    usuario: dict = Depends(get_current_user)
):
    """
    Modifica un item específico de un inventario.
    
    - Calcula automáticamente la utilidad contable si se proporcionan precio_unitario y costo_unitario
    - Actualiza el costo total del inventario basado en la suma de todos los items
    - Valida que el inventario y el item existan
    
    Utilidad contable = (precio_unitario - costo_unitario) * cantidad
    """
    try:
        print(f"[MODIFICAR-ITEM] ========== INICIO ==========")
        print(f"[MODIFICAR-ITEM] Paso 1: Validando permisos y parámetros")
        print(f"[MODIFICAR-ITEM] item_id recibido: {item_id}")
        print(f"[MODIFICAR-ITEM] inventario_id recibido: {inventario_id}")
        print(f"[MODIFICAR-ITEM] usuario: {usuario.get('correo', usuario.get('usuarioCorreo', 'N/A'))}")
        print(f"[MODIFICAR-ITEM] data recibida: {data.dict() if hasattr(data, 'dict') else data}")
        
        collection = get_collection("INVENTARIOS")
        
        print(f"[MODIFICAR-ITEM] Paso 2: Buscando inventario")
        # Verificar que el inventario existe y no está eliminado
        inventario = await collection.find_one({"_id": ObjectId(inventario_id)})
        if not inventario:
            print(f"[MODIFICAR-ITEM] ERROR: Inventario no encontrado")
            raise HTTPException(status_code=404, detail="Inventario no encontrado")
        print(f"[MODIFICAR-ITEM] Inventario encontrado: {inventario_id}, estado: {inventario.get('estado', 'N/A')}")
        
        # Verificar que el inventario no esté eliminado
        if inventario.get("estado") == "eliminado":
            print(f"[MODIFICAR-ITEM] ERROR: Inventario está eliminado")
            raise HTTPException(status_code=400, detail="No se puede modificar un inventario eliminado. Debe restaurarlo primero.")
        
        # Verificar que el inventario tiene items
        items = inventario.get("items", [])
        if not items:
            print(f"[MODIFICAR-ITEM] ERROR: Inventario no tiene items")
            raise HTTPException(status_code=404, detail="El inventario no tiene items")
        print(f"[MODIFICAR-ITEM] Inventario tiene {len(items)} items")
        
        # Buscar el item por ObjectId (_id o item_id), código o índice dentro del inventario especificado
        item_index = None
        item_actual = None
        
        # Verificar si item_id parece ser un ObjectId válido (24 caracteres hexadecimales)
        es_objectid = False
        try:
            test_oid = ObjectId(item_id)
            es_objectid = True
        except (InvalidId, ValueError, TypeError):
            pass
        
        item_id_normalizado = str(item_id).strip()
        
        # ✅ PRIORIDAD 1: Buscar por código del producto en PRODUCTOS
        # El frontend envía el código del producto, no el item_id interno
        try:
            productos_collection = get_collection("PRODUCTOS")
            try:
                await productos_collection.find_one({})
            except:
                productos_collection = get_collection("INVENTARIOS")
            
            # Intentar buscar el producto por código (si item_id es un código)
            producto = None
            codigo_producto = None
            
            # Si es ObjectId, buscar producto por _id
            if es_objectid:
                producto = await productos_collection.find_one({"_id": ObjectId(item_id)})
                if producto:
                    codigo_producto = producto.get("codigo")
            else:
                # Si no es ObjectId, asumir que es el código del producto
                codigo_producto = item_id_normalizado
                producto = await productos_collection.find_one({"codigo": codigo_producto})
            
            # Si encontramos el producto, buscar el item en el inventario por su código
            if producto and codigo_producto is not None:
                codigo_producto_str = str(codigo_producto).strip()
                codigo_producto_num = None
                try:
                    codigo_producto_num = float(codigo_producto_str)
                except (ValueError, TypeError):
                    pass
                
                # Buscar el item en el inventario por ese código
                for idx, item in enumerate(items):
                    item_codigo = item.get("codigo")
                    if item_codigo is not None:
                        item_codigo_str = str(item_codigo).strip()
                        
                        # Comparar como strings exactos
                        if item_codigo_str == codigo_producto_str:
                            item_index = idx
                            item_actual = item.copy()
                            print(f"[MODIFICAR-ITEM] Item encontrado por código del producto: {codigo_producto_str}")
                            
                            # Si el item no tiene inventario_id, agregarlo automáticamente
                            item_inventario_id = str(item_actual.get("inventario_id", ""))
                            inventario_id_str = str(inventario_id)
                            if not item_inventario_id:
                                print(f"[MODIFICAR-ITEM] Item no tiene inventario_id, agregándolo automáticamente")
                                await collection.update_one(
                                    {"_id": ObjectId(inventario_id)},
                                    {"$set": {f"items.{idx}.inventario_id": inventario_id_str}}
                                )
                                item_actual["inventario_id"] = inventario_id_str
                            
                            break
                        
                        # Comparar como números si ambos son numéricos
                        if codigo_producto_num is not None:
                            try:
                                item_codigo_num = float(item_codigo_str)
                                if abs(item_codigo_num - codigo_producto_num) < 0.0001:
                                    item_index = idx
                                    item_actual = item.copy()
                                    print(f"[MODIFICAR-ITEM] Item encontrado por código del producto (numérico): {codigo_producto_str}")
                                    
                                    # Si el item no tiene inventario_id, agregarlo automáticamente
                                    item_inventario_id = str(item_actual.get("inventario_id", ""))
                                    inventario_id_str = str(inventario_id)
                                    if not item_inventario_id:
                                        print(f"[MODIFICAR-ITEM] Item no tiene inventario_id, agregándolo automáticamente")
                                        await collection.update_one(
                                            {"_id": ObjectId(inventario_id)},
                                            {"$set": {f"items.{idx}.inventario_id": inventario_id_str}}
                                        )
                                        item_actual["inventario_id"] = inventario_id_str
                                    
                                    break
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            print(f"[MODIFICAR-ITEM] Error al buscar producto: {str(e)}")
            pass  # Continuar con otras búsquedas
        
        # PRIORIDAD 2: Si no se encontró por código del producto, buscar por _id (ObjectId) del item directamente
        if item_index is None and es_objectid:
            for idx, item in enumerate(items):
                item_obj_id = item.get("item_id") or item.get("_id")
                if item_obj_id:
                    try:
                        # Convertir ambos a ObjectId para comparar
                        item_obj_id_obj = ObjectId(item_obj_id) if not isinstance(item_obj_id, ObjectId) else item_obj_id
                        item_id_obj = ObjectId(item_id)
                        if item_obj_id_obj == item_id_obj:
                            item_index = idx
                            item_actual = item.copy()
                            print(f"[MODIFICAR-ITEM] Item encontrado por _id (ObjectId): {item_id}")
                            print(f"[MODIFICAR-ITEM] Item encontrado: {item_actual.get('_id') or item_actual.get('item_id')}")
                            
                            # Validar que el item pertenezca al inventario correcto
                            # Convertir ambos a string para comparar (evita problemas de tipo)
                            item_inventario_id = str(item_actual.get("inventario_id", ""))
                            inventario_id_str = str(inventario_id)
                            
                            if item_inventario_id and item_inventario_id != inventario_id_str:
                                print(f"[MODIFICAR-ITEM] ADVERTENCIA: inventario_id del item ({item_inventario_id}) != inventario_id recibido ({inventario_id_str})")
                                raise HTTPException(status_code=404, detail="Item no encontrado en este inventario")
                            
                            break
                    except (InvalidId, ValueError, TypeError):
                        # Si falla la conversión a ObjectId, comparar como strings
                        item_id_str = str(item_obj_id).strip()
                        if item_id_str == item_id_normalizado:
                            item_index = idx
                            item_actual = item.copy()
                            print(f"[MODIFICAR-ITEM] Item encontrado por _id (string): {item_id}")
                            print(f"[MODIFICAR-ITEM] Item encontrado: {item_actual.get('_id') or item_actual.get('item_id')}")
                            
                            # Validar que el item pertenezca al inventario correcto
                            item_inventario_id = str(item_actual.get("inventario_id", ""))
                            inventario_id_str = str(inventario_id)
                            
                            if item_inventario_id and item_inventario_id != inventario_id_str:
                                print(f"[MODIFICAR-ITEM] ADVERTENCIA: inventario_id del item ({item_inventario_id}) != inventario_id recibido ({inventario_id_str})")
                                raise HTTPException(status_code=404, detail="Item no encontrado en este inventario")
                            
                            break
        
        # PRIORIDAD 3: Si no se encontró, buscar por código directamente en items
        if item_index is None:
            item_id_num = None
            try:
                item_id_num = float(item_id_normalizado)
            except (ValueError, TypeError):
                pass
            
            # Buscar por código
            for idx, item in enumerate(items):
                item_codigo = item.get("codigo")
                if item_codigo is not None:
                    codigo_normalizado = str(item_codigo).strip()
                    
                    # Comparar como strings exactos
                    if codigo_normalizado == item_id_normalizado:
                        item_index = idx
                        item_actual = item.copy()
                        print(f"[MODIFICAR-ITEM] Item encontrado por código: {item_id}")
                        
                        # Si el item no tiene inventario_id, agregarlo automáticamente
                        item_inventario_id = str(item_actual.get("inventario_id", ""))
                        inventario_id_str = str(inventario_id)
                        if not item_inventario_id:
                            print(f"[MODIFICAR-ITEM] Item no tiene inventario_id, agregándolo automáticamente")
                            await collection.update_one(
                                {"_id": ObjectId(inventario_id)},
                                {"$set": {f"items.{idx}.inventario_id": inventario_id_str}}
                            )
                            item_actual["inventario_id"] = inventario_id_str
                        
                        break
                    
                    # Comparar como números si ambos son numéricos
                    if item_id_num is not None:
                        try:
                            codigo_num = float(codigo_normalizado)
                            if abs(codigo_num - item_id_num) < 0.0001:
                                item_index = idx
                                item_actual = item.copy()
                                print(f"[MODIFICAR-ITEM] Item encontrado por código (numérico): {item_id}")
                                
                                # Si el item no tiene inventario_id, agregarlo automáticamente
                                item_inventario_id = str(item_actual.get("inventario_id", ""))
                                inventario_id_str = str(inventario_id)
                                if not item_inventario_id:
                                    print(f"[MODIFICAR-ITEM] Item no tiene inventario_id, agregándolo automáticamente")
                                    await collection.update_one(
                                        {"_id": ObjectId(inventario_id)},
                                        {"$set": {f"items.{idx}.inventario_id": inventario_id_str}}
                                    )
                                    item_actual["inventario_id"] = inventario_id_str
                                
                                break
                        except (ValueError, TypeError):
                            pass
        
        # PRIORIDAD 4: Buscar por índice numérico
        if item_index is None:
            try:
                idx_num = int(item_id)
                if 0 <= idx_num < len(items):
                    item_index = idx_num
                    item_actual = items[idx_num].copy()
                    print(f"[MODIFICAR-ITEM] Item encontrado por índice: {idx_num}")
            except ValueError:
                pass
        
        if item_index is None:
            print(f"[MODIFICAR-ITEM] Item NO encontrado. item_id: {item_id}, Total items: {len(items)}")
            # Solo mostrar información básica en caso de error
            codigos_unicos = set()
            for item in items:
                codigo = item.get('codigo')
                if codigo:
                    codigos_unicos.add(str(codigo).strip())
            raise HTTPException(
                status_code=404, 
                detail=f"Item no encontrado. item_id: {item_id}. Total items: {len(items)}"
            )
        
        # Log final del item encontrado
        print(f"[MODIFICAR-ITEM] Paso 3: Item encontrado exitosamente")
        print(f"[MODIFICAR-ITEM] Item encontrado: {item_actual.get('_id') or item_actual.get('item_id')}")
        print(f"[MODIFICAR-ITEM] inventario_id del item: {item_actual.get('inventario_id', 'No tiene inventario_id')}")
        print(f"[MODIFICAR-ITEM] item_index: {item_index}")
        print(f"[MODIFICAR-ITEM] Item actual completo: {item_actual}")
        
        print(f"[MODIFICAR-ITEM] Paso 4: Preparando datos para actualizar")
        # Preparar los datos a actualizar
        update_data = {}
        
        # Actualizar campos básicos si se proporcionan
        print(f"[MODIFICAR-ITEM] Validando campos del request body")
        if data.nombre is not None:
            print(f"[MODIFICAR-ITEM] nombre: {data.nombre}")
            update_data["nombre"] = data.nombre
        if data.codigo is not None:
            print(f"[MODIFICAR-ITEM] codigo: {data.codigo}")
            update_data["codigo"] = data.codigo
        if data.cantidad is not None:
            print(f"[MODIFICAR-ITEM] cantidad recibida: {data.cantidad} (tipo: {type(data.cantidad)})")
            # Convertir a int si es necesario (puede venir como string o float)
            try:
                cantidad_valor = int(data.cantidad) if not isinstance(data.cantidad, int) else data.cantidad
            except (ValueError, TypeError) as e:
                print(f"[MODIFICAR-ITEM] ERROR: No se puede convertir cantidad a int: {data.cantidad}, error: {str(e)}")
                raise HTTPException(status_code=400, detail=f"La cantidad debe ser un número entero válido: {data.cantidad}")
            
            if cantidad_valor < 0:
                print(f"[MODIFICAR-ITEM] ERROR: Cantidad negativa")
                raise HTTPException(status_code=400, detail="La cantidad no puede ser negativa")
            # Permitir cantidad = 0 (puede ser válido para ajustes de inventario)
            update_data["cantidad"] = cantidad_valor
            print(f"[MODIFICAR-ITEM] cantidad agregada a update_data: {update_data['cantidad']} (tipo final: {type(update_data['cantidad'])})")
        else:
            print(f"[MODIFICAR-ITEM] cantidad es None - no se actualizará este campo")
        if data.precio_unitario is not None:
            print(f"[MODIFICAR-ITEM] precio_unitario recibido: {data.precio_unitario} (tipo: {type(data.precio_unitario)})")
            # Convertir a float si es necesario
            try:
                precio_valor = float(data.precio_unitario) if not isinstance(data.precio_unitario, (int, float)) else float(data.precio_unitario)
            except (ValueError, TypeError) as e:
                print(f"[MODIFICAR-ITEM] ERROR: No se puede convertir precio_unitario a float: {data.precio_unitario}, error: {str(e)}")
                raise HTTPException(status_code=400, detail=f"El precio unitario debe ser un número válido: {data.precio_unitario}")
            
            if precio_valor < 0:
                print(f"[MODIFICAR-ITEM] ERROR: Precio unitario negativo")
                raise HTTPException(status_code=400, detail="El precio unitario no puede ser negativo")
            update_data["precio_unitario"] = precio_valor
            print(f"[MODIFICAR-ITEM] precio_unitario agregado a update_data: {update_data['precio_unitario']} (tipo final: {type(update_data['precio_unitario'])})")
        else:
            print(f"[MODIFICAR-ITEM] precio_unitario es None - no se actualizará este campo")
        if data.costo_unitario is not None:
            print(f"[MODIFICAR-ITEM] costo_unitario recibido: {data.costo_unitario} (tipo: {type(data.costo_unitario)})")
            # Convertir a float si es necesario
            try:
                costo_valor = float(data.costo_unitario) if not isinstance(data.costo_unitario, (int, float)) else float(data.costo_unitario)
            except (ValueError, TypeError) as e:
                print(f"[MODIFICAR-ITEM] ERROR: No se puede convertir costo_unitario a float: {data.costo_unitario}, error: {str(e)}")
                raise HTTPException(status_code=400, detail=f"El costo unitario debe ser un número válido: {data.costo_unitario}")
            
            if costo_valor < 0:
                print(f"[MODIFICAR-ITEM] ERROR: Costo unitario negativo")
                raise HTTPException(status_code=400, detail="El costo unitario no puede ser negativo")
            update_data["costo_unitario"] = costo_valor
            print(f"[MODIFICAR-ITEM] costo_unitario agregado a update_data: {update_data['costo_unitario']} (tipo final: {type(update_data['costo_unitario'])})")
        else:
            print(f"[MODIFICAR-ITEM] costo_unitario es None - no se actualizará este campo")
        if data.descripcion is not None:
            print(f"[MODIFICAR-ITEM] descripcion: {data.descripcion}")
            update_data["descripcion"] = data.descripcion
        
        # CRÍTICO: Actualizar lotes si se proporcionan
        if data.lotes is not None:
            print(f"[MODIFICAR-ITEM] lotes recibidos: {len(data.lotes) if data.lotes else 0} lotes")
            # Convertir los lotes a diccionarios para guardar en MongoDB
            lotes_dict = [lote.dict() if hasattr(lote, 'dict') else lote for lote in data.lotes]
            update_data["lotes"] = lotes_dict
            print(f"[MODIFICAR-ITEM] lotes agregados a update_data: {lotes_dict}")
        else:
            print(f"[MODIFICAR-ITEM] lotes es None - no se actualizará este campo")
        
        print(f"[MODIFICAR-ITEM] update_data después de validar campos: {update_data}")
        
        # Obtener valores actuales o nuevos para calcular campos derivados
        cantidad = update_data.get("cantidad", item_actual.get("cantidad", 0))
        precio_unitario = update_data.get("precio_unitario", item_actual.get("precio_unitario", item_actual.get("precio", 0)))
        costo_unitario = update_data.get("costo_unitario", item_actual.get("costo_unitario", item_actual.get("costo", 0)))
        
        # Si costo_unitario viene como "costo" (total), calcularlo unitario
        if "costo_unitario" not in update_data and item_actual.get("costo") and not item_actual.get("costo_unitario"):
            costo_total_item = item_actual.get("costo", 0)
            cantidad_actual = item_actual.get("cantidad", 1)
            if cantidad_actual > 0:
                costo_unitario = costo_total_item / cantidad_actual
        
        print(f"[MODIFICAR-ITEM] Valores para cálculo: cantidad={cantidad}, precio_unitario={precio_unitario}, costo_unitario={costo_unitario}")
        
        # CRÍTICO: Recalcular campos derivados (costo, precio, utilidad_contable) si cambió cantidad, precio_unitario o costo_unitario
        # Esto asegura que los campos calculados siempre estén actualizados
        campos_calculados_necesarios = False
        if "cantidad" in update_data or "precio_unitario" in update_data or "costo_unitario" in update_data:
            campos_calculados_necesarios = True
            print(f"[MODIFICAR-ITEM] Se actualizaron campos que afectan cálculos, recalculando campos derivados")
        
        # Calcular costo total del item (costo_unitario * cantidad)
        if campos_calculados_necesarios:
            costo_item = costo_unitario * cantidad
            update_data["costo"] = costo_item
            print(f"[MODIFICAR-ITEM] Costo del item calculado: {costo_item} = {costo_unitario} × {cantidad}")
        
        # Calcular precio total del item (precio_unitario * cantidad)
        if campos_calculados_necesarios:
            precio_item = precio_unitario * cantidad
            update_data["precio"] = precio_item
            print(f"[MODIFICAR-ITEM] Precio del item calculado: {precio_item} = {precio_unitario} × {cantidad}")
        
        # Calcular utilidad contable
        # Utilidad contable = (precio_unitario - costo_unitario) * cantidad
        if campos_calculados_necesarios:
            if precio_unitario > 0 and costo_unitario > 0 and cantidad >= 0:
                utilidad_contable = (precio_unitario - costo_unitario) * cantidad
                update_data["utilidad_contable"] = utilidad_contable
                print(f"[MODIFICAR-ITEM] Utilidad contable calculada: {utilidad_contable} = ({precio_unitario} - {costo_unitario}) × {cantidad}")
            else:
                update_data["utilidad_contable"] = 0.0
                print(f"[MODIFICAR-ITEM] Utilidad contable = 0 (valores no válidos para cálculo)")
        
        # Si se proporciona utilidad_contable manualmente, usarla (sobrescribe el cálculo)
        if data.utilidad_contable is not None:
            update_data["utilidad_contable"] = data.utilidad_contable
            print(f"[MODIFICAR-ITEM] Utilidad contable proporcionada manualmente: {data.utilidad_contable}")
        
        # CRÍTICO: Preservar campos importantes que no deben perderse
        # Asegurar que item_id e inventario_id se preserven
        if "item_id" not in update_data and item_actual.get("item_id"):
            # No agregar a update_data porque no queremos actualizarlo, solo preservarlo
            print(f"[MODIFICAR-ITEM] Preservando item_id: {item_actual.get('item_id')}")
        
        if "inventario_id" not in update_data and item_actual.get("inventario_id"):
            # No agregar a update_data porque no queremos actualizarlo, solo preservarlo
            print(f"[MODIFICAR-ITEM] Preservando inventario_id: {item_actual.get('inventario_id')}")
        
        print(f"[MODIFICAR-ITEM] update_data final antes de guardar: {update_data}")
        
        # Actualizar el item en el array
        print(f"[MODIFICAR-ITEM] Paso 5: Verificando si hay datos para actualizar")
        print(f"[MODIFICAR-ITEM] update_data tiene {len(update_data)} campos: {list(update_data.keys())}")
        
        if update_data:
            print(f"[MODIFICAR-ITEM] Paso 6: Construyendo campos de actualización")
            # Construir el path del campo a actualizar
            update_fields = {}
            for key, value in update_data.items():
                field_path = f"items.{item_index}.{key}"
                update_fields[field_path] = value
                print(f"[MODIFICAR-ITEM] Campo a actualizar: {field_path} = {value}")
            
            print(f"[MODIFICAR-ITEM] update_fields completo: {update_fields}")
            print(f"[MODIFICAR-ITEM] Paso 7: Ejecutando actualización en MongoDB")
            
            # Actualizar el item en MongoDB
            # NOTA: En MongoDB con Motor (async), update_one() ya guarda los cambios directamente
            # No hay necesidad de item.save() - update_one() persiste los cambios automáticamente
            print(f"[MODIFICAR-ITEM] Guardando cambios en MongoDB con update_one()")
            result = await collection.update_one(
                {"_id": ObjectId(inventario_id)},
                {"$set": update_fields}
            )
            
            print(f"[MODIFICAR-ITEM] Resultado de update_one:")
            print(f"[MODIFICAR-ITEM]   - matched_count: {result.matched_count}")
            print(f"[MODIFICAR-ITEM]   - modified_count: {result.modified_count}")
            print(f"[MODIFICAR-ITEM]   - upserted_id: {result.upserted_id}")
            
            # Verificar si se encontró el documento
            if result.matched_count == 0:
                print(f"[MODIFICAR-ITEM] ERROR: No se encontró el documento para actualizar")
                print(f"[MODIFICAR-ITEM] Posibles causas:")
                print(f"[MODIFICAR-ITEM]   - El item_index ({item_index}) es incorrecto")
                print(f"[MODIFICAR-ITEM]   - El inventario_id ({inventario_id}) es incorrecto")
                raise HTTPException(status_code=404, detail="No se pudo actualizar el item")
            
            # Si modified_count = 0 pero matched_count = 1, significa que los valores ya son los mismos
            # Esto es válido y no debe considerarse un error
            if result.modified_count == 0:
                print(f"[MODIFICAR-ITEM] INFO: modified_count = 0 (los valores ya son los mismos, no se modificó nada)")
                print(f"[MODIFICAR-ITEM] Esto es válido - el item ya tenía esos valores")
            else:
                print(f"[MODIFICAR-ITEM] Item actualizado exitosamente en MongoDB (modified_count = {result.modified_count})")
            
            print(f"[MODIFICAR-ITEM] Paso 8: Recalculando costo total del inventario")
            # Recalcular el costo total del inventario
            inventario_actualizado = await collection.find_one({"_id": ObjectId(inventario_id)})
            items_actualizados = inventario_actualizado.get("items", [])
            print(f"[MODIFICAR-ITEM] Items actualizados: {len(items_actualizados)}")
            
            # Calcular costo total: suma de (costo_unitario * cantidad) de todos los items
            # IMPORTANTE: Usar costo_unitario, NO precio_unitario
            costo_total = 0.0
            print(f"[MODIFICAR-ITEM] Calculando costo total del inventario:")
            for idx, item in enumerate(items_actualizados):
                costo_unit = item.get("costo_unitario", 0) or 0
                cantidad_item = item.get("cantidad", 0) or 0
                item_costo = costo_unit * cantidad_item
                costo_total += item_costo
                if idx < 5:  # Log primeros 5 items para debugging
                    print(f"[MODIFICAR-ITEM]   Item {idx}: cantidad={cantidad_item}, costo_unitario={costo_unit}, costo_item={item_costo}")
            
            print(f"[MODIFICAR-ITEM] Costo total calculado: {costo_total} (suma de cantidad × costo_unitario)")
            print(f"[MODIFICAR-ITEM] NOTA: Se usa costo_unitario, NO precio_unitario para el cálculo")
            
            # CRÍTICO: Calcular total de existencias (suma de todas las cantidades)
            total_existencias = 0
            for item in items_actualizados:
                cantidad_item = item.get("cantidad", 0) or 0
                total_existencias += cantidad_item
            
            print(f"[MODIFICAR-ITEM] Total existencias calculado: {total_existencias} (suma de todas las cantidades)")
            
            # Actualizar el costo total y total de existencias del inventario
            # IMPORTANTE: Guardar en campo "costo", NO "precio"
            print(f"[MODIFICAR-ITEM] Paso 9: Actualizando costo total y total existencias del inventario")
            print(f"[MODIFICAR-ITEM] Guardando costo_total={costo_total} en campo 'costo' del inventario")
            print(f"[MODIFICAR-ITEM] Guardando total_existencias={total_existencias} en campo 'total_items' o 'total_existencias'")
            
            # Actualizar ambos campos en una sola operación
            update_inventario = {
                "costo": costo_total,
                "total_items": total_existencias  # Usar total_items para consistencia
            }
            
            result_costo = await collection.update_one(
                {"_id": ObjectId(inventario_id)},
                {"$set": update_inventario}
            )
            print(f"[MODIFICAR-ITEM] Inventario actualizado en MongoDB:")
            print(f"[MODIFICAR-ITEM]   - matched_count: {result_costo.matched_count}")
            print(f"[MODIFICAR-ITEM]   - modified_count: {result_costo.modified_count}")
            print(f"[MODIFICAR-ITEM]   - Campos actualizados: costo={costo_total}, total_items={total_existencias}")
            
            # Verificar que se guardó correctamente
            if result_costo.matched_count == 0:
                print(f"[MODIFICAR-ITEM] ERROR: No se encontró el inventario para actualizar")
                raise HTTPException(status_code=500, detail="Error al actualizar el inventario")
            elif result_costo.modified_count > 0:
                print(f"[MODIFICAR-ITEM] ✅ Inventario guardado exitosamente en MongoDB (costo y total_items)")
            else:
                print(f"[MODIFICAR-ITEM] INFO: Inventario no cambió (ya tenía esos valores)")
            
            # Verificar que los valores se guardaron correctamente
            inventario_verificado = await collection.find_one({"_id": ObjectId(inventario_id)})
            costo_guardado = inventario_verificado.get("costo", 0)
            total_items_guardado = inventario_verificado.get("total_items", 0)
            print(f"[MODIFICAR-ITEM] Verificación: costo en BD={costo_guardado}, total_items en BD={total_items_guardado}")
            
            if abs(costo_guardado - costo_total) > 0.01:
                print(f"[MODIFICAR-ITEM] ADVERTENCIA: El costo guardado ({costo_guardado}) no coincide con el calculado ({costo_total})")
            
            if total_items_guardado != total_existencias:
                print(f"[MODIFICAR-ITEM] ADVERTENCIA: El total_items guardado ({total_items_guardado}) no coincide con el calculado ({total_existencias})")
            
            # Obtener el item actualizado para retornarlo
            print(f"[MODIFICAR-ITEM] Paso 10: Obteniendo item actualizado para respuesta")
            inventario_final = await collection.find_one({"_id": ObjectId(inventario_id)})
            items_final = inventario_final.get("items", [])
            print(f"[MODIFICAR-ITEM] Items finales: {len(items_final)}, item_index: {item_index}")
            
            if item_index >= len(items_final):
                print(f"[MODIFICAR-ITEM] ERROR: item_index ({item_index}) fuera de rango (items: {len(items_final)})")
                raise HTTPException(status_code=500, detail="Error al obtener el item actualizado")
            
            item_actualizado = items_final[item_index]
            print(f"[MODIFICAR-ITEM] Item actualizado obtenido: {item_actualizado}")
            
            # Asegurar que el item tenga item_id o _id para la respuesta
            if not item_actualizado.get("item_id") and not item_actualizado.get("_id"):
                item_actualizado["item_id"] = item_id
            elif item_actualizado.get("item_id"):
                item_actualizado["item_id"] = str(item_actualizado["item_id"])
            elif item_actualizado.get("_id"):
                item_actualizado["_id"] = str(item_actualizado["_id"])
            
            print(f"[MODIFICAR-ITEM] Paso 11: Preparando respuesta")
            respuesta = {
                "message": "Item actualizado exitosamente",
                "item": item_actualizado,
                "costo_total_inventario": costo_total
            }
            print(f"[MODIFICAR-ITEM] Respuesta preparada: {respuesta}")
            print(f"[MODIFICAR-ITEM] ========== ÉXITO ==========")
            return respuesta
        else:
            print(f"[MODIFICAR-ITEM] ERROR: No se proporcionaron campos para actualizar")
            print(f"[MODIFICAR-ITEM] update_data está vacío: {update_data}")
            raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
            
    except InvalidId as e:
        print(f"[MODIFICAR-ITEM] ERROR InvalidId: {str(e)}")
        import traceback
        print(f"[MODIFICAR-ITEM] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail="ID de inventario o item inválido")
    except HTTPException as e:
        print(f"[MODIFICAR-ITEM] ERROR HTTPException: status={e.status_code}, detail={e.detail}")
        raise
    except Exception as e:
        print(f"[MODIFICAR-ITEM] ERROR Exception: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[MODIFICAR-ITEM] Traceback completo:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al modificar el item: {str(e)}"
        )

@router.post("/presigned-url")
async def get_presigned_url(request: Request):
    """
    Endpoint para generar una URL prefirmada para Cloudflare R2.
    """
    data = await request.json()
    object_name = data.get('object_name')
    operation = data.get('operation', 'get_object')
    expires_in = data.get('expires_in', 3600)
    content_type = data.get('content_type')

    if not object_name:
        return JSONResponse(status_code=400, content={"error": "Missing 'object_name' in request body"})

    try:
        if operation == 'get_object':
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': R2_BUCKET,
                    'Key': object_name
                },
                ExpiresIn=expires_in
            )
        elif operation == 'put_object':
            if not content_type:
                return JSONResponse(status_code=400, content={"error": "For 'put_object' operation, 'content_type' is required."})
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': R2_BUCKET,
                    'Key': object_name,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in
            )
        else:
            return JSONResponse(status_code=400, content={"error": "Invalid 'operation'. Must be 'get_object' or 'put_object'."})
        return {"presigned_url": presigned_url}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to generate presigned URL: {str(e)}"})

