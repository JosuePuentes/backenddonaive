from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Rapifarma Backend", version="1.0.0")

# Endpoints básicos que siempre funcionan
@app.get("/")
async def root():
    return {"message": "API funcionando"}

@app.get("/ping")
async def ping():
    return {"message": "pong", "status": "ok"}

@app.get("/version")
async def version():
    return {"version": "1.0.0", "status": "running"}

@app.get("/test-direct")
async def test_direct():
    return {"message": "Endpoint directo funcionando", "status": "ok"}

@app.get("/test-simple")
async def test_simple():
    return {"message": "Test simple funcionando", "timestamp": "2024-01-19"}

@app.get("/health-check")
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "endpoints": ["test-direct", "test-simple", "usuarios", "farmacias/resumen"]}

# Importar dependencias y agregar endpoints complejos
try:
    from app.api.v1.routes_example import router as example_router
    from app.routes import auth, metas
    from app.routes.pagoscpp import router as pagoscpp_router
    from app.routes.cuadres import router as cuadres
    from app.core.get_current_user import get_current_user
    from app.db.mongo import get_collection
    from bson import ObjectId
    from bson.errors import InvalidId
    from typing import List
    
    # ===== ENDPOINTS DE USUARIOS DIRECTOS =====
    
    @app.get("/usuarios")
    async def listar_usuarios(usuario: dict = Depends(get_current_user)):
        """Listar todos los usuarios - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede listar usuarios")

        usuarios_collection = get_collection("USUARIOS")
        items = []
        async for u in usuarios_collection.find({}, {"contraseña": 0}):
            u["_id"] = str(u["_id"])
            items.append(u)
        return {"usuarios": items}

    @app.get("/usuarios/{id}")
    async def obtener_usuario(id: str, usuario: dict = Depends(get_current_user)):
        """Obtener usuario específico por ID - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede ver usuarios")

        try:
            oid = ObjectId(id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="ID inválido")

        usuarios_collection = get_collection("USUARIOS")
        usuario_obj = await usuarios_collection.find_one({"_id": oid}, {"contraseña": 0})
        
        if not usuario_obj:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_obj["_id"] = str(usuario_obj["_id"])
        return {"usuario": usuario_obj}

    @app.post("/usuarios")
    async def crear_usuario(data: dict = Body(...), usuario: dict = Depends(get_current_user)):
        """Crear nuevo usuario - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede crear usuarios")

        try:
            from app.core.auth import hashear_contraseña
            
            usuarios_collection = get_collection("USUARIOS")
            
            # Verificar que el correo no exista
            correo = data.get("correo")
            if not correo:
                raise HTTPException(status_code=400, detail="El correo es requerido")
            
            usuario_existente = await usuarios_collection.find_one({"correo": correo})
            if usuario_existente:
                raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")
            
            # Preparar datos del nuevo usuario
            nuevo_usuario = {
                "correo": correo,
                "contraseña": hashear_contraseña(data.get("contraseña", "123456")),
                "farmacias": data.get("farmacias", {}),
                "permisos": data.get("permisos", [
                    "ver_inicio",
                    "ver_about"
                ])
            }
            
            # Insertar usuario
            result = await usuarios_collection.insert_one(nuevo_usuario)
            
            # Devolver usuario creado sin contraseña
            usuario_creado = await usuarios_collection.find_one(
                {"_id": result.inserted_id},
                {"contraseña": 0}
            )
            usuario_creado["_id"] = str(usuario_creado["_id"])
            
            return {
                "message": "Usuario creado exitosamente",
                "usuario": usuario_creado
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

    @app.patch("/usuarios/{id}")
    async def actualizar_usuario(id: str, data: dict = Body(...), usuario: dict = Depends(get_current_user)):
        """Actualizar usuario - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede actualizar usuarios")

        try:
            oid = ObjectId(id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="ID inválido")

        usuarios_collection = get_collection("USUARIOS")
        
        # Preparar actualización
        update_fields = dict(data)
        if "contraseña" in update_fields and update_fields["contraseña"]:
            from app.core.auth import hashear_contraseña
            update_fields["contraseña"] = hashear_contraseña(update_fields["contraseña"])
        
        update_fields.pop("_id", None)
        
        result = await usuarios_collection.update_one({"_id": oid}, {"$set": update_fields})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Devolver usuario actualizado sin contraseña
        actualizado = await usuarios_collection.find_one({"_id": oid}, {"contraseña": 0})
        actualizado["_id"] = str(actualizado["_id"])
        return {"usuario": actualizado}

    @app.delete("/usuarios/{id}")
    async def eliminar_usuario(id: str, usuario: dict = Depends(get_current_user)):
        """Eliminar usuario - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede eliminar usuarios")

        try:
            oid = ObjectId(id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="ID inválido")

        usuarios_collection = get_collection("USUARIOS")
        
        # Proteger al admin de ser eliminado
        usuario_obj = await usuarios_collection.find_one({"_id": oid})
        if not usuario_obj:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if usuario_obj.get("correo") == "admin@gmail.com":
            raise HTTPException(status_code=403, detail="No se puede eliminar al usuario admin")
        
        result = await usuarios_collection.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"deleted": True}

    @app.get("/permisos")
    async def listar_permisos_disponibles():
        """Listar todos los permisos disponibles en el sistema"""
        permisos = {
            "permisos_basicos": [
                "ver_inicio",
                "ver_about"
            ],
            "permisos_cuadres": [
                "agregar_cuadre",
                "ver_cuadres_dia",
                "verificar_cuadres",
                "editar_cuadre",
                "eliminar_cuadre"
            ],
            "permisos_gastos": [
                "agregar_gasto",
                "ver_gastos",
                "verificar_gastos",
                "editar_gasto",
                "eliminar_gasto"
            ],
            "permisos_inventario": [
                "ver_inventario",
                "agregar_inventario",
                "editar_inventario",
                "eliminar_inventario"
            ],
            "permisos_usuarios": [
                "ver_usuarios",
                "crear_usuarios",
                "editar_usuarios",
                "eliminar_usuarios"
            ],
            "permisos_admin": [
                "admin_completo",
                "ver_reportes",
                "configurar_sistema"
            ]
        }
        return permisos

    @app.get("/farmacias/resumen")
    async def resumen_farmacias_con_costos():
        """Resumen de farmacias con costos totales de cuadres e inventario"""
        try:
            # Obtener farmacias
            farmacias_collection = get_collection("FARMACIAS")
            farmacias_docs = await farmacias_collection.find({}, {"_id": 0}).to_list(length=None)
            
            farmacias = {}
            for doc in farmacias_docs:
                if 'id' in doc and 'nombre' in doc:
                    farmacias[doc['id']] = doc['nombre']
                else:
                    for k, v in doc.items():
                        if k != '_id':
                            farmacias[k] = v
            
            # Obtener costos de cuadres por farmacia
            db = get_collection("CUADRES").database
            colecciones = await db.list_collection_names()
            colecciones_farmacias = [nombre for nombre in colecciones if nombre.startswith("CUADRES-")]
            
            resumen_farmacias = {}
            costoInventarioTotal = 0
            
            for nombre_coleccion in colecciones_farmacias:
                # Extraer ID de farmacia del nombre de la colección (ej: CUADRES-01 -> 01)
                farmacia_id = nombre_coleccion.split("-")[1]
                
                collection = db[nombre_coleccion]
                
                # Pipeline para sumar costos de cuadres verificados
                pipeline = [
                    {
                        "$match": {
                            "estado": "verified"
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "totalCuadres": {"$sum": 1},
                            "costoTotal": {"$sum": {"$ifNull": ["$costo", 0]}},
                            "ventasTotal": {"$sum": {"$ifNull": ["$totalCajaSistemaBs", 0]}},
                            "costoInventario": {"$sum": {"$ifNull": ["$costoInventario", 0]}}
                        }
                    }
                ]
                
                resultado = await collection.aggregate(pipeline).to_list(length=None)
                
                if resultado:
                    costoInventarioFarmacia = resultado[0]["costoInventario"]
                    costoInventarioTotal += costoInventarioFarmacia
                    
                    resumen_farmacias[farmacia_id] = {
                        "id": farmacia_id,
                        "nombre": farmacias.get(farmacia_id, f"Farmacia {farmacia_id}"),
                        "totalCuadres": resultado[0]["totalCuadres"],
                        "costoTotal": resultado[0]["costoTotal"],
                        "ventasTotal": resultado[0]["ventasTotal"] + costoInventarioFarmacia
                    }
                else:
                    resumen_farmacias[farmacia_id] = {
                        "id": farmacia_id,
                        "nombre": farmacias.get(farmacia_id, f"Farmacia {farmacia_id}"),
                        "totalCuadres": 0,
                        "costoTotal": 0,
                        "ventasTotal": 0
                    }
            
            return {
                "farmacias": resumen_farmacias,
                "totalGeneral": {
                    "totalCuadres": sum(f["totalCuadres"] for f in resumen_farmacias.values()),
                    "costoTotal": sum(f["costoTotal"] for f in resumen_farmacias.values()),
                    "ventasTotal": sum(f["ventasTotal"] for f in resumen_farmacias.values()),
                    "costoInventarioTotal": costoInventarioTotal
                }
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al obtener resumen de farmacias: {str(e)}")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # o especifica tu dominio del frontend
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(example_router, prefix="/api/v1")
    app.include_router(auth.router, tags=["auth"]) # auth.router now only contains login and admin-specific endpoints
    app.include_router(pagoscpp_router)
    app.include_router(metas.router, tags=["metas"])
    app.include_router(cuadres, prefix="/api/cuadres", tags=["cuadres"])

except Exception as e:
    print(f"Error importing complex dependencies: {e}")
    # CORS básico para endpoints simples
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )