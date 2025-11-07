"""
Script para resetear la contraseña del usuario admin.
Ejecutar: python reset_admin_password.py
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
import certifi
from app.core.config import MONGO_URI
from app.core.auth import hashear_contraseña

async def reset_admin_password():
    """Resetea la contraseña del usuario admin a 'donaiveadmin'"""
    try:
        print(f"🔌 Conectando a MongoDB...")
        client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client["RAPIFARMA"]  # Usar el mismo nombre de BD que usa el backend
        usuarios_collection = db["USUARIOS"]
        
        # Buscar usuario admin
        correo_admin = "admin@gmail.com"
        print(f"🔍 Buscando usuario: {correo_admin}")
        
        usuario = await usuarios_collection.find_one({"correo": correo_admin})
        
        if not usuario:
            print(f"❌ ERROR: Usuario {correo_admin} no encontrado en la base de datos")
            print("💡 Creando usuario admin...")
            
            # Crear usuario admin si no existe
            nueva_contraseña = "donaiveadmin"
            contraseña_hash = hashear_contraseña(nueva_contraseña)
            
            nuevo_usuario = {
                "correo": correo_admin,
                "contraseña": contraseña_hash,
                "permisos": [
                    "ver_inicio",
                    "ver_about",
                    "agregar_cuadre",
                    "ver_cuadres_dia",
                    "verificar_cuadres",
                    "editar_cuadre",
                    "eliminar_cuadre",
                    "agregar_gasto",
                    "ver_gastos",
                    "verificar_gastos",
                    "editar_gasto",
                    "eliminar_gasto",
                    "ver_inventario",
                    "agregar_inventario",
                    "editar_inventario",
                    "eliminar_inventario",
                    "ver_usuarios",
                    "crear_usuarios",
                    "editar_usuarios",
                    "eliminar_usuarios",
                    "admin_completo",
                    "ver_reportes",
                    "configurar_sistema",
                    "gestionar_clientes"
                ],
                "farmacias": {}
            }
            
            result = await usuarios_collection.insert_one(nuevo_usuario)
            print(f"✅ Usuario admin creado exitosamente con ID: {result.inserted_id}")
            print(f"📧 Correo: {correo_admin}")
            print(f"🔑 Contraseña: {nueva_contraseña}")
            return
        
        # Resetear contraseña
        nueva_contraseña = "donaiveadmin"
        contraseña_hash = hashear_contraseña(nueva_contraseña)
        
        print(f"🔄 Reseteando contraseña para usuario: {correo_admin}")
        
        result = await usuarios_collection.update_one(
            {"correo": correo_admin},
            {"$set": {"contraseña": contraseña_hash}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Contraseña reseteada exitosamente")
            print(f"📧 Correo: {correo_admin}")
            print(f"🔑 Nueva contraseña: {nueva_contraseña}")
        else:
            print(f"⚠️  La contraseña no se modificó (puede que ya sea la misma)")
            print(f"📧 Correo: {correo_admin}")
            print(f"🔑 Contraseña actual: {nueva_contraseña}")
        
        client.close()
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    print("=" * 50)
    print("RESETEAR CONTRASEÑA DE ADMIN")
    print("=" * 50)
    asyncio.run(reset_admin_password())
    print("=" * 50)

