from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import datetime

# Horario
@dataclass
class HorarioDTO:
    __entity__: str = "Horario"
    id: Optional[int] = None
    dia: Optional[str] = None
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None
    grupo_id: Optional[int] = None
    aula_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None)
        return data

    def to_dictid(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HorarioDTO":
        return cls(**data)
