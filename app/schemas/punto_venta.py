from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TasaCambioResponse(BaseModel):
    fecha: str
    tasa: float
    divisa: str = "Bs/USD"


class LoteProducto(BaseModel):
    """Modelo para un lote en la respuesta de productos"""
    lote: Optional[str] = None  # numero_lote
    fecha_vencimiento: Optional[str] = None
    cantidad: Optional[int] = None


class StockPorSucursal(BaseModel):
    """Modelo para stock por sucursal"""
    sucursal_id: str
    sucursal_nombre: Optional[str] = None
    cantidad: int  # Stock total (suma de lotes si existen)
    stock: int  # Alias para compatibilidad


class ProductoItem(BaseModel):
    id: str
    nombre: str
    codigo: Optional[str] = None
    precio: float
    precio_usd: Optional[float] = None
    stock: int  # Alias para compatibilidad
    cantidad: Optional[int] = None  # Stock total (suma de lotes si existen)
    stock_por_sucursal: Optional[List[StockPorSucursal]] = []  # REQUERIDO: Stock en todas las sucursales
    lotes: Optional[List[LoteProducto]] = []  # Array de lotes
    sucursal: Optional[str] = None


class MetodoPago(BaseModel):
    tipo: str  # "efectivo", "tarjeta", "transferencia", etc.
    monto: float
    divisa: str = "Bs"  # "Bs" o "USD"


class ItemVenta(BaseModel):
    producto_id: str
    nombre: str
    codigo: Optional[str] = None
    cantidad: int
    precio_unitario: float  # Precio en Bs CON descuento
    precio_unitario_usd: Optional[float] = None  # Precio en USD CON descuento
    precio_unitario_original: Optional[float] = None  # Precio original en Bs SIN descuento
    precio_unitario_original_usd: Optional[float] = None  # Precio original en USD SIN descuento
    subtotal: float  # Subtotal en Bs CON descuento
    subtotal_usd: Optional[float] = None  # Subtotal en USD CON descuento
    descuento_aplicado: Optional[float] = None  # Porcentaje de descuento aplicado al item


class VentaRequest(BaseModel):
    items: List[ItemVenta]
    metodos_pago: List[MetodoPago]
    total_bs: float
    total_usd: Optional[float] = None
    tasa_dia: float
    sucursal: str
    cajero: Optional[str] = None
    cliente: Optional[str] = None
    porcentaje_descuento: Optional[float] = None  # Porcentaje de descuento aplicado a toda la venta
    notas: Optional[str] = None


class VentaResponse(BaseModel):
    numero_factura: str
    fecha: str
    items: List[ItemVenta]
    metodos_pago: List[MetodoPago]
    total_bs: float
    total_usd: Optional[float] = None
    tasa_dia: float
    sucursal: str
    cajero: Optional[str] = None
    cliente: Optional[str] = None
    porcentaje_descuento: Optional[float] = None  # Porcentaje de descuento aplicado a toda la venta
    notas: Optional[str] = None
    _id: str
