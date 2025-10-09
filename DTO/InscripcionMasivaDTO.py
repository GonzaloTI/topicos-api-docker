from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
import datetime

@dataclass
class InscripcionMasivaDTO:
    estudiante_registro: str = "00000"
    periodo_id: Optional[int] = None  
    __entity__: str = "InscripcionMateriaList"
    
    fecha: Optional[datetime.date] = None
    grupos_ids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el DTO a un diccionario para el payload de la tarea."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InscripcionMasivaDTO":
        """Crea una instancia del DTO a partir de un diccionario (ej. JSON del request)."""
        return cls(**data)
