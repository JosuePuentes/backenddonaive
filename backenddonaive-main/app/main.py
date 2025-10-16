from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes_example import router as example_router
from app.routes import auth, metas
from app.routes.pagoscpp import router as pagoscpp_router
from app.routes.cuadres import router as cuadres


app = FastAPI(title="Rapifarma Backend", version="1.0.0")

# Endpoint de prueba directo
@app.get("/test-direct")
async def test_direct():
    return {"message": "Endpoint directo funcionando", "status": "ok"}

# Endpoint de usuarios directo para debug
@app.get("/usuarios-debug")
async def usuarios_debug():
    return {"message": "Endpoint usuarios debug funcionando", "status": "ok"}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # o especifica tu dominio del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(example_router, prefix="/api/v1")
app.include_router(auth.router, tags=["auth", "usuarios"])
app.include_router(pagoscpp_router)
app.include_router(metas.router, tags=["metas"])
app.include_router(cuadres, prefix="/api/cuadres", tags=["cuadres"])
