from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Carrera
@dataclass
class CarreraDTO:
    __entity__: str = "Carrera"
    id: Optional[int] = None
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    otros: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CarreraDTO":
        return cls(**data)
