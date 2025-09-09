from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Modulo
@dataclass
class ModuloDTO:
    __entity__: str = "Modulo"
    __identificadores__: str = "id,numero"
    id: Optional[int] = None
    numero: Optional[str] = None
    nombre: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModuloDTO":
        return cls(**data)
