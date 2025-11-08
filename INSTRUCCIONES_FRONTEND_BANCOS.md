# Instrucciones para el Frontend: Endpoint POST /bancos

## Estructura de Datos Requerida

El frontend **DEBE** enviar un objeto JSON con los siguientes campos:

### Campos Requeridos (obligatorios):
- `numero_cuenta` (string): Número de cuenta bancaria
- `nombre_banco` (string): Nombre del banco
- `nombre_titular` (string): Nombre del titular de la cuenta

### Campos Opcionales:
- `saldo` (number): Saldo inicial de la cuenta (por defecto: 0)
- `divisa` (string): Moneda de la cuenta - debe ser `"USD"` o `"BS"` (por defecto: `"USD"`)
- `activo` (boolean): Si el banco está activo (por defecto: `true`)

## Ejemplo de Request

```javascript
// ✅ CORRECTO - Estructura mínima
const bancoData = {
  numero_cuenta: "0102-1234-5678-9012",
  nombre_banco: "Banco de Venezuela",
  nombre_titular: "Juan Pérez"
};

// ✅ CORRECTO - Con todos los campos
const bancoDataCompleto = {
  numero_cuenta: "0102-1234-5678-9012",
  nombre_banco: "Banco de Venezuela",
  nombre_titular: "Juan Pérez",
  saldo: 1000.0,
  divisa: "USD",
  activo: true
};

// ❌ INCORRECTO - Falta campo requerido
const bancoDataIncorrecto = {
  numero_cuenta: "0102-1234-5678-9012",
  nombre_banco: "Banco de Venezuela"
  // Falta 'nombre_titular'
};
```

## Ejemplo de Código Frontend

### Usando fetch:

```javascript
const crearBanco = async (bancoData) => {
  try {
    const response = await fetch('https://rapifarma-backend.onrender.com/bancos', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` // Token JWT requerido
      },
      body: JSON.stringify({
        numero_cuenta: bancoData.numero_cuenta,
        nombre_banco: bancoData.nombre_banco,
        nombre_titular: bancoData.nombre_titular,
        saldo: bancoData.saldo || 0,
        divisa: bancoData.divisa || "USD",
        activo: bancoData.activo !== undefined ? bancoData.activo : true
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al crear banco');
    }

    const resultado = await response.json();
    return resultado;
  } catch (error) {
    console.error('Error al crear banco:', error);
    throw error;
  }
};
```

### Usando Axios:

```javascript
import axios from 'axios';

const crearBanco = async (bancoData) => {
  try {
    const response = await axios.post(
      'https://rapifarma-backend.onrender.com/bancos',
      {
        numero_cuenta: bancoData.numero_cuenta,
        nombre_banco: bancoData.nombre_banco,
        nombre_titular: bancoData.nombre_titular,
        saldo: bancoData.saldo || 0,
        divisa: bancoData.divisa || "USD",
        activo: bancoData.activo !== undefined ? bancoData.activo : true
      },
      {
        headers: {
          'Authorization': `Bearer ${token}` // Token JWT requerido
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error al crear banco:', error.response?.data || error.message);
    throw error;
  }
};
```

## Estructura de Respuesta

El backend retorna el banco creado con la siguiente estructura:

```json
{
  "_id": "690c40be93d9d9d635fbae83",
  "numero_cuenta": "0102-1234-5678-9012",
  "nombre_banco": "Banco de Venezuela",
  "nombre_titular": "Juan Pérez",
  "saldo": 1000.0,
  "divisa": "USD",
  "activo": true
}
```

## Errores Comunes

### 400 Bad Request - "El campo 'numero_cuenta' es requerido"
**Causa**: No se está enviando el campo `numero_cuenta` en el request.

**Solución**: Asegúrate de incluir `numero_cuenta` en el objeto que envías:
```javascript
{
  numero_cuenta: "0102-1234-5678-9012", // ✅ REQUERIDO
  // ... otros campos
}
```

### 400 Bad Request - "El campo 'nombre_banco' es requerido"
**Causa**: No se está enviando el campo `nombre_banco` en el request.

**Solución**: Asegúrate de incluir `nombre_banco` en el objeto que envías:
```javascript
{
  nombre_banco: "Banco de Venezuela", // ✅ REQUERIDO
  // ... otros campos
}
```

### 400 Bad Request - "El campo 'nombre_titular' es requerido"
**Causa**: No se está enviando el campo `nombre_titular` en el request.

**Solución**: Asegúrate de incluir `nombre_titular` en el objeto que envías:
```javascript
{
  nombre_titular: "Juan Pérez", // ✅ REQUERIDO
  // ... otros campos
}
```

### 400 Bad Request - "El campo 'divisa' debe ser 'USD' o 'BS'"
**Causa**: Se está enviando un valor de `divisa` que no es "USD" ni "BS".

**Solución**: Asegúrate de que `divisa` sea exactamente `"USD"` o `"BS"`:
```javascript
{
  divisa: "USD", // ✅ CORRECTO
  // o
  divisa: "BS",  // ✅ CORRECTO
  // divisa: "usd" // ❌ INCORRECTO (minúsculas)
  // divisa: "EUR" // ❌ INCORRECTO (no permitido)
}
```

### 400 Bad Request - "Ya existe un banco con el número de cuenta {numero_cuenta}"
**Causa**: Ya existe un banco en la base de datos con el mismo `numero_cuenta`.

**Solución**: Usa un número de cuenta diferente o verifica si el banco ya existe antes de crearlo.

## Checklist para el Frontend

- [ ] El request incluye el header `Authorization: Bearer <token>`
- [ ] El request incluye el header `Content-Type: application/json`
- [ ] El body del request incluye `numero_cuenta` (string)
- [ ] El body del request incluye `nombre_banco` (string)
- [ ] El body del request incluye `nombre_titular` (string)
- [ ] Si se envía `divisa`, debe ser exactamente `"USD"` o `"BS"`
- [ ] El body está correctamente serializado como JSON (`JSON.stringify()`)
- [ ] Se manejan los errores 400, 401, 500 apropiadamente

## Notas Importantes

1. **Autenticación**: El endpoint requiere autenticación JWT. Asegúrate de incluir el token en el header `Authorization`.

2. **Nombres de campos**: El backend acepta tanto `snake_case` como `camelCase` para algunos campos, pero se recomienda usar `snake_case` para consistencia:
   - ✅ `numero_cuenta` (preferido)
   - ✅ `numeroCuenta` (también aceptado)
   - ✅ `nombre_banco` (preferido)
   - ✅ `nombreBanco` (también aceptado)
   - ✅ `nombre_titular` (preferido)
   - ✅ `nombreTitular` (también aceptado)

3. **Valores por defecto**: Si no envías `saldo`, `divisa` o `activo`, el backend usará valores por defecto:
   - `saldo`: 0
   - `divisa`: "USD"
   - `activo`: true

4. **Validación de divisa**: El backend valida estrictamente que `divisa` sea `"USD"` o `"BS"` (case-sensitive).

