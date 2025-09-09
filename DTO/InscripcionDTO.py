from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import datetime

@dataclass
class InscripcionDTO:
    __entity__: str = "Inscripcion"
    id: Optional[int] = None
    fecha: Optional[datetime.date] = None
    estudiante_id: Optional[int] = None 
    periodo_id: Optional[int] = None  

    def to_dict(self) -> Dict[str, Any]:
        
        if self.fecha:
            self.fecha = self.fecha.isoformat()  
        data = asdict(self)
        data.pop("id", None)
        return data

    def to_dictid(self) -> Dict[str, Any]:
        if self.fecha:
            self.fecha = self.fecha.isoformat() 
        data = asdict(self) 
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InscripcionDTO":
        return cls(**data)
