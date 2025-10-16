# Módulo de Modificación de Usuarios

## 📋 Descripción
Módulo completo para la gestión de usuarios con endpoints REST seguros, incluyendo listado, actualización y eliminación de usuarios.

## 🔐 Endpoints Implementados

### 1. **GET /usuarios** - Listar Usuarios
```http
GET /usuarios
Authorization: Bearer <token_admin>
```

**Respuesta:**
```json
{
  "usuarios": [
    {
      "_id": "6830cadaf1916150d7f1d600",
      "correo": "admin@gmail.com",
      "farmacias": {...},
      "permisos": [...]
    }
  ]
}
```

**Características:**
- ✅ Solo admin puede acceder
- ✅ Excluye contraseñas de la respuesta
- ✅ Serializa ObjectId a string

### 2. **PATCH /usuarios/{id}** - Actualizar Usuario
```http
PATCH /usuarios/6830cadaf1916150d7f1d600
Authorization: Bearer <token_admin>
Content-Type: application/json

{
  "contraseña": "nueva_contraseña",
  "farmacias": {...},
  "permisos": [...]
}
```

**Respuesta:**
```json
{
  "usuario": {
    "_id": "6830cadaf1916150d7f1d600",
    "correo": "admin@gmail.com",
    "farmacias": {...},
    "permisos": [...]
  }
}
```

**Características:**
- ✅ Solo admin puede actualizar
- ✅ Hashea automáticamente contraseñas
- ✅ Protege campos críticos
- ✅ Valida ObjectId

### 3. **DELETE /usuarios/{id}** - Eliminar Usuario
```http
DELETE /usuarios/6830cadaf1916150d7f1d600
Authorization: Bearer <token_admin>
```

**Respuesta:**
```json
{
  "deleted": true
}
```

**Características:**
- ✅ Solo admin puede eliminar
- ✅ Protege al usuario admin de ser eliminado
- ✅ Valida ObjectId

## 🛡️ Seguridad Implementada

### Autenticación y Autorización
- **JWT Required**: Todos los endpoints requieren token válido
- **Admin Only**: Solo `admin@gmail.com` puede ejecutar operaciones
- **Password Hashing**: Contraseñas se hashean automáticamente con bcrypt

### Protecciones de Datos
- **No Password Exposure**: Las contraseñas nunca se devuelven en respuestas
- **Admin Protection**: No se puede eliminar al usuario admin
- **Input Validation**: Validación de ObjectId y campos requeridos

## 🔧 Uso Práctico

### Cambiar Contraseña del Admin
```bash
# 1. Login como admin
POST /auth/login
{
  "correo": "admin@gmail.com",
  "contraseña": "contraseña_actual"
}

# 2. Cambiar contraseña
PATCH /usuarios/6830cadaf1916150d7f1d600
Authorization: Bearer <token>
{
  "contraseña": "salchipapa"
}
```

### Gestionar Usuarios
```bash
# Listar todos los usuarios
GET /usuarios
Authorization: Bearer <token_admin>

# Actualizar permisos de un usuario
PATCH /usuarios/USER_ID
Authorization: Bearer <token_admin>
{
  "permisos": ["ver_inicio", "agregar_cuadre"]
}

# Eliminar usuario (excepto admin)
DELETE /usuarios/USER_ID
Authorization: Bearer <token_admin>
```

## 📁 Archivos Modificados

### `app/routes/auth.py`
- ✅ `GET /usuarios` - Listar usuarios
- ✅ `PATCH /usuarios/{id}` - Actualizar usuario
- ✅ `DELETE /usuarios/{id}` - Eliminar usuario

### Dependencias
- `fastapi` - Framework web
- `motor` - Driver asíncrono de MongoDB
- `passlib` - Hashing de contraseñas
- `python-dotenv` - Variables de entorno

## 🚀 Instalación y Configuración

### 1. Instalar Dependencias
```bash
pip install fastapi motor passlib python-dotenv certifi
```

### 2. Configurar Variables de Entorno
```env
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=RAPIFARMA
SECRET_KEY=tu_secret_key
ALGORITHM=HS256
```

### 3. Ejecutar Servidor
```bash
uvicorn app.main:app --reload
```

## 🧪 Testing

### Test de Endpoints
```bash
# Test listar usuarios
curl -X GET "http://localhost:8000/usuarios" \
  -H "Authorization: Bearer <token>"

# Test actualizar usuario
curl -X PATCH "http://localhost:8000/usuarios/6830cadaf1916150d7f1d600" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"contraseña": "salchipapa"}'

# Test eliminar usuario
curl -X DELETE "http://localhost:8000/usuarios/USER_ID" \
  -H "Authorization: Bearer <token>"
```

## 📊 Estructura de Usuario

```json
{
  "_id": "ObjectId",
  "correo": "string",
  "contraseña": "hash_bcrypt",
  "farmacias": {
    "01": "santa elena",
    "02": "rapifarma"
  },
  "permisos": [
    "ver_inicio",
    "agregar_cuadre",
    "verificar_cuadres"
  ]
}
```

## ⚠️ Consideraciones

1. **Solo Admin**: Todos los endpoints están restringidos al usuario admin
2. **Password Security**: Las contraseñas se hashean automáticamente
3. **Admin Protection**: No se puede eliminar al usuario admin
4. **ObjectId Validation**: Se valida el formato de los IDs de MongoDB
5. **No Password Return**: Las contraseñas nunca se devuelven en respuestas

## 🔄 Flujo de Trabajo

1. **Autenticación**: Usuario admin hace login
2. **Autorización**: Token JWT se valida en cada request
3. **Operación**: Se ejecuta la operación CRUD correspondiente
4. **Respuesta**: Se devuelve resultado sin exponer datos sensibles

---

**Estado**: ✅ Implementado y Funcional  
**Última Actualización**: $(date)  
**Versión**: 1.0.0
