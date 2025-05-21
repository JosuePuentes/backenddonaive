import asyncio
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import certifi
# Conexión a MongoDB
client = AsyncIOMotorClient("mongodb+srv://rapifarma:30780142@cluster0.9nirn5t.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",tlsCAFile=certifi.where())
db = client["RAPIFARMA"]
print("Conexión a MongoDB establecida.", client)
# Obtener una colección
def get_collection(nombre: str) -> AsyncIOMotorCollection:
    return db[nombre]

# Hasheo de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Crear un usuario básico
async def crear_usuario_basico(correo: str, contraseña: str) -> dict:
    usuarios_collection = get_collection("USUARIOS")
    # Verificar si ya existe un usuario con ese correo
    usuario_existente = await usuarios_collection.find_one({"correo": correo})
    if usuario_existente:
        raise ValueError("Ya existe un usuario con ese correo.")

    # Hashear contraseña
    contraseña_segura = pwd_context.hash(contraseña)

    # Insertar usuario
    nuevo_usuario = {
        "correo": correo,
        "contraseña": contraseña_segura
    }

    resultado = await usuarios_collection.insert_one(nuevo_usuario)

    return {
        "id": str(resultado.inserted_id),
        "correo": correo
    }

# Función de prueba
async def main():
    try:
        nuevo = await crear_usuario_basico("admin@gmail.com", "admin")
        print("Usuario creado:", nuevo)
    except ValueError as e:
        print("Error:", str(e))

# Ejecutar como script
if __name__ == "__main__":
    asyncio.run(main())
