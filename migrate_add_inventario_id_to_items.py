"""
Script de migración para agregar inventario_id a los items existentes en inventarios.

Este script:
1. Itera sobre todos los inventarios en la colección INVENTARIOS
2. Para cada inventario, actualiza todos sus items para incluir el inventario_id
3. Solo actualiza items que no tengan inventario_id (para evitar sobrescribir)

Ejecutar con:
python migrate_add_inventario_id_to_items.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent))

from app.db.mongo import get_collection
from bson import ObjectId
from bson.errors import InvalidId

async def migrate_items_inventario_id():
    """
    Migra los items existentes para agregar el campo inventario_id.
    """
    try:
        collection = get_collection("INVENTARIOS")
        
        # Obtener todos los inventarios
        inventarios = await collection.find({}).to_list(length=None)
        
        total_inventarios = len(inventarios)
        total_items_actualizados = 0
        total_items_ya_tienen_id = 0
        inventarios_procesados = 0
        
        print(f"[MIGRACIÓN] Encontrados {total_inventarios} inventarios para procesar")
        
        for inventario in inventarios:
            inventario_id = str(inventario.get("_id"))
            items = inventario.get("items", [])
            
            if not items:
                print(f"[MIGRACIÓN] Inventario {inventario_id} no tiene items, saltando...")
                continue
            
            items_actualizados = 0
            items_ya_tienen_id = 0
            
            # Actualizar cada item que no tenga inventario_id
            for idx, item in enumerate(items):
                # Verificar si el item ya tiene inventario_id
                if item.get("inventario_id"):
                    items_ya_tienen_id += 1
                    continue
                
                # Agregar inventario_id al item
                update_field = f"items.{idx}.inventario_id"
                result = await collection.update_one(
                    {"_id": ObjectId(inventario_id)},
                    {"$set": {update_field: inventario_id}}
                )
                
                if result.modified_count > 0:
                    items_actualizados += 1
            
            total_items_actualizados += items_actualizados
            total_items_ya_tienen_id += items_ya_tienen_id
            inventarios_procesados += 1
            
            if items_actualizados > 0:
                print(f"[MIGRACIÓN] Inventario {inventario_id}: {items_actualizados} items actualizados, {items_ya_tienen_id} ya tenían inventario_id")
        
        print("\n" + "="*60)
        print("[MIGRACIÓN] RESUMEN:")
        print(f"  Inventarios procesados: {inventarios_procesados}/{total_inventarios}")
        print(f"  Items actualizados: {total_items_actualizados}")
        print(f"  Items que ya tenían inventario_id: {total_items_ya_tienen_id}")
        print("="*60)
        print("[MIGRACIÓN] Migración completada exitosamente")
        
    except Exception as e:
        print(f"[MIGRACIÓN] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    print("Iniciando migración para agregar inventario_id a items existentes...")
    print("="*60)
    asyncio.run(migrate_items_inventario_id())

