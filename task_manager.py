# task_manager.py
import json
import base64
import cloudpickle
import threading
from typing import Optional, Dict, Any, Callable

from pony.orm import db_session, commit
from DTO.PlanDeEstudioDTO import PlanDeEstudioDTO
from tarea import Tarea, Metodo, Estado
from cola import Cola


class WorkerManager:
    def __init__(self, cola: Cola, dborm, num_workers: int = 1, bzpop_timeout: int = 1):
        self.workers = [
            TaskWorker(cola=cola, dborm=dborm, name=f"Worker-{i+1}", bzpop_timeout=bzpop_timeout)
            for i in range(num_workers)
        ]

    def start(self):
        for w in self.workers:
            w.start()

    def pause_all(self):
        for w in self.workers:
            w.pause()

    def resume_all(self):
        for w in self.workers:
            w.resume()

    def stop_all(self):
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.join(timeout=2.0)

# ------Worker -----------------------------------

def _loads_base64_maybe(s):
    """retorna el objeto de cloudpickle"""
    if not isinstance(s, str):
        return s
    try:
        return cloudpickle.loads(base64.b64decode(s.encode("utf-8")))
    except Exception:
        return s


class TaskWorker(threading.Thread):
    def __init__(
        self,
        cola: Cola,
        dborm,                      
        name: Optional[str] = None,
        bzpop_timeout: int = 5      
    ):
        super().__init__(daemon=True, name=name or "TaskWorker")
        self.cola = cola
        self.dborm = dborm
        self.bzpop_timeout = bzpop_timeout

        self._stop_event = threading.Event()
        self._run_event = threading.Event()
        self._run_event.set()  # inicia sin pausa

        self._status_hash = f"{self.cola.nombre}:status"

        self._handlers: Dict[Metodo, Callable[[Tarea], Any]] = {
            Metodo.GET: self._handle_get,
            Metodo.POST: self._handle_post,
            Metodo.PUT: self._handle_update,
            Metodo.UPDATE: self._handle_update,
        }

    # -------- control del Worker --------
    def pause(self):
        self._run_event.clear()

    def resume(self):
        self._run_event.set()

    def stop(self):
        self._stop_event.set()
        self._run_event.set()  

    # -------- loop --------
    def run(self):
        print(" Worker task_manage escuchando tareas....")
        while not self._stop_event.is_set():
            if not self._run_event.wait(timeout=self.bzpop_timeout):
                continue

            tarea: Optional[Tarea] = self.cola.obtener_bloqueante(timeout=self.bzpop_timeout)
            if tarea is None:
                continue
            tarea.marcar_procesando()
            self._save_status(tarea)

            try:
                handler = self._handlers.get(tarea.metodo)
                print(f"procesando tarea: {tarea}")
                print(f"Procesando tarea: {tarea.id} con método: {tarea.metodo.value}")
                
                if handler is None:
                    raise ValueError(f"Método no soportado: {tarea.metodo.value}")

                resultado = handler(tarea)  # Ejecuta el handler de la tarea
                print(f"Tarea {tarea.id} completada con éxito. Resultado: {resultado}")
                tarea.marcar_realizado(resultado)
                self._save_status(tarea)

            except Exception as e:
                tarea.marcar_error({"error": str(e)})
                self._save_status(tarea)

    # -------- persistencia de estado --------
    def _save_status(self, tarea: Tarea):
        data = tarea.to_dict()
        # Asegurar que payload/resultado sean serializables a JSON (fallback a repr)
        for k in ("payload", "resultado"):
            try:
                json.dumps(data.get(k))
            except Exception:
                data[k] = repr(data.get(k))
        self.cola.redis.hset(self._status_hash, tarea.id, json.dumps(data, ensure_ascii=False))

    # -------- utils de modelo --------
    def _resolve_entity_from_class(self, cls):
       
        if not hasattr(cls, "__name__"):
            raise ValueError("Modelo serializado inválido: no es una clase")
        name = cls.__name__
        Modelo = getattr(self.dborm.db, name, None)
        if Modelo is None:
            raise ValueError(f"Modelo '{name}' no existe en dborm.db")
        return Modelo

    def _obj_to_dict(self, obj):
        if hasattr(obj, "to_full_dict"): return obj.to_full_dict()
        if hasattr(obj, "to_dict"):      return obj.to_dict()
        return obj.to_dict()

  
       # -------- handlers por metodo GET , POST, UPDATE--------
    @db_session
    def _handle_get(self, tarea: Tarea):
       
        dto_data = json.loads(tarea.payload) 
        dto = PlanDeEstudioDTO.from_dict(dto_data)  
        Modelo = getattr(self.dborm.db, dto.__entity__)  

        query = Modelo.select()
        
        result = [item.to_full_dict() for item in query]

        return result

  
    @db_session
    def _handle_post(self, tarea: Tarea):
       
        return None

    @db_session
    def _handle_update(self, tarea: Tarea):
        
        return None

