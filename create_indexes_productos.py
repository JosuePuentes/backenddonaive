"""
Script para crear índices recomendados en las colecciones PRODUCTOS e INVENTARIOS.
Estos índices mejoran significativamente el rendimiento de las búsquedas de productos.

Uso:
    python create_indexes_productos.py
"""

import asyncio
import os
from motor.motorengine import MotorClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/rapifarma")


async def create_indexes():
    """Crear índices recomendados para las colecciones PRODUCTOS e INVENTARIOS"""
    try:
        client = MotorClient(MONGODB_URI)
        db = client.get_database()
        productos_collection = db["PRODUCTOS"]
        inventarios_collection = db["INVENTARIOS"]
        
        print("Creando índices para mejorar el rendimiento de búsqueda de productos...\n")
        
        # ========== ÍNDICES PARA PRODUCTOS ==========
        print("📦 Índices para colección PRODUCTOS:")
        
        # Índice de texto para búsqueda rápida por nombre, código y farmacia
        try:
            await productos_collection.create_index([
                ("nombre", "text"),
                ("codigo", "text"),
                ("farmacia", "text")
            ], name="text_search_index")
            print("  ✅ Índice de texto creado en 'nombre', 'codigo' y 'farmacia'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice de texto (puede que ya exista): {str(e)}")
        
        # Índice en código para búsquedas exactas rápidas
        try:
            await productos_collection.create_index("codigo", name="codigo_index")
            print("  ✅ Índice creado en 'codigo'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en código: {str(e)}")
        
        # Índice compuesto en estado y código (muy usado en búsquedas)
        try:
            await productos_collection.create_index([
                ("estado", 1),
                ("codigo", 1)
            ], name="estado_codigo_index")
            print("  ✅ Índice compuesto creado en 'estado' y 'codigo'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice compuesto: {str(e)}")
        
        # Índice en estado para filtrar productos activos
        try:
            await productos_collection.create_index("estado", name="estado_index")
            print("  ✅ Índice creado en 'estado'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en estado: {str(e)}")
        
        # Índice en sucursal para filtros por sucursal
        try:
            await productos_collection.create_index("sucursal", name="sucursal_index")
            print("  ✅ Índice creado en 'sucursal'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en sucursal: {str(e)}")
        
        # Índice en stock_sucursal para búsquedas por stock
        try:
            await productos_collection.create_index("stock_sucursal", name="stock_sucursal_index")
            print("  ✅ Índice creado en 'stock_sucursal'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en stock_sucursal: {str(e)}")
        
        # ========== ÍNDICES PARA INVENTARIOS ==========
        print("\n📋 Índices para colección INVENTARIOS:")
        
        # Índice compuesto en sucursal y estado (muy usado en búsquedas de lotes)
        try:
            await inventarios_collection.create_index([
                ("sucursal", 1),
                ("estado", 1)
            ], name="sucursal_estado_index")
            print("  ✅ Índice compuesto creado en 'sucursal' y 'estado'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice compuesto: {str(e)}")
        
        # Índice en estado para filtrar inventarios activos
        try:
            await inventarios_collection.create_index("estado", name="estado_index")
            print("  ✅ Índice creado en 'estado'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en estado: {str(e)}")
        
        # Índice en sucursal
        try:
            await inventarios_collection.create_index("sucursal", name="sucursal_index")
            print("  ✅ Índice creado en 'sucursal'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en sucursal: {str(e)}")
        
        # Índice en items.codigo para búsquedas rápidas de items por código
        try:
            await inventarios_collection.create_index("items.codigo", name="items_codigo_index")
            print("  ✅ Índice creado en 'items.codigo'")
        except Exception as e:
            print(f"  ⚠️  Error al crear índice en items.codigo: {str(e)}")
        
        print("\n✅ Todos los índices se crearon exitosamente!")
        
        # Listar índices creados
        print("\n📊 Índices actuales en PRODUCTOS:")
        indexes = await productos_collection.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"  - {idx.get('name')}: {idx.get('key')}")
        
        print("\n📊 Índices actuales en INVENTARIOS:")
        indexes = await inventarios_collection.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"  - {idx.get('name')}: {idx.get('key')}")
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Error al crear índices: {str(e)}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(create_indexes())

