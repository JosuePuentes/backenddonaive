from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.db.mongo import get_collection
from app.core.config import SECRET_KEY, ALGORITHM

# Configuración para obtener el token del header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Valida el token JWT y retorna el usuario autenticado.
    Requiere que el frontend envíe el header: Authorization: Bearer <token>
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales. Asegúrate de enviar el header 'Authorization: Bearer <token>' en la petición.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not token:
            print("[AUTH] ERROR: Token no proporcionado en la petición")
            raise credentials_exception
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        if correo is None:
            print(f"[AUTH] ERROR: Token no contiene 'sub' (correo)")
            raise credentials_exception
    except JWTError as e:
        print(f"[AUTH] ERROR: Token JWT inválido o expirado: {str(e)}")
        raise credentials_exception
    except Exception as e:
        print(f"[AUTH] ERROR: Error al decodificar token: {str(e)}")
        raise credentials_exception
    
    usuarios = get_collection("USUARIOS")
    usuario = await usuarios.find_one({"correo": correo})
    if usuario is None:
        print(f"[AUTH] ERROR: Usuario no encontrado en BD: {correo}")
        raise credentials_exception
    
    usuario["_id"] = str(usuario["_id"])
    return usuario
