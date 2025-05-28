from fastapi import APIRouter, HTTPException, Body
from app.schemas.auth import LoginInput, Cuadre
from app.services.users_service import login_y_token

from fastapi import APIRouter, Query
from typing import List, Optional
from app.db.mongo import get_collection  # tu helper para acceder a la colección
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()

class Gasto(BaseModel):
    monto: float
    titulo: str
    descripcion: str
    localidad: str
    fecha: str

@router.get("/")
async def root():
    return {"message": "API funcionando"}


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
        cuadre_dict["cajeroId"] = cuadre.cajeroId  # Store the cashier's ID
        result = collection.insert_one(cuadre_dict)
        return {"message": "Cuadre guardado", "result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cuadres")
async def agregar_cuadre(cuadre: Cuadre):
    try:
        collection = get_collection("CUADRES")
        cuadre_dict = cuadre.dict()
        cuadre_dict["fecha"] = datetime.strptime(cuadre.fecha, "%Y-%m-%d")
        # Add default estado field
        cuadre_dict["estado"] = "wait"
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
        gasto_dict["fecha"] = datetime.strptime(gasto.fecha, "%Y-%m-%d")
        # Add default estado field
        gasto_dict["estado"] = "wait"
        result = await collection.insert_one(gasto_dict)
        return {"message": "Gasto agregado exitosamente", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gastos")
async def obtener_gastos(
    localidad: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
):
    try:
        collection = get_collection("GASTOS")
        filtro = {}

        if localidad:
            filtro["localidad"] = localidad

        if fecha_inicio and fecha_fin:
            filtro["fecha"] = {
                "$gte": datetime.strptime(fecha_inicio, "%Y-%m-%d"),
                "$lte": datetime.strptime(fecha_fin, "%Y-%m-%d")
            }

        resultados = await collection.find(filtro).to_list(1000)
        for r in resultados:
            r["_id"] = str(r["_id"])
            r["fecha"] = r["fecha"].strftime("%Y-%m-%d")

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
        db = get_collection("CUADRES").database  # Obtenemos instancia de la base de datos
        colecciones = await db.list_collection_names()
        colecciones_farmacias = [nombre for nombre in colecciones if nombre.startswith("CUADRES-")]

        resultados_totales = []

        for nombre_coleccion in colecciones_farmacias:
            collection = db[nombre_coleccion]

            pipeline = [
                {
                    "$match": {
                        "dia": {
                            "$gte": startDate,
                            "$lte": endDate,
                        },
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
                    "$match": {
                        "cajeroInfo.tipocomision": {"$in": ["Turno"]}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "cajeroId": "$cajeroId",
                            "turno": "$turno"
                        },
                        # "totalVentas": {"$sum": {"$divide": ["$totalCajaSistemaBs", {"$ifNull": ["$tasa", 1]}]}},
                        "totalVentas": {"$sum": "$totalGeneralUsd"},
                        "totalSobrante": {"$sum": {"$ifNull": ["$sobranteUsd", 0]}},
                        "totalFaltante": {"$sum": {"$ifNull": ["$faltanteUsd", 0]}},
                        "cajero": {"$first": "$cajeroInfo.NOMBRE"},
                        "comisionPorcentaje": {"$first": "$cajeroInfo.comision"},
                        "farmacias": {"$first": "$cajeroInfo.FARMACIAS"}
                    }
                },
                {
                    "$project": {
                        "cajero": 1,
                        "turno": "$_id.turno",
                        "totalVentas": 1,
                        "sobrante": "$totalSobrante",
                        "faltante": "$totalFaltante",
                        "comision": {
                            "$divide": [
                                { "$multiply": ["$totalVentas", {"$toDouble": "$comisionPorcentaje"}] },
                                100
                            ]
                        },
                        "farmacias": 1,
                        "_id": 0
                    }
                }
            ]

            resultados = await collection.aggregate(pipeline).to_list(length=None)
            resultados_totales.extend(resultados)

        return resultados_totales

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

                        # "totalVentas": {"$sum": "$totalGeneralUsd"}
                    }
                }
            ]
            resultados = await collection.aggregate(pipeline).to_list(length=None)
            total_farmacia = resultados[0]["totalVentas"] if resultados else 0
            total_ventas_especial += total_farmacia

            # Buscar cajero especial para esta farmacia
            cajeros_farmacia = farmacias_cajeros.get(codigo_farmacia, [])
            cajero_especial = next((c for c in cajeros_farmacia if "Especial" in (c.get("tipocomision") or [])), None)
            if cajero_especial:
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