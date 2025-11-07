# Instrucciones para el Frontend - Validación de Stock y Métodos de Pago

## ✅ Cambios en el Backend

### 1. Validación de Stock Mejorada
- ✅ El backend ahora busca el stock en los **inventarios activos** de la sucursal
- ✅ Usa el campo `cantidad` del item del inventario (no la colección PRODUCTOS)
- ✅ Si hay lotes, suma las cantidades de los lotes
- ✅ El stock se valida **antes** de registrar la venta

### 2. Validación de Métodos de Pago
- ✅ El backend ahora compara todos los montos en **USD** (no en Bs)
- ✅ Convierte automáticamente los métodos de pago en Bs a USD usando la tasa del día
- ✅ Los mensajes de error muestran valores en USD

### 3. Actualización Automática del Cuadre
- ✅ El backend actualiza automáticamente el cuadre al confirmar una venta
- ✅ **No requiere cambios en el frontend** - es automático

## Lo que el Frontend DEBE Verificar

### 1. **Métodos de Pago - Divisa Correcta** ⚠️ CRÍTICO

**Problema común:**
- El frontend envía métodos de pago en USD (ej: 3.0 USD)
- Pero el total está en Bs (ej: 360.03 Bs)
- El backend ahora valida correctamente, pero el frontend debe asegurar consistencia

**Solución:**
```javascript
// Al preparar métodos de pago, asegurar que la divisa sea correcta
const metodosPago = [
  {
    tipo: "efectivo",
    monto: 3.0,  // Si es USD, debe ser 3.0
    divisa: "USD"  // ✅ IMPORTANTE: Especificar la divisa correcta
  },
  // ... otros métodos
];

// Si el total está en Bs, convertir métodos de pago a Bs O viceversa
// Ejemplo: Si total_bs = 360.03 y tasa = 120, entonces total_usd = 3.0
// Los métodos de pago en USD deben sumar 3.0 USD
```

**Ejemplo correcto:**
```javascript
// Si el total es 360.03 Bs y la tasa es 120:
const totalBs = 360.03;
const tasaDia = 120;
const totalUsd = totalBs / tasaDia; // 3.0 USD

// Métodos de pago deben sumar 3.0 USD
const metodosPago = [
  {
    tipo: "efectivo",
    monto: 3.0,  // ✅ En USD
    divisa: "USD"  // ✅ Especificar USD
  }
];

// O si están en Bs:
const metodosPago = [
  {
    tipo: "efectivo",
    monto: 360.03,  // ✅ En Bs
    divisa: "Bs"  // ✅ Especificar Bs
  }
];
```

### 2. **Manejo de Errores de Validación** ⚠️ IMPORTANTE

**El backend ahora devuelve mensajes de error más claros:**

```javascript
// Error de métodos de pago
{
  "detail": "La suma de métodos de pago ($3.00 USD) no coincide con el total ($3.00 USD). Verifica que los montos y divisas sean correctos."
}

// Error de stock
{
  "detail": "Stock insuficiente para CEMENTO BLANCO ARGOS X 20KG (código: 2). Stock disponible: 50, solicitado: 3"
}
```

**El frontend debe:**
- Mostrar estos mensajes de error al usuario
- Verificar que los métodos de pago sumen correctamente antes de enviar
- Verificar que el stock sea suficiente antes de enviar (opcional, pero recomendado)

### 3. **Verificación de Stock Antes de Enviar** (Opcional pero Recomendado)

```javascript
// Función para verificar stock antes de enviar la venta
async function verificarStockAntesDeEnviar(items, sucursal) {
  // El backend ya valida, pero puedes hacer una verificación previa
  // usando el endpoint GET /punto-venta/productos/buscar
  for (const item of items) {
    const response = await fetch(
      `/punto-venta/productos/buscar?q=${item.codigo}&sucursal=${sucursal}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    const productos = await response.json();
    const producto = productos.find(p => p.codigo === item.codigo);
    
    if (producto) {
      const stockDisponible = producto.cantidad || producto.stock || 0;
      if (stockDisponible < item.cantidad) {
        throw new Error(
          `Stock insuficiente para ${item.nombre}. Disponible: ${stockDisponible}, Solicitado: ${item.cantidad}`
        );
      }
    }
  }
}
```

### 4. **Estructura Correcta de Métodos de Pago**

```javascript
// ✅ CORRECTO: Métodos de pago con divisa especificada
const metodosPago = [
  {
    tipo: "efectivo",
    monto: 3.0,
    divisa: "USD"  // ✅ Especificar divisa
  },
  {
    tipo: "zelle",
    monto: 1.5,
    divisa: "USD"  // ✅ Especificar divisa
  },
  {
    tipo: "transferencia",
    monto: 180.0,
    divisa: "Bs"  // ✅ Especificar divisa
  }
];

// ❌ INCORRECTO: No especificar divisa (por defecto será "Bs")
const metodosPago = [
  {
    tipo: "efectivo",
    monto: 3.0  // ❌ Sin divisa, se asume "Bs" pero el monto es en USD
  }
];
```

### 5. **Cálculo Correcto de Totales**

```javascript
// Al calcular el total, asegurar consistencia entre Bs y USD
function calcularTotales(items, tasaDia) {
  let totalBs = 0;
  let totalUsd = 0;
  
  for (const item of items) {
    totalBs += item.subtotal || (item.precio_unitario * item.cantidad);
    totalUsd += item.subtotal_usd || (item.precio_unitario_usd * item.cantidad);
  }
  
  // Verificar que totalBs / tasaDia ≈ totalUsd (con tolerancia)
  const totalUsdCalculado = totalBs / tasaDia;
  if (Math.abs(totalUsd - totalUsdCalculado) > 0.01) {
    console.warn('Inconsistencia entre totalBs y totalUsd');
    // Ajustar totalUsd al valor calculado
    totalUsd = totalUsdCalculado;
  }
  
  return { totalBs, totalUsd };
}

// Al preparar métodos de pago, asegurar que sumen el total correcto
function prepararMetodosPago(metodosPago, totalBs, totalUsd, tasaDia) {
  // Calcular suma en USD
  let sumaUsd = 0;
  for (const metodo of metodosPago) {
    if (metodo.divisa === 'USD') {
      sumaUsd += metodo.monto;
    } else {
      sumaUsd += metodo.monto / tasaDia;
    }
  }
  
  // Verificar que la suma coincida con el total
  if (Math.abs(sumaUsd - totalUsd) > 0.01) {
    throw new Error(
      `La suma de métodos de pago ($${sumaUsd.toFixed(2)} USD) no coincide con el total ($${totalUsd.toFixed(2)} USD)`
    );
  }
  
  return metodosPago;
}
```

## Checklist para el Frontend

- [ ] Verificar que los métodos de pago tengan el campo `divisa` especificado correctamente
- [ ] Asegurar que la suma de métodos de pago (en USD) coincida con el total (en USD)
- [ ] Manejar errores de validación de métodos de pago y mostrarlos al usuario
- [ ] Manejar errores de stock insuficiente y mostrarlos al usuario
- [ ] (Opcional) Verificar stock antes de enviar la venta para mejor UX
- [ ] Asegurar que `total_bs` y `total_usd` sean consistentes con la tasa del día

## Ejemplo Completo de Envío de Venta

```javascript
async function confirmarVenta(ventaData) {
  try {
    // 1. Calcular totales
    const { totalBs, totalUsd } = calcularTotales(ventaData.items, ventaData.tasa_dia);
    
    // 2. Preparar métodos de pago
    const metodosPago = prepararMetodosPago(
      ventaData.metodos_pago,
      totalBs,
      totalUsd,
      ventaData.tasa_dia
    );
    
    // 3. Preparar datos de venta
    const ventaCompleta = {
      items: ventaData.items,
      metodos_pago: metodosPago,  // ✅ Con divisa especificada
      total_bs: totalBs,
      total_usd: totalUsd,
      tasa_dia: ventaData.tasa_dia,
      sucursal: ventaData.sucursal,
      cajero: ventaData.cajero,
      cliente: ventaData.cliente,
      porcentaje_descuento: ventaData.porcentaje_descuento || 0,
      notas: ventaData.notas || ""
    };
    
    // 4. Enviar venta
    const response = await fetch('/punto-venta/ventas', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(ventaCompleta)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al registrar la venta');
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('Error al confirmar venta:', error);
    // Mostrar error al usuario
    alert(error.message);
    throw error;
  }
}
```

## Notas Importantes

1. **El backend valida automáticamente**: No es necesario validar en el frontend, pero ayuda a la UX
2. **Los mensajes de error son claros**: Úsalos para mostrar información útil al usuario
3. **El cuadre se actualiza automáticamente**: No necesitas hacer nada adicional
4. **El stock se busca en inventarios**: Asegúrate de que los productos tengan el campo `codigo` correcto

