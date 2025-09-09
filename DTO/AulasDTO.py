from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Aula
@dataclass
class AulaDTO:
    __entity__: str = "Aula"
    id: Optional[int] = None
    numero: Optional[str] = None
    nombre: Optional[str] = None
    modulo_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AulaDTO":
        return cls(**data)
