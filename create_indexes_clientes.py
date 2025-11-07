"""
Script para crear índices recomendados en la colección CLIENTES.
Ejecutar una vez después de implementar los endpoints de clientes.

Uso:
    python create_indexes_clientes.py
"""

import asyncio
import os
from motor.motorengine import MotorClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/rapifarma")


async def create_indexes():
    """Crear índices recomendados para la colección CLIENTES"""
    try:
        client = MotorClient(MONGODB_URI)
        db = client.get_database()
        clientes_collection = db["CLIENTES"]
        
        print("Creando índices para la colección CLIENTES...")
        
        # Índice único en cédula (para evitar duplicados)
        await clientes_collection.create_index("cedula", unique=True)
        print("✅ Índice único creado en 'cedula'")
        
        # Índice de texto para búsqueda por nombre y cédula
        await clientes_collection.create_index([("nombre", "text"), ("cedula", "text")])
        print("✅ Índice de texto creado en 'nombre' y 'cedula'")
        
        # Índice en email (opcional, para búsquedas rápidas)
        await clientes_collection.create_index("email")
        print("✅ Índice creado en 'email'")
        
        # Índice en fecha_creacion (para ordenar por fecha)
        await clientes_collection.create_index("fecha_creacion")
        print("✅ Índice creado en 'fecha_creacion'")
        
        print("\n✅ Todos los índices se crearon exitosamente!")
        
        # Listar índices creados
        indexes = await clientes_collection.list_indexes().to_list(length=None)
        print("\nÍndices actuales en CLIENTES:")
        for idx in indexes:
            print(f"  - {idx.get('name')}: {idx.get('key')}")
        
    except Exception as e:
        print(f"❌ Error al crear índices: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())

