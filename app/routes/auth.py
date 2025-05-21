from fastapi import APIRouter, HTTPException
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
    token = await login_y_token(data.correo, data.contraseña)
    if not token:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return {"access_token": token, "token_type": "bearer"}

@router.get("/cuadres")
async def obtener_cuadres():
    collection = get_collection("CUADRES")
    resultados = await collection.find({}).to_list(100)
    # Convertir _id a string
    print(f"resultados: {resultados}")
    for r in resultados:
        r["_id"] = str(r["_id"])
    return resultados

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
        print(f"cuadre: {cuadre}")
        result = collection.insert_one({**cuadre.dict()})
        print(f"result: {result}")
        return {"message": "Cuadre guardado", "result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/farmacias")
async def obtener_farmacias():
    try:
        collection = get_collection("FARMACIAS")
        farmacia = await collection.find_one({})
        if farmacia:
            farmacia["_id"] = str(farmacia["_id"])
            return farmacia
        else:
            raise HTTPException(status_code=404, detail="No se encontró ninguna farmacia")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

