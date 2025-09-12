# task_manager.py
from datetime import datetime, date
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
        """Handler mejorado para POST con mejor manejo de relaciones"""
        #print("Procesando POST con worker genérico", tarea)
        
        dto_data = json.loads(tarea.payload)
        entity_name = dto_data.get("__entity__")
        
        # Obtener el modelo
        Modelo = getattr(self.dborm.db, entity_name, None)
        if Modelo is None:
            raise ValueError(f"Modelo '{entity_name}' no existe en dborm.db.")
        
        # Filtrar datos válidos (excluir metadatos)
        data = {k: v for k, v in dto_data.items() 
                if k not in ("__entity__", "id", "__identificadores__") and v is not None}
        
        # Procesar los datos antes de crear la entidad
        processed_data = self._process_entity_data(Modelo, data)
        
        # Crear la entidad
        try:
            result = Modelo(**processed_data)
            commit()  # Asegurar que se guarde
            return result.to_full_dict()
        except Exception as e:
            raise ValueError(f"Error al crear {entity_name}: {str(e)}")
    
    @db_session
    def _handle_update(self, tarea: Tarea):
        """Handler mejorado para PUT/UPDATE con mejor manejo de relaciones"""
        #print("Procesando UPDATE con worker genérico", tarea)
        
        dto_data = json.loads(tarea.payload)
        entity_name = dto_data.get("__entity__")
        
        # Obtener el modelo
        Modelo = getattr(self.dborm.db, entity_name, None)
        if Modelo is None:
            raise ValueError(f"Modelo '{entity_name}' no existe en dborm.db.")
        
        # Buscar la entidad existente
        obj = self._find_existing_entity(Modelo, dto_data)
        if obj is None:
            raise ValueError(f"No existe {entity_name} con los identificadores proporcionados.")
        
        # Filtrar y procesar datos para actualización
        data = {k: v for k, v in dto_data.items() 
                if k not in ("__entity__", "id", "__identificadores__") and v is not None}
        
        processed_data = self._process_entity_data(Modelo, data)
        
        # Actualizar los campos
        for field_name, value in processed_data.items():
            if hasattr(obj, field_name):
                setattr(obj, field_name, value)
        
        commit()
        return obj.to_full_dict()
    
    def _find_existing_entity(self, Modelo, dto_data):
        """Buscar entidad existente por ID o identificadores alternativos"""
        # Primero intentar por ID
        if "id" in dto_data and dto_data["id"] is not None:
            return Modelo.get(id=dto_data["id"])
        
        # Si no hay ID, buscar por identificadores alternativos
        identificadores = dto_data.get("__identificadores__", "").split(",")
        for identificador in identificadores:
            identificador = identificador.strip()
            if identificador in dto_data and dto_data[identificador] is not None:
                try:
                    obj = Modelo.get(**{identificador: dto_data[identificador]})
                    if obj:
                        return obj
                except Exception:
                    continue  # Continuar con el siguiente identificador
        
        return None
    
    def _process_entity_data(self, Modelo, data):
        """Procesar datos de entrada, manejando relaciones y tipos especiales"""
        processed_data = {}
        model_attrs = Modelo._adict_
        
        for field_name, value in data.items():
            # Manejar campos con sufijo _id (referencias a relaciones)
            if field_name.endswith('_id'):
                relation_name = field_name[:-3]  # Quitar el '_id'
                
                # Verificar si existe la relación en el modelo
                if relation_name in model_attrs:
                    attr = model_attrs[relation_name]
                    
                    # Verificar si es realmente una relación
                    if hasattr(attr, 'is_relation') and attr.is_relation and not attr.is_collection:
                        # Obtener el modelo relacionado
                        RelatedEntity = attr.py_type
                        
                        # Buscar la entidad relacionada
                        related_obj = RelatedEntity.get(id=value)
                        if related_obj is None:
                            raise ValueError(f"No existe {RelatedEntity.__name__} con id={value}")
                        
                        # Asignar la relación completa, no solo el ID
                        processed_data[relation_name] = related_obj
                        continue
                
                # Si no es una relación reconocida, mantener el campo original
                processed_data[field_name] = value
                continue
            
            # Manejar campos de fecha - pero solo si realmente necesitas conversión
            if field_name in model_attrs:
                attr = model_attrs[field_name]
                if hasattr(attr, 'py_type'):
                    # Solo convertir si viene como string y el modelo espera date/datetime
                    if attr.py_type in (date,) and isinstance(value, str):
                        processed_data[field_name] = datetime.strptime(value, "%Y-%m-%d").date()
                        continue

                    elif attr.py_type in (datetime,) and isinstance(value, str):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                            try:
                                processed_data[field_name] = datetime.strptime(value, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            processed_data[field_name] = value
                        continue
            
            # Para todos los demás campos, usar el valor tal como está
            processed_data[field_name] = value
        
        return processed_data