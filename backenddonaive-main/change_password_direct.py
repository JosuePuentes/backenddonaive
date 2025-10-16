#!/usr/bin/env python3
"""
Script directo para cambiar la contraseña del admin a 'salchipapa'
Ejecutar con: python change_password_direct.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Agregar el directorio app al path
sys.path.append(str(Path(__file__).parent))

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    import certifi
    from passlib.context import CryptContext
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Falta instalar dependencias: {e}")
    print("Instala con: pip install motor passlib python-dotenv certifi")
    sys.exit(1)

# Cargar variables de entorno
load_dotenv()

# Configuración para hashear contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def change_admin_password():
    """Cambia la contraseña del usuario admin a 'salchipapa'"""
    
    # Configuración de conexión
    MONGO_URI = os.getenv("MONGO_URI")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "RAPIFARMA")
    
    if not MONGO_URI:
        print("Error: MONGO_URI no está definido en las variables de entorno")
        print("Sugerencia: Crea un archivo .env con MONGO_URI=tu_conexion_mongodb")
        return False
    
    try:
        # Conectar a MongoDB
        print("Conectando a MongoDB...")
        client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client[DATABASE_NAME]
        usuarios_collection = db["USUARIOS"]
        
        # Buscar el usuario admin
        admin_user = await usuarios_collection.find_one({"correo": "admin@gmail.com"})
        if not admin_user:
            print("Error: No se encontró el usuario admin@gmail.com")
            return False
        
        print(f"Usuario admin encontrado: {admin_user['_id']}")
        print(f"Correo: {admin_user['correo']}")
        
        # Hashear la nueva contraseña
        nueva_contraseña = "salchipapa"
        nueva_contraseña_hash = pwd_context.hash(nueva_contraseña)
        
        print(f"Nueva contraseña: {nueva_contraseña}")
        print(f"Hash generado: {nueva_contraseña_hash[:50]}...")
        
        # Actualizar la contraseña en la base de datos
        result = await usuarios_collection.update_one(
            {"correo": "admin@gmail.com"},
            {"$set": {"contraseña": nueva_contraseña_hash}}
        )
        
        if result.modified_count == 0:
            print("Error: No se pudo actualizar la contraseña")
            return False
        
        print("Contraseña actualizada exitosamente")
        
        # Verificar el cambio
        admin_updated = await usuarios_collection.find_one({"correo": "admin@gmail.com"})
        if admin_updated:
            print("Verificación: Hash actualizado en la base de datos")
            print(f"Usuario ID: {admin_updated['_id']}")
        
        print("Operación completada exitosamente")
        print(f"Nueva contraseña para admin@gmail.com: {nueva_contraseña}")
        return True
        
    except Exception as e:
        print(f"Error durante la operación: {str(e)}")
        return False
    
    finally:
        # Cerrar conexión
        if 'client' in locals():
            client.close()
            print("Conexión cerrada")

async def main():
    """Función principal"""
    print("Iniciando cambio de contraseña para admin...")
    print("Nueva contraseña: salchipapa")
    print("=" * 50)
    
    success = await change_admin_password()
    
    if success:
        print("=" * 50)
        print("Contraseña cambiada exitosamente")
        print("Ahora puedes hacer login con:")
        print("   Correo: admin@gmail.com")
        print("   Contraseña: salchipapa")
    else:
        print("=" * 50)
        print("Error al cambiar la contraseña")
        print("Verifica tu conexión a MongoDB y las variables de entorno")

if __name__ == "__main__":
    asyncio.run(main())
