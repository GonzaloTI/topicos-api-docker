from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class InscripcionMateriaDTO:
    __entity__: str = "InscripcionMateria"
    
    id: Optional[int] = None
    inscripcion_id: Optional[int] = None  # Relacionado a Inscripcion
    grupo_id: Optional[int] = None        # Relacionado a GrupoMateria

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("id", None) 
        return data

    def to_dictid(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InscripcionMateriaDTO":
        return cls(**data)
