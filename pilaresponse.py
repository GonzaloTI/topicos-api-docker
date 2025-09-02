'''representa una clase cache para las respuesats'''
from respuesta import Respuesta

class PilaResponseCache:
    def __init__(self):
        self._respuestas = {}

    def set_respuesta(self, id_tarea, resultado):
        """Guarda una instancia de Respuesta."""
        self._respuestas[id_tarea] = Respuesta(id_tarea, resultado)

    def get_respuesta(self, id_tarea):
        """Retorna el dict serializable."""
        res = self._respuestas.get(id_tarea)
        return res.to_dict() if res else None

    def eliminar_respuesta(self, id_tarea):
        if id_tarea in self._respuestas:
            del self._respuestas[id_tarea]

    def existe(self, id_tarea):
        return id_tarea in self._respuestas
