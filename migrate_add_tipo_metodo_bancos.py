"""
Script de migración para agregar campo tipo_metodo a bancos existentes.

Este script:
1. Busca todos los bancos que no tienen el campo tipo_metodo
2. Les asigna el valor por defecto "pago_movil"
3. Actualiza los documentos en la base de datos

Ejecutar: python migrate_add_tipo_metodo_bancos.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Cargar variables de entorno
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Obtener configuración de MongoDB
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "rapifarma")

if not MONGO_URI:
    print("ERROR: No se encontró MONGO_URI o MONGODB_URI en las variables de entorno")
    exit(1)

async def migrar_bancos():
    """Migra bancos existentes para agregar tipo_metodo"""
    try:
        # Conectar a MongoDB
        client = AsyncIOMotorClient(MONGO_URI)
        db = client[DATABASE_NAME]
        bancos_collection = db["BANCOS"]
        
        print(f"[MIGRACION] Conectado a MongoDB: {DATABASE_NAME}")
        
        # Buscar bancos que no tienen tipo_metodo
        bancos_sin_tipo = await bancos_collection.find({
            "$or": [
                {"tipo_metodo": {"$exists": False}},
                {"tipo_metodo": None}
            ]
        }).to_list(length=None)
        
        print(f"[MIGRACION] Encontrados {len(bancos_sin_tipo)} bancos sin tipo_metodo")
        
        if len(bancos_sin_tipo) == 0:
            print("[MIGRACION] No hay bancos que migrar. Todos ya tienen tipo_metodo.")
            return
        
        # Actualizar cada banco
        actualizados = 0
        for banco in bancos_sin_tipo:
            banco_id = banco.get("_id")
            numero_cuenta = banco.get("numero_cuenta", banco.get("numeroCuenta", "N/A"))
            
            try:
                result = await bancos_collection.update_one(
                    {"_id": banco_id},
                    {"$set": {"tipo_metodo": "pago_movil"}}
                )
                
                if result.modified_count > 0:
                    actualizados += 1
                    print(f"[MIGRACION] ✅ Banco actualizado: {numero_cuenta} (ID: {banco_id})")
                else:
                    print(f"[MIGRACION] ⚠️  Banco no modificado: {numero_cuenta} (ID: {banco_id})")
                    
            except Exception as e:
                print(f"[MIGRACION] ❌ Error al actualizar banco {numero_cuenta}: {str(e)}")
                continue
        
        print(f"\n[MIGRACION] ✅ Migración completada: {actualizados} bancos actualizados")
        
    except Exception as e:
        print(f"[MIGRACION] ❌ Error crítico: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        if 'client' in locals():
            client.close()
            print("[MIGRACION] Conexión cerrada")

if __name__ == "__main__":
    print("=" * 60)
    print("Script de migración: Agregar tipo_metodo a bancos")
    print("=" * 60)
    asyncio.run(migrar_bancos())

