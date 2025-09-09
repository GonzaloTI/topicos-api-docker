from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class PlanDeEstudioDTO:
    __entity__: str = "PlanDeEstudio"   # nombre de la entidad en PonyORM
    __identificadores__:str="id,codigo" #buscar por otro atributo unico
    id: Optional[int] = None
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    fecha: Optional[str] = None         # "YYYY-MM-DD"
    estado: Optional[str] = None
    carrera_id: Optional[int] = None

    # Convierte DTO → dict serializable (para Redis o JSON)
    def to_dict(self) -> Dict[str, Any]:
        if self.fecha:
            self.fecha = self.fecha.isoformat()  
        data = asdict(self)  # Convierte el objeto en un diccionario
        data.pop("id", None)  # Elimina el campo 'id' si existe
        return data
    
    def to_dictid(self) -> Dict[str, Any]:
        if self.fecha:
            self.fecha = self.fecha.isoformat()  
        data = asdict(self)  # Convierte el objeto en un diccionario
        return data

    # Convierte dict → DTO (cuando lo sacamos de Redis)
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanDeEstudioDTO":
        return cls(**data)
