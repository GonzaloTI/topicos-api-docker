"""Clase que representa una respuesta a una tarea"""
class Respuesta:
    def __init__(self, id_tarea, resultado):
        self.id = id_tarea
        self.resultado = resultado

    def to_dict(self):
        return {
            "id": self.id,
            "resultado": self.resultado
        }
