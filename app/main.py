from fastapi import FastAPI, Depends, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI(title="Rapifarma Backend", version="1.0.0")

# Exception handler para errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Maneja errores de validación y devuelve mensajes más claros"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error.get("loc", []))
        msg = error.get("msg", "Error de validación")
        error_type = error.get("type", "unknown")
        errors.append(f"{field}: {msg} (tipo: {error_type})")
    
    error_msg = f"Error de validación: {'; '.join(errors)}"
    print(f"[VALIDATION-ERROR] {error_msg}")
    print(f"[VALIDATION-ERROR] Path: {request.url.path}")
    print(f"[VALIDATION-ERROR] Body recibido: {await request.body()}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": error_msg, "errors": exc.errors()}
    )

# Configurar CORS primero para que siempre esté disponible
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.donaive.com.ve",
        "https://donaive.com.ve",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints básicos que siempre funcionan
@app.get("/")
async def root():
    return {"message": "API funcionando - Deploy actualizado", "version": "1.0.0", "commit": "478af4c", "farmacias_resumen": "disponible"}

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

@app.get("/debug/routes")
async def debug_routes():
    """Endpoint de diagnóstico para verificar qué rutas están registradas"""
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else []
            })
    return {
        "total_routes": len(routes),
        "routes": sorted(routes, key=lambda x: x["path"])
    }

# Importar dependencias y agregar endpoints complejos
try:
    print("🔄 Iniciando importación de módulos...")
    from app.api.v1.routes_example import router as example_router
    print("✅ example_router importado")
    from app.routes import auth, metas
    print("✅ auth y metas importados")
    from app.routes.pagoscpp import router as pagoscpp_router
    print("✅ pagoscpp_router importado")
    from app.routes.cuadres import router as cuadres
    print("✅ cuadres importado")
    from app.routes.punto_venta import router as punto_venta_router
    print("✅ punto_venta_router importado")
    from app.routes.clientes import router as clientes_router
    print("✅ clientes_router importado")
    from app.routes.compras import router as compras_router
    print("✅ compras_router importado")
    from app.core.get_current_user import get_current_user
    print("✅ get_current_user importado")
    from app.db.mongo import get_collection
    print("✅ get_collection importado")
    from bson import ObjectId
    from bson.errors import InvalidId
    from typing import List
    from datetime import datetime
    print("✅ Todas las importaciones básicas completadas")
    
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
    
    @app.get("/usuarios/me")
    async def obtener_usuario_actual(usuario: dict = Depends(get_current_user)):
        """Obtener información del usuario actual autenticado"""
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
    
    @app.get("/modificar-usuarios")
    async def modificar_usuarios(usuario: dict = Depends(get_current_user)):
        """Endpoint para el módulo de modificar usuarios - Retorna todos los usuarios"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede acceder a este módulo")

        usuarios_collection = get_collection("USUARIOS")
        items = []
        async for u in usuarios_collection.find({}, {"contraseña": 0}):
            u["_id"] = str(u["_id"])
            items.append(u)
        return {"usuarios": items}
    
    @app.get("/modificar-usuarios/me")
    async def obtener_usuario_actual_modificar(usuario: dict = Depends(get_current_user)):
        """Obtener información del usuario actual desde el módulo de modificar usuarios"""
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
            
            return {"usuario": usuario_actualizado}
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[OBTENER-USUARIO-ACTUAL-MODIFICAR] Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al obtener usuario actual: {str(e)}"
            )

    @app.get("/modificar-usuarios/{id}")
    async def obtener_usuario_modificar(id: str, usuario: dict = Depends(get_current_user)):
        """Obtener usuario específico por ID desde el módulo de modificar usuarios - Solo admin"""
        if usuario.get("correo") != "admin@gmail.com":
            raise HTTPException(status_code=403, detail="Solo el usuario admin puede ver usuarios")

        try:
            oid = ObjectId(id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="ID inválido")

        usuarios_collection = get_collection("USUARIOS")
        # Obtener usuario con permisos actualizados desde la BD
        usuario_obj = await usuarios_collection.find_one({"_id": oid}, {"contraseña": 0})
        
        if not usuario_obj:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        usuario_obj["_id"] = str(usuario_obj["_id"])
        return {"usuario": usuario_obj}

    @app.patch("/modificar-usuarios/{id}")
    async def actualizar_usuario_modificar(id: str, data: dict = Body(...), usuario: dict = Depends(get_current_user)):
        """Actualizar usuario desde el módulo de modificar usuarios - Solo admin"""
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
        
        # Devolver usuario actualizado sin contraseña con permisos actualizados desde la BD
        actualizado = await usuarios_collection.find_one({"_id": oid}, {"contraseña": 0})
        actualizado["_id"] = str(actualizado["_id"])
        return {"usuario": actualizado}

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

    # Endpoint para obtener bancos
    @app.get("/bancos")
    async def obtener_bancos(usuario: dict = Depends(get_current_user)):
        """
        Obtiene la lista de bancos disponibles.
        Retorna solo bancos activos (activo: true).
        Requiere autenticación.
        
        Estructura de respuesta esperada por el frontend:
        {
          "bancos": [
            {
              "_id": "...",
              "numero_cuenta": "...",
              "nombre_banco": "...",
              "nombre_titular": "...",
              "saldo": 0.0,
              "divisa": "USD",
              "activo": true
            }
          ]
        }
        """
        try:
            # Intentar obtener desde colección BANCOS
            try:
                bancos_collection = get_collection("BANCOS")
                # Filtrar solo bancos activos
                bancos = await bancos_collection.find({"activo": True}).to_list(length=None)
                
                if bancos and len(bancos) > 0:
                    resultado = []
                    for banco in bancos:
                        # Normalizar saldo: asegurar que siempre sea un float con valor por defecto 0.0
                        saldo_banco = banco.get("saldo")
                        if saldo_banco is None:
                            saldo_banco = 0.0
                        else:
                            try:
                                saldo_banco = float(saldo_banco)
                            except (ValueError, TypeError):
                                saldo_banco = 0.0
                        
                        banco_dict = {
                            "_id": str(banco.get("_id", "")),
                            "numero_cuenta": banco.get("numero_cuenta", banco.get("numeroCuenta", "")),
                            "nombre_banco": banco.get("nombre_banco", banco.get("nombreBanco", banco.get("nombre", banco.get("banco", "")))),
                            "nombre_titular": banco.get("nombre_titular", banco.get("nombreTitular", "")),
                            "saldo": saldo_banco,  # Siempre será un float, nunca None
                            "divisa": banco.get("divisa", "USD"),
                            "activo": banco.get("activo", True),
                            "tipo_metodo": banco.get("tipo_metodo", "pago_movil")  # Valor por defecto si no existe
                        }
                        resultado.append(banco_dict)
                    
                    print(f"[OBTENER-BANCOS] Encontrados {len(resultado)} bancos activos en colección BANCOS")
                    return {"bancos": resultado}
            except Exception as e:
                print(f"[OBTENER-BANCOS] No se encontró colección BANCOS o error al buscar: {str(e)}")
            
            # Si no hay colección BANCOS o está vacía, retornar lista vacía
            # El frontend manejará la lista vacía
            print(f"[OBTENER-BANCOS] No se encontraron bancos, retornando lista vacía")
            return {"bancos": []}
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[OBTENER-BANCOS] Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al obtener bancos: {str(e)}"
            )

    # Endpoint para crear un banco
    @app.post("/bancos")
    async def crear_banco(
        data: dict = Body(...),
        usuario: dict = Depends(get_current_user)
    ):
        """
        Crea un nuevo banco.
        Requiere autenticación.
        
        Estructura de request esperada:
        {
          "numero_cuenta": "...",
          "nombre_banco": "...",
          "nombre_titular": "...",
          "saldo": 0.0,  // opcional, por defecto 0
          "divisa": "USD",  // opcional, por defecto "USD"
          "activo": true  // opcional, por defecto true
        }
        
        Estructura de respuesta:
        {
          "_id": "...",
          "numero_cuenta": "...",
          "nombre_banco": "...",
          "nombre_titular": "...",
          "saldo": 0.0,
          "divisa": "USD",
          "activo": true
        }
        """
        try:
            # Log para debugging
            print(f"[CREAR-BANCO] Datos recibidos: {data}")
            print(f"[CREAR-BANCO] Tipo de datos: {type(data)}")
            
            # Validar campos requeridos
            numero_cuenta = data.get("numero_cuenta") or data.get("numeroCuenta")
            nombre_banco = data.get("nombre_banco") or data.get("nombreBanco") or data.get("nombre")
            nombre_titular = data.get("nombre_titular") or data.get("nombreTitular")
            
            print(f"[CREAR-BANCO] Campos extraídos - numero_cuenta: {numero_cuenta}, nombre_banco: {nombre_banco}, nombre_titular: {nombre_titular}")
            
            if not numero_cuenta:
                print(f"[CREAR-BANCO] ERROR: Falta campo 'numero_cuenta'")
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'numero_cuenta' es requerido"
                )
            
            if not nombre_banco:
                print(f"[CREAR-BANCO] ERROR: Falta campo 'nombre_banco'")
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'nombre_banco' es requerido"
                )
            
            if not nombre_titular:
                print(f"[CREAR-BANCO] ERROR: Falta campo 'nombre_titular'")
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'nombre_titular' es requerido"
                )
            
            # Obtener valores opcionales con defaults
            saldo = float(data.get("saldo", 0) or 0)
            divisa = data.get("divisa", "USD")
            activo = data.get("activo", True)
            tipo_metodo = data.get("tipo_metodo", "pago_movil")
            
            # Validar que divisa sea USD o BS
            if divisa not in ["USD", "BS"]:
                raise HTTPException(
                    status_code=400,
                    detail="El campo 'divisa' debe ser 'USD' o 'BS'"
                )
            
            # Validar que tipo_metodo sea uno de los valores permitidos
            tipos_metodo_permitidos = ["pago_movil", "efectivo", "zelle", "tarjeta_debit", "tarjeta_credito", "vales"]
            if tipo_metodo not in tipos_metodo_permitidos:
                raise HTTPException(
                    status_code=400,
                    detail=f"El campo 'tipo_metodo' debe ser uno de: {', '.join(tipos_metodo_permitidos)}"
                )
            
            # Verificar si ya existe un banco con el mismo número de cuenta
            bancos_collection = get_collection("BANCOS")
            banco_existente = await bancos_collection.find_one({
                "numero_cuenta": numero_cuenta
            })
            
            if banco_existente:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un banco con el número de cuenta {numero_cuenta}"
                )
            
            # Crear documento del banco
            nuevo_banco = {
                "numero_cuenta": numero_cuenta,
                "nombre_banco": nombre_banco,
                "nombre_titular": nombre_titular,
                "saldo": saldo,
                "divisa": divisa,
                "activo": activo,
                "tipo_metodo": tipo_metodo,
                "fecha_creacion": datetime.now().isoformat(),
                "usuario_creacion": usuario.get("correo", usuario.get("usuarioCorreo", ""))
            }
            
            # Insertar en la base de datos
            resultado = await bancos_collection.insert_one(nuevo_banco)
            banco_id = str(resultado.inserted_id)
            
            print(f"[CREAR-BANCO] Banco creado con ID: {banco_id}, número de cuenta: {numero_cuenta}")
            
            # Retornar el banco creado
            return {
                "_id": banco_id,
                "numero_cuenta": numero_cuenta,
                "nombre_banco": nombre_banco,
                "nombre_titular": nombre_titular,
                "saldo": saldo,
                "divisa": divisa,
                "activo": activo,
                "tipo_metodo": tipo_metodo
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[CREAR-BANCO] Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear banco: {str(e)}"
            )

    # Endpoint para obtener movimientos de un banco
    @app.get("/bancos/{banco_id}/movimientos")
    async def obtener_movimientos_banco(
        banco_id: str,
        usuario: dict = Depends(get_current_user)
    ):
        """
        Obtiene los movimientos de un banco específico.
        Requiere autenticación.
        
        Retorna una lista de movimientos asociados al banco.
        """
        try:
            # Validar que el banco existe
            bancos_collection = get_collection("BANCOS")
            try:
                banco_oid = ObjectId(banco_id)
            except InvalidId:
                raise HTTPException(
                    status_code=400,
                    detail="ID de banco inválido"
                )
            
            banco = await bancos_collection.find_one({"_id": banco_oid})
            if not banco:
                raise HTTPException(
                    status_code=404,
                    detail="Banco no encontrado"
                )
            
            print(f"[OBTENER-MOVIMIENTOS-BANCO] Buscando movimientos para banco: {banco_id}")
            
            # Buscar movimientos en diferentes colecciones posibles
            movimientos = []
            
            # 1. Buscar en colección MOVIMIENTOS_BANCOS (si existe)
            try:
                movimientos_collection = get_collection("MOVIMIENTOS_BANCOS")
                movimientos_docs = await movimientos_collection.find({
                    "banco_id": banco_id
                }).sort("fecha", -1).to_list(length=None)
                
                for mov in movimientos_docs:
                    mov["_id"] = str(mov["_id"])
                    movimientos.append(mov)
                
                print(f"[OBTENER-MOVIMIENTOS-BANCO] Encontrados {len(movimientos_docs)} movimientos en MOVIMIENTOS_BANCOS")
            except Exception as e:
                print(f"[OBTENER-MOVIMIENTOS-BANCO] No se encontró colección MOVIMIENTOS_BANCOS: {str(e)}")
            
            # 2. Buscar en PAGOS_CPP donde el banco es emisor o receptor
            try:
                pagos_collection = get_collection("PAGOS_CPP")
                # Buscar por bancoEmisor o bancoReceptor (puede ser ID o nombre)
                numero_cuenta = banco.get("numero_cuenta", "")
                nombre_banco = banco.get("nombre_banco", banco.get("nombreBanco", ""))
                
                # Buscar por ID del banco
                pagos_por_id = await pagos_collection.find({
                    "$or": [
                        {"bancoEmisor": banco_id},
                        {"bancoReceptor": banco_id}
                    ]
                }).sort("fecha", -1).to_list(length=None)
                
                # Buscar por número de cuenta o nombre de banco
                pagos_por_nombre = await pagos_collection.find({
                    "$or": [
                        {"bancoEmisor": numero_cuenta},
                        {"bancoReceptor": numero_cuenta},
                        {"bancoEmisor": nombre_banco},
                        {"bancoReceptor": nombre_banco}
                    ]
                }).sort("fecha", -1).to_list(length=None)
                
                # Combinar y evitar duplicados
                pagos_encontrados = {}
                for pago in pagos_por_id + pagos_por_nombre:
                    pago_id = str(pago.get("_id", ""))
                    if pago_id not in pagos_encontrados:
                        pago["_id"] = pago_id
                        pago["tipo"] = "pago_cpp"  # Identificar el tipo de movimiento
                        pagos_encontrados[pago_id] = pago
                
                movimientos.extend(list(pagos_encontrados.values()))
                print(f"[OBTENER-MOVIMIENTOS-BANCO] Encontrados {len(pagos_encontrados)} pagos en PAGOS_CPP")
            except Exception as e:
                print(f"[OBTENER-MOVIMIENTOS-BANCO] Error al buscar en PAGOS_CPP: {str(e)}")
            
            # Ordenar todos los movimientos por fecha (más recientes primero)
            movimientos_ordenados = sorted(
                movimientos,
                key=lambda x: x.get("fecha", x.get("fechaRegistro", x.get("fecha_creacion", ""))),
                reverse=True
            )
            
            print(f"[OBTENER-MOVIMIENTOS-BANCO] Total de movimientos encontrados: {len(movimientos_ordenados)}")
            
            return {
                "banco_id": banco_id,
                "numero_cuenta": banco.get("numero_cuenta", ""),
                "nombre_banco": banco.get("nombre_banco", banco.get("nombreBanco", "")),
                "movimientos": movimientos_ordenados,
                "total": len(movimientos_ordenados)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[OBTENER-MOVIMIENTOS-BANCO] Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al obtener movimientos del banco: {str(e)}"
            )

    # Endpoint para actualizar un banco
    @app.put("/bancos/{banco_id}")
    async def actualizar_banco(
        banco_id: str,
        data: dict = Body(...),
        usuario: dict = Depends(get_current_user)
    ):
        """
        Actualiza un banco existente.
        Requiere autenticación.
        
        Estructura de request esperada:
        {
          "numero_cuenta": "...",  // opcional
          "nombre_banco": "...",  // opcional
          "nombre_titular": "...",  // opcional
          "saldo": 0.0,  // opcional
          "divisa": "USD",  // opcional
          "activo": true,  // opcional
          "tipo_metodo": "pago_movil"  // opcional
        }
        
        Estructura de respuesta:
        {
          "_id": "...",
          "numero_cuenta": "...",
          "nombre_banco": "...",
          "nombre_titular": "...",
          "saldo": 0.0,
          "divisa": "USD",
          "activo": true,
          "tipo_metodo": "pago_movil"
        }
        """
        try:
            # Validar ID de banco
            try:
                banco_oid = ObjectId(banco_id)
            except InvalidId:
                raise HTTPException(
                    status_code=400,
                    detail="ID de banco inválido"
                )
            
            # Verificar que el banco existe
            bancos_collection = get_collection("BANCOS")
            banco_existente = await bancos_collection.find_one({"_id": banco_oid})
            if not banco_existente:
                raise HTTPException(
                    status_code=404,
                    detail="Banco no encontrado"
                )
            
            # Preparar datos de actualización
            update_data = {}
            
            # Campos opcionales que se pueden actualizar
            if "numero_cuenta" in data:
                numero_cuenta = data.get("numero_cuenta") or data.get("numeroCuenta")
                if numero_cuenta:
                    # Verificar que no exista otro banco con el mismo número de cuenta
                    banco_duplicado = await bancos_collection.find_one({
                        "numero_cuenta": numero_cuenta,
                        "_id": {"$ne": banco_oid}
                    })
                    if banco_duplicado:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Ya existe otro banco con el número de cuenta {numero_cuenta}"
                        )
                    update_data["numero_cuenta"] = numero_cuenta
            
            if "nombre_banco" in data:
                nombre_banco = data.get("nombre_banco") or data.get("nombreBanco") or data.get("nombre")
                if nombre_banco:
                    update_data["nombre_banco"] = nombre_banco
            
            if "nombre_titular" in data:
                nombre_titular = data.get("nombre_titular") or data.get("nombreTitular")
                if nombre_titular:
                    update_data["nombre_titular"] = nombre_titular
            
            if "saldo" in data:
                saldo = data.get("saldo")
                if saldo is not None:
                    update_data["saldo"] = float(saldo)
            
            if "divisa" in data:
                divisa = data.get("divisa")
                if divisa:
                    if divisa not in ["USD", "BS"]:
                        raise HTTPException(
                            status_code=400,
                            detail="El campo 'divisa' debe ser 'USD' o 'BS'"
                        )
                    update_data["divisa"] = divisa
            
            if "activo" in data:
                activo = data.get("activo")
                if activo is not None:
                    update_data["activo"] = bool(activo)
            
            if "tipo_metodo" in data:
                tipo_metodo = data.get("tipo_metodo")
                if tipo_metodo:
                    tipos_metodo_permitidos = ["pago_movil", "efectivo", "zelle", "tarjeta_debit", "tarjeta_credito", "vales"]
                    if tipo_metodo not in tipos_metodo_permitidos:
                        raise HTTPException(
                            status_code=400,
                            detail=f"El campo 'tipo_metodo' debe ser uno de: {', '.join(tipos_metodo_permitidos)}"
                        )
                    update_data["tipo_metodo"] = tipo_metodo
            
            # Si no hay nada que actualizar
            if not update_data:
                raise HTTPException(
                    status_code=400,
                    detail="No se proporcionaron campos para actualizar"
                )
            
            # Agregar fecha de actualización
            update_data["fecha_actualizacion"] = datetime.now().isoformat()
            update_data["usuario_actualizacion"] = usuario.get("correo", usuario.get("usuarioCorreo", ""))
            
            # Actualizar banco
            result = await bancos_collection.update_one(
                {"_id": banco_oid},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Banco no encontrado"
                )
            
            # Obtener banco actualizado
            banco_actualizado = await bancos_collection.find_one({"_id": banco_oid})
            
            # Retornar el banco actualizado
            return {
                "_id": str(banco_actualizado.get("_id", "")),
                "numero_cuenta": banco_actualizado.get("numero_cuenta", ""),
                "nombre_banco": banco_actualizado.get("nombre_banco", banco_actualizado.get("nombreBanco", "")),
                "nombre_titular": banco_actualizado.get("nombre_titular", banco_actualizado.get("nombreTitular", "")),
                "saldo": float(banco_actualizado.get("saldo", 0) or 0),
                "divisa": banco_actualizado.get("divisa", "USD"),
                "activo": banco_actualizado.get("activo", True),
                "tipo_metodo": banco_actualizado.get("tipo_metodo", "pago_movil")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"[ACTUALIZAR-BANCO] Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error al actualizar banco: {str(e)}"
            )

    # Registrar routers
    print("🔄 Registrando routers...")
    app.include_router(example_router, prefix="/api/v1")
    print("✅ example_router registrado")
    app.include_router(auth.router, tags=["auth"]) # auth.router now only contains login and admin-specific endpoints
    print("✅ auth.router registrado")
    app.include_router(pagoscpp_router)
    print("✅ pagoscpp_router registrado")
    app.include_router(metas.router, tags=["metas"])
    print("✅ metas.router registrado")
    app.include_router(cuadres, prefix="/api/cuadres", tags=["cuadres"])
    print("✅ cuadres registrado")
    app.include_router(punto_venta_router, prefix="/punto-venta", tags=["punto-venta"])
    print("✅ punto_venta_router registrado")
    app.include_router(clientes_router, tags=["clientes"])
    print("✅ clientes_router registrado")
    app.include_router(compras_router, tags=["compras"])
    print("✅ compras_router registrado")
    print("✅ Todos los routers registrados exitosamente")

except Exception as e:
    import traceback
    error_trace = traceback.format_exc()
    print(f"❌ ERROR importing complex dependencies: {e}")
    print(f"❌ Full traceback:\n{error_trace}")
    # CORS ya está configurado arriba, no es necesario configurarlo de nuevo
    # Registrar al menos los routers básicos aunque haya errores
    try:
        from app.routes import auth
        app.include_router(auth.router, tags=["auth"])
        print("✅ auth.router registrado como fallback")
    except Exception as auth_error:
        print(f"❌ Error al registrar auth.router como fallback: {auth_error}")
