from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# Materia
@dataclass
class MateriaDTO:
    __entity__: str = "Materia"
    __identificadores__: str = "id,sigla"
    id: Optional[int] = None
    sigla: Optional[str] = None
    nombre: Optional[str] = None
    creditos: Optional[int] = None
    plan_id: Optional[int] = None
    nivel_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data
    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MateriaDTO":
        return cls(**data)

