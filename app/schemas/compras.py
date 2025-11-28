from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProveedorCreate(BaseModel):
    """Modelo para crear un proveedor"""
    nombre: str = Field(..., description="Nombre del proveedor", min_length=1)
    rif: Optional[str] = Field(None, description="RIF del proveedor")
    telefono: Optional[str] = Field(None, description="Teléfono del proveedor")
    email: Optional[str] = Field(None, description="Email del proveedor")
    direccion: Optional[str] = Field(None, description="Dirección del proveedor")
    contacto: Optional[str] = Field(None, description="Nombre de contacto")
    notas: Optional[str] = Field(None, description="Notas adicionales sobre el proveedor")
    dias_credito: Optional[int] = Field(0, description="Días de crédito del proveedor", ge=0)
    descuento_comercial: Optional[float] = Field(0, description="Descuento comercial (%)", ge=0, le=100)
    descuento_pronto_pago: Optional[float] = Field(0, description="Descuento por pronto pago (%)", ge=0, le=100)


class ProveedorResponse(BaseModel):
    """Modelo de respuesta para un proveedor"""
    _id: str
    nombre: str
    rif: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    contacto: Optional[str] = None
    notas: Optional[str] = None
    dias_credito: Optional[int] = 0
    descuento_comercial: Optional[float] = 0
    descuento_pronto_pago: Optional[float] = 0
    fecha_creacion: Optional[str] = None
    fecha_actualizacion: Optional[str] = None
    estado: Optional[str] = "activo"
    
    class Config:
        extra = "allow"  # Permite campos adicionales que puedan existir en los proveedores


class ItemCompra(BaseModel):
    """Modelo para un item de compra"""
    codigo: str = Field(..., description="Código del producto")
    nombre: str = Field(..., description="Nombre del producto")
    cantidad: int = Field(..., description="Cantidad comprada", gt=0)
    costo_unitario: float = Field(..., description="Costo unitario del producto", gt=0)
    precio_unitario: Optional[float] = Field(None, description="Precio unitario de venta")
    lote: Optional[str] = Field(None, description="Número de lote")
    fecha_vencimiento: Optional[str] = Field(None, description="Fecha de vencimiento (YYYY-MM-DD)")
    descripcion: Optional[str] = Field(None, description="Descripción adicional del item")
    lleva_iva: Optional[bool] = Field(False, description="Si el item lleva IVA")


class CompraCreate(BaseModel):
    """Modelo para crear una compra"""
    proveedor_id: str = Field(..., description="ID del proveedor")
    farmacia: str = Field(..., description="Código de la farmacia")
    sucursal: Optional[str] = Field(None, description="ID de la sucursal")
    sucursal_id: Optional[str] = Field(None, description="ID de la sucursal (alias de sucursal)")
    numero_factura: Optional[str] = Field(None, description="Número de factura")
    numero_control: Optional[str] = Field(None, description="Número de control")
    fecha_compra: str = Field(..., description="Fecha de compra (YYYY-MM-DD)")
    fecha_vencimiento_factura: Optional[str] = Field(None, description="Fecha de vencimiento de la factura (YYYY-MM-DD)")
    items: List[ItemCompra] = Field(..., description="Lista de items comprados", min_items=1)
    total: float = Field(..., description="Total de la compra", gt=0)
    divisa: str = Field(..., description="Divisa de la compra (BS o USD)", pattern="^(BS|USD)$")
    tasa: Optional[float] = Field(None, description="Tasa de cambio si la divisa es BS", gt=0)
    lleva_iva: Optional[bool] = Field(False, description="Si la compra lleva IVA")
    iva: Optional[float] = Field(0, description="Monto del IVA (16% sobre costo ajustado)", ge=0)
    notas: Optional[str] = Field(None, description="Notas adicionales sobre la compra")


class CompraResponse(BaseModel):
    """Modelo de respuesta para una compra"""
    _id: str
    proveedor_id: str
    proveedor_nombre: Optional[str] = None
    farmacia: str
    sucursal: Optional[str] = None
    sucursal_id: Optional[str] = None
    numero_factura: Optional[str] = None
    numero_control: Optional[str] = None
    fecha_compra: str
    fecha_vencimiento_factura: Optional[str] = None
    items: List[dict] = []
    total: float
    divisa: str
    tasa: Optional[float] = None
    lleva_iva: Optional[bool] = False
    iva: Optional[float] = 0
    total_con_iva: Optional[float] = None
    notas: Optional[str] = None
    usuario_creacion: Optional[str] = None
    fecha_creacion: Optional[str] = None
    estado: Optional[str] = "activa"
    estado_pago: Optional[str] = "sin_pago"  # sin_pago, abonado, pagada
    monto_pagado: Optional[float] = 0
    monto_pendiente: Optional[float] = None
    dias_credito: Optional[int] = 0
    dias_mora: Optional[int] = 0
    
    class Config:
        extra = "allow"  # Permite campos adicionales que puedan existir en las compras


class PagoCompraCreate(BaseModel):
    """Modelo para crear un pago de compra"""
    monto: float = Field(..., description="Monto del pago", gt=0)
    fecha_pago: str = Field(..., description="Fecha del pago (YYYY-MM-DD)")
    metodo_pago: str = Field(..., description="Método de pago (efectivo, transferencia, cheque, etc.)")
    referencia: Optional[str] = Field(None, description="Referencia del pago (número de cheque, transferencia, etc.)")
    notas: Optional[str] = Field(None, description="Notas adicionales sobre el pago")


class PagoCompraResponse(BaseModel):
    """Modelo de respuesta para un pago de compra"""
    _id: str
    compra_id: str
    monto: float
    fecha_pago: str
    metodo_pago: str
    referencia: Optional[str] = None
    notas: Optional[str] = None
    usuario_creacion: Optional[str] = None
    fecha_creacion: Optional[str] = None
    
    class Config:
        extra = "allow"

