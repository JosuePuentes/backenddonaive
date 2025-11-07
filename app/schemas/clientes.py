from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClienteCreate(BaseModel):
    """Modelo para crear un cliente"""
    cedula: str = Field(..., description="Cédula del cliente", min_length=1)
    nombre: str = Field(..., description="Nombre completo del cliente", min_length=1)
    telefono: Optional[str] = Field(None, description="Teléfono del cliente")
    email: Optional[str] = Field(None, description="Email del cliente")
    direccion: Optional[str] = Field(None, description="Dirección del cliente")
    fecha_nacimiento: Optional[str] = Field(None, description="Fecha de nacimiento (YYYY-MM-DD)")
    notas: Optional[str] = Field(None, description="Notas adicionales sobre el cliente")


class ClienteResponse(BaseModel):
    """Modelo de respuesta para un cliente"""
    _id: str
    cedula: str
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    notas: Optional[str] = None
    fecha_creacion: Optional[str] = None
    fecha_actualizacion: Optional[str] = None
    
    class Config:
        extra = "allow"  # Permite campos adicionales que puedan existir en los clientes


class ComprasTotalResponse(BaseModel):
    """Modelo de respuesta para el total de compras de un cliente"""
    cliente_id: str
    total_usd: float
    total_bs: float
    numero_ventas: int


class ItemCompraResponse(BaseModel):
    """Modelo de respuesta para un item comprado por un cliente"""
    producto_id: str
    nombre: str
    codigo: Optional[str] = None
    cantidad: int
    precio_unitario: float
    precio_unitario_usd: Optional[float] = None
    subtotal: float
    subtotal_usd: Optional[float] = None
    fecha_venta: str
    numero_factura: Optional[str] = None

