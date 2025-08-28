# pila.py
import json
from pony.orm import db_session, commit
from pony.orm.core import TransactionIntegrityError

class PilaManager:
    def __init__(self, db):
        # recibimos la referencia al db de DatabaseORM
        self.Pila = db.Pila

    @db_session
    def guardar_tarea(self, instruccion, modelo, datos):
        """Guardar una nueva tarea en la pila."""
        try:
            tarea = self.Pila(
                instruccion=instruccion,
                modelo=modelo,
                datos=json.dumps(datos)
            )
            commit()
            return tarea
        except TransactionIntegrityError as e:
            raise Exception(f"Error de integridad: {str(e)}")
        except Exception as e:
            raise Exception(f"Error guardando en pila: {str(e)}")

    @db_session
    def listar(self):
        """Listar todas las tareas de la pila."""
        return [{
            "id": p.id,
            "instruccion": p.instruccion,
            "modelo": p.modelo,
            "estado": p.estado,
            "datos": p.datos
        } for p in self.Pila.select()]

    @db_session
    def actualizar_estado(self, id_tarea, nuevo_estado):
        """Actualizar el estado de una tarea."""
        tarea = self.Pila.get(id=id_tarea)
        if not tarea:
            raise Exception("Tarea no encontrada")
        tarea.estado = nuevo_estado
        commit()
        return tarea
