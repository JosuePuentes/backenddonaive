"""
Script para cambiar la contraseña del usuario admin@gmail.com a 'donaiveadmin'
Usa la misma conexión que el backend.
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.mongo import get_collection
from app.core.auth import hashear_contraseña

async def cambiar_password_admin():
    """Cambia la contraseña del usuario admin@gmail.com a 'donaiveadmin'"""
    try:
        print("=" * 60)
        print("CAMBIAR CONTRASEÑA DE ADMIN")
        print("=" * 60)
        
        usuarios_collection = get_collection("USUARIOS")
        correo_admin = "admin@gmail.com"
        
        print(f"🔍 Buscando usuario: {correo_admin}")
        
        # Buscar usuario admin
        usuario = await usuarios_collection.find_one({"correo": correo_admin})
        
        if not usuario:
            print(f"❌ ERROR: Usuario {correo_admin} no encontrado en la base de datos")
            print("💡 El usuario admin no existe. Debes crearlo primero.")
            return False
        
        print(f"✅ Usuario encontrado: {correo_admin}")
        print(f"📋 ID: {usuario.get('_id')}")
        
        # Cambiar contraseña
        nueva_contraseña = "donaiveadmin"
        contraseña_hash = hashear_contraseña(nueva_contraseña)
        
        print(f"🔄 Cambiando contraseña a: {nueva_contraseña}")
        
        result = await usuarios_collection.update_one(
            {"correo": correo_admin},
            {"$set": {"contraseña": contraseña_hash}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Contraseña cambiada exitosamente")
            print(f"📧 Correo: {correo_admin}")
            print(f"🔑 Nueva contraseña: {nueva_contraseña}")
            print("=" * 60)
            return True
        else:
            print(f"⚠️  La contraseña no se modificó (puede que ya sea la misma)")
            print(f"📧 Correo: {correo_admin}")
            print(f"🔑 Contraseña: {nueva_contraseña}")
            print("=" * 60)
            return True  # Aún así es exitoso si ya tenía esa contraseña
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return False

if __name__ == "__main__":
    asyncio.run(cambiar_password_admin())

