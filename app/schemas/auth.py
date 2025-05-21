from pydantic import BaseModel
from typing import Optional

class LoginInput(BaseModel):
    correo: str
    contraseña: str

class Cuadre(BaseModel):
    dia: str
    cajaNumero: int
    tasa: float
    turno: str
    cajero: str
    totalCajaSistemaBs: float
    devolucionesBs: float
    recargaBs: float
    pagomovilBs: float
    puntoDebitoBs: float
    puntoCreditoBs: float
    efectivoBs: float
    totalBs: float
    totalBsEnUsd: float
    efectivoUsd: float
    zelleUsd: float
    totalGeneralUsd: float
    diferenciaUsd: float
    delete: Optional[bool] = False