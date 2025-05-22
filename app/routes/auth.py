from fastapi import APIRouter, HTTPException, Body
from app.schemas.auth import LoginInput, Cuadre
from app.services.users_service import login_y_token

from fastapi import APIRouter, Query
from typing import List
from app.db.mongo import get_collection  # tu helper para acceder a la colección
from bson import ObjectId
from datetime import datetime

router = APIRouter()

@router.post("/auth/login")
async def login_user(data: LoginInput):
    usuario, token = await login_y_token(data.correo, data.contraseña, return_user=True)
    if not token or not usuario:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    # El usuario debe ser un dict con el campo 'farmacias'
    usuario["_id"] = str(usuario["_id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": usuario
    }

@router.get("/cuadres")
async def obtener_cuadres():
    collection = get_collection("CUADRES")
    resultados = await collection.find({}).to_list(100)
    # Convertir _id a string
    print(f"resultados: {resultados}")
    for r in resultados:
        r["_id"] = str(r["_id"])
    return resultados

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
        # puntosVenta ya viene como array de objetos
        result = collection.insert_one(cuadre_dict)
        return {"message": "Cuadre guardado", "result": str(result)}
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
async def actualizar_estado_cuadre_por_id(farmacia_id: str, cuadre_id: str, estado: str = Body(..., embed=True)):
    try:
        collection = get_collection(f"CUADRES-{farmacia_id}")
        result = await collection.update_one(
            {"_id": ObjectId(cuadre_id)},
            {"$set": {"estado": estado}}
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
    collection = get_collection("CAJEROS")
    docs = await collection.find({}).to_list(length=None)
    # Convertir _id a string para el frontend
    for doc in docs:
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
    return docs

