from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# GrupoMateria
@dataclass
class GrupoMateriaDTO:
    __entity__: str = "GrupoMateria"
    id: Optional[int] = None
    grupo: Optional[str] = None
    nombre: Optional[str] = None
    estado: Optional[str] = None
    materia_id: Optional[int] = None
    docente_id: Optional[int] = None
    periodo_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GrupoMateriaDTO":
        return cls(**data)
