from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Docente
@dataclass
class DocenteDTO:
    __entity__: str = "Docente"
    id: Optional[int] = None
    registro: Optional[str] = None
    ci: Optional[str] = None
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    otros: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocenteDTO":
        return cls(**data)