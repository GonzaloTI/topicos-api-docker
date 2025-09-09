from enum import Enum
import json
from typing import Any, Optional


class Metodo(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    UPDATE = "UPDATE"


class Prioridad(Enum):
    BAJA = 1
    MEDIA = 2
    ALTA = 3


class Estado(Enum):
    ESPERA = "espera"
    PROCESANDO = "procesando"
    REALIZADO = "realizado"
    ERROR = "error"


class Tarea:
    def __init__(
        self,
        id: str,
        metodo: Metodo,
        prioridad: Prioridad,
        payload: Any = None,
        estado: Estado = Estado.ESPERA,
        resultado: Any = None,
    ):
        if not isinstance(metodo, Metodo):
            raise ValueError("Método inválido")
        if not isinstance(prioridad, Prioridad):
            raise ValueError("Prioridad inválida")
        if not isinstance(estado, Estado):
            raise ValueError("Estado inválido")

        self.id = id
        self.metodo = metodo
        self.prioridad = prioridad
        self.payload = payload
        self.estado = estado
        self.resultado: Any = resultado  # None al inicio

    # --- Helpers de estado ---
    def marcar_procesando(self):
        self.estado = Estado.PROCESANDO

    def marcar_realizado(self, resultado: Any = None):
        self.estado = Estado.REALIZADO
        self.resultado = resultado

    def marcar_error(self, error_info: Any = None):
        self.estado = Estado.ERROR
        self.resultado = error_info

    # --- Serialización sencilla (para guardar en Redis como JSON) ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "metodo": self.metodo.value,
            "prioridad": self.prioridad.value,
            "payload": self.payload,       # OJO: debe ser JSON-serializable
            "estado": self.estado.value,
            "resultado": self.resultado,   # puede ser None
        }
   
    @staticmethod
    def from_dict(data: dict) -> "Tarea":
        return Tarea(
            id=data["id"],
            metodo=Metodo(data["metodo"]),
            prioridad=Prioridad(data["prioridad"]),
            payload=data.get("payload"),
            estado=Estado(data.get("estado", Estado.ESPERA.value)),
            resultado=data.get("resultado"),
        )

    def __repr__(self):
        return (
            f"Tarea(id={self.id}, metodo={self.metodo.value}, prioridad={self.prioridad.value}, "
            f"estado={self.estado.value}, resultado={self.resultado}, payload={self.payload})"
        )
 # --- Método de comparación para PriorityQueue ---
    def __lt__(self, other):
        # Si la prioridad es mayor, debería aparecer primero en la cola
        return self.prioridad.value < other.prioridad.value