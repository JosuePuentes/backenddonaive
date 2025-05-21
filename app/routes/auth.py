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

@router.post("/cuadres/{farmacia}")
async def agregar_cuadre(farmacia: str, cuadre: Cuadre):
    try:
        collection = get_collection("CUADRES")
        result = collection.insert_one({**cuadre.dict(), "created_at": datetime.utcnow()})
        return {"message": "Cuadre guardado", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))