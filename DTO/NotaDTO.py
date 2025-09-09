from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class NotaDTO:
    __entity__: str = "Nota"
    id: Optional[int] = None
    nota: Optional[float] = None
    inscripcionmateria_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)  # El POST no necesita enviar id
        return data

    def to_dictid(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotaDTO":
        return cls(**data)