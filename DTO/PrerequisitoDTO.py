from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Prerequisito
@dataclass
class PrerequisitoDTO:
    __entity__: str = "Prerequisito"
    id: Optional[int] = None
    materia_id: Optional[int] = None
    materia_id_requisito: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data
    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrerequisitoDTO":
        return cls(**data)
