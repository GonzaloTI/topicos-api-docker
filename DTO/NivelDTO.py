from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Nivel
@dataclass
class NivelDTO:
    __entity__: str = "Nivel"
    id: Optional[int] = None
    nivel: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NivelDTO":
        return cls(**data)
