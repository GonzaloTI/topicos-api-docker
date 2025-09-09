from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Estudiante
@dataclass
class EstudianteDTO:
    __entity__: str = "Estudiante"
    __identificadores__: str = "id,registro,ci"
    id: Optional[int] = None
    registro: Optional[str] = None
    ci: Optional[str] = None
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    correo: Optional[str] = None
    otros: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EstudianteDTO":
        return cls(**data)
