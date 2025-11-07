from app.core.auth import verificar_contraseña
from app.db.mongo import get_collection
from app.core.jwt import crear_token_jwt

async def autenticar_usuario(correo: str, contraseña: str):
    """
    Autentica un usuario verificando correo y contraseña.
    Retorna el usuario si las credenciales son correctas, None en caso contrario.
    """
    try:
        users = get_collection("USUARIOS")
        usuario = await users.find_one({"correo": correo})
        
        if not usuario:
            print(f"[AUTENTICAR-USUARIO] Usuario no encontrado: {correo}")
            return None
        
        print(f"[AUTENTICAR-USUARIO] Usuario encontrado: {correo}, verificando contraseña...")
        
        # Verificar contraseña
        try:
            contraseña_valida = verificar_contraseña(contraseña, usuario.get("contraseña", ""))
            if not contraseña_valida:
                print(f"[AUTENTICAR-USUARIO] Contraseña incorrecta para: {correo}")
                return None
            
            print(f"[AUTENTICAR-USUARIO] Usuario autenticado exitosamente: {correo}")
            return usuario
        except Exception as e:
            print(f"[AUTENTICAR-USUARIO] Error al verificar contraseña: {str(e)}")
            return None
            
    except Exception as e:
        print(f"[AUTENTICAR-USUARIO] Error crítico al autenticar usuario: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

# Ejemplo de login_y_token
async def login_y_token(correo, contraseña, return_user=False):
    usuario = await autenticar_usuario(correo, contraseña)
    if not usuario:
        return None
    token = crear_token_jwt({"sub": usuario["correo"]})
    print(f"token:{token}")
    if return_user:
        return usuario, token
    return token
