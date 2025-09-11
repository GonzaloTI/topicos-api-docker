# task_manager.py
from datetime import date
import datetime
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

class TaskWorker(threading.Thread):
    def __init__(
        self,
        cola: Cola,
        dborm,                      
        name: Optional[str] = None,
        bzpop_timeout: int = 1   
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
                #print(f"procesando tarea: {tarea}")
                #print(f"Procesando tarea: {tarea.id} con método: {tarea.metodo.value}")
                
                if handler is None:
                    raise ValueError(f"Método no soportado: {tarea.metodo.value}")

                resultado = handler(tarea)  # Ejecuta el handler de la tarea
                #print(f"Tarea {tarea.id} completada con éxito. Resultado: {resultado}")
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

  
       # -------- handlers por metodo GET , POST, UPDATE--------
    @db_session
    def _handle_get(self, tarea: Tarea):
        #print("entrada get para procesar con worker generico", tarea)
        dto_data = json.loads(tarea.payload)
        entity_name = dto_data.get("__entity__")
        Modelo = getattr(self.dborm.db, entity_name, None)
        
        query = Modelo.select()
        
        result = [item.to_full_dict() for item in query]

        return result

    @db_session
    def _handle_post(self, tarea: Tarea):
        #print("entrada en post para procesar con worker generico", tarea)

        dto_data = json.loads(tarea.payload)
        entity_name = dto_data.get("__entity__")

        Modelo = getattr(self.dborm.db, entity_name, None)
        if Modelo is None:
            raise ValueError(f"Modelo '{entity_name}' no existe en dborm.db.")

        data = {k: v for k, v in dto_data.items() if k != "__entity__" and k != "id" and k != "__identificadores__"}

        #print("datos a procesar ", data)
        
        # Recorrer campos para convertir relaciones
        for attr, val in list(data.items()):
            if val is None:
                continue

            if '_id' in attr:  # Si el campo contiene '_id'
                rel_name = attr.split('_id')[0]
                if rel_name in Modelo._adict_:  
                    RelatedEntity = Modelo._adict_[rel_name].py_type
                    data[rel_name] = RelatedEntity[val]  # obtener la entidad por PK
                    data.pop(attr)

        # Crear entidad genérica
        result = Modelo(**data)
        return result.to_full_dict()

    @db_session
    def _handle_update(self, tarea: Tarea):
        #print("entrada en update para procesar generico", tarea)
        dto = json.loads(tarea.payload)
        entity_name = dto.get("__entity__")
        
        Modelo = getattr(self.dborm.db, entity_name, None)
        if Modelo is None:
            raise ValueError(f"Modelo '{entity_name}' no existe en dborm.db.")
        
        if "id" in dto and dto["id"] is not None:
            obj = Modelo.get(id=dto["id"])
        else:
            # Si no hay id, buscar entre los identificadores definidos en '__identificadores__'
            identificadores = dto.get("__identificadores__", "").split(",")
            for identificador in identificadores:
                if identificador in dto and dto[identificador] is not None:
                    obj = Modelo.get(**{identificador: dto[identificador]})  # Buscar por identificador alternativo
                    if obj:
                        break

        if obj is None:
            raise ValueError(f"No existe {entity_name} con los identificadores proporcionados.")
                     
        attrs = Modelo._adict_

        for key, value in dto.items():
            if key in ("__entity__", "id"):
                continue
            if value is None:
                continue  # no tocar campos None

            # actualizar referencia hacia una relación con *_id
            if key.endswith("_id"):
                nombre_relacion = key[:-3]
                atributo_relacion = attrs.get(nombre_relacion)
                if atributo_relacion and getattr(atributo_relacion, "is_relation", False) and not getattr(atributo_relacion, "is_collection", False):
                    EntidadRelacionada = atributo_relacion.py_type
                    objeto_relacion = EntidadRelacionada.get(id=value)
                    if objeto_relacion is None:
                        raise ValueError(f"No existe {EntidadRelacionada.__name__} con id={value} para '{nombre_relacion}'.")
                    setattr(obj, nombre_relacion, objeto_relacion)
                continue


            # actualizar campos presentes (simples o relaciones ya resueltas fuera)
            if key in attrs:
                setattr(obj, key, value)

        commit()        
                    
            ##actualizar los campos, que esteen presentes , nada mas , 
        
        return obj.to_full_dict()

