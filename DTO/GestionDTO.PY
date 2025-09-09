from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Gestion
@dataclass
class GestionDTO:
    __entity__: str = "Gestion"
    id: Optional[int] = None
    anio: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GestionDTO":
        return cls(**data)


# TipoPeriodo
@dataclass
class TipoPeriodoDTO:
    __entity__: str = "TipoPeriodo"
    id: Optional[int] = None
    nombre: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TipoPeriodoDTO":
        return cls(**data)
# Periodo
@dataclass
class PeriodoDTO:
    __entity__: str = "Periodo"
    id: Optional[int] = None
    numero: Optional[str] = None
    descripcion: Optional[str] = None
    gestion_id: Optional[int] = None
    tipoperiodo_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PeriodoDTO":
        return cls(**data)
