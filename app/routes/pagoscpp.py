from fastapi import APIRouter, HTTPException, Body, Depends, Query
from app.db.mongo import get_collection
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import pytz
from bson import ObjectId

router = APIRouter()

class PagoCPP(BaseModel):
    fecha: str
    hora: Optional[str] = None
    moneda: str
    monto: float
    referencia: str
    usuario: str
    bancoEmisor: str
    bancoReceptor: str
    tasa: Optional[float] = None
    imagenPago: Optional[str] = None
    farmaciaId: str
    estado: str
    cuentaPorPagarId: str
    fechaRegistro: Optional[str] = None
    horaRegistro: Optional[str] = None

class EstadoUpdate(BaseModel):
    estado: str

def pago_to_dict(pago):
    d = dict(pago)
    if '_id' in d and isinstance(d['_id'], ObjectId):
        d['_id'] = str(d['_id'])
    return d

@router.post("/pagoscpp")
async def crear_pago_cpp(pago: PagoCPP):
    try:
        venezuela_tz = pytz.timezone("America/Caracas")
        now_ve = datetime.now(venezuela_tz)
        pago_dict = pago.dict()
        pago_dict["fechaRegistro"] = now_ve.strftime("%Y-%m-%d")
        pago_dict["horaRegistro"] = now_ve.strftime("%H:%M:%S")
        collection = get_collection("PAGOSCPP")
        result = await collection.insert_one(pago_dict)
        return {"message": "Pago registrado exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pagoscpp")
async def listar_pagos_cpp(cuentaPorPagarId: str = Query(...)):
    try:
        collection = get_collection("PAGOSCPP")
        pagos = await collection.find({"cuentaPorPagarId": cuentaPorPagarId}).to_list(length=100)
        pagos = [pago_to_dict(p) for p in pagos]
        return pagos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pagoscpp/all")
async def listar_todos_los_pagos_cpp():
    try:
        collection = get_collection("PAGOSCPP")
        pagos = await collection.find({}).to_list(length=1000)
        pagos = [pago_to_dict(p) for p in pagos]
        return pagos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/pagoscpp/{pago_id}/estado")
async def actualizar_estado_pago_cpp(pago_id: str, body: EstadoUpdate):
    try:
        collection = get_collection("PAGOSCPP")
        result = await collection.update_one(
            {"_id": ObjectId(pago_id)},
            {"$set": {"estado": body.estado}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Pago no encontrado o estado sin cambios")
        return {"message": "Estado actualizado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
