# task_manager.py
from datetime import datetime, date
import datetime
import json
import threading
from typing import Optional, Dict, Any, Callable

from pony.orm import db_session, commit, rollback
from tarea import Tarea, Metodo
from cola2 import Cola2
import logging

logger = logging.getLogger("app_logger.manager")  # o logging.getLogger("cola_logger").getChild("manager")
# NO agregues handlers aquí. Hereda el RotatingFileHandler de cola_logger y escribe en app.log

class WorkerManager:
    def __init__(self, cola2: Cola2, dborm, num_workers: int = 1, bzpop_timeout: int = 1):
        
        self._lock = threading.RLock()
        self._next_id = num_workers + 1
        self.cola = cola2
        self.dborm = dborm
        self.bzpop_timeout = bzpop_timeout
        
        self.workers = [
            TaskWorker(cola2=cola2, dborm=dborm, name=f"Worker-{i+1}", bzpop_timeout=bzpop_timeout)
            for i in range(num_workers)
        ]
        logger.info(f"Creados {num_workers} workers con timeout {bzpop_timeout}s")

    def start(self):
        for w in self.workers:
            print(f"[Iniciando worker para cola='{w.cola.nombre}'")
            w.start()
        logger.info(f"Iniciados {len(self.workers)} workers")
    def count(self) -> int:
        # Si quieres contar solo vivos:
        with self._lock:
            return sum(1 for w in self.workers if w.is_alive())

    def pause_all(self):
        for w in self.workers:
            w.pause()
        logger.info("Todos los workers pausados")

    def resume_all(self):
        for w in self.workers:
            w.resume()
        logger.info("Todos los workers reanudados")

    def stop_all(self):
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.join(timeout=2.0)
        logger.info("Workers detenidos")
    
    def add_workers(self, n: int) -> dict:
        created = []
        with self._lock:
            for _ in range(max(0, n)):
                name = f"Worker-{self._next_id}"
                self._next_id += 1
                w = TaskWorker(cola2=self.cola, dborm=self.dborm, name=name, bzpop_timeout=self.bzpop_timeout)
                w.start()
                self.workers.append(w)
                created.append(w.name)
        return {"ok": True, "added": len(created), "names": created}

    # === NUEVO: remover n workers ===
    def remove_workers(self, n: int) -> dict:
        stopped = []
        with self._lock:
            # tomar vivos desde el final para “apagar” los más nuevos primero
            candidates = [w for w in reversed(self.workers) if w.is_alive()]
            to_stop = candidates[:max(0, n)]
            for w in to_stop:
                w.stop()
        # fuera del lock: join
        for w in to_stop:
            w.join(timeout=2.0)
        # limpiar la lista
        with self._lock:
            remaining = []
            for w in self.workers:
                if w in to_stop:
                    stopped.append(w.name)
                else:
                    remaining.append(w)
            self.workers = remaining
        return {"ok": True, "removed": len(stopped), "names": stopped}
    

# ------Worker -----------------------------------

class TaskWorker(threading.Thread):
    def __init__(
        self,
        cola2: Cola2,
        dborm,                      
        name: Optional[str] = None,
        bzpop_timeout: int = 1   
    ):
        super().__init__(daemon=True, name=name or "TaskWorker")
        self.cola = cola2
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
        logger.info(f"{self.name} pausando")

    def resume(self):
        self._run_event.set()
        logger.info(f"{self.name} reanudado...")

    def stop(self):
        self._stop_event.set()
        self._run_event.set()
        logger.info(f"{self.name} deteniendo...")
        
        

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
        
        if entity_name == "InscripcionMateriaList":
            return self._procesar_inscripcion_materia3(dto_data)
    
        
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



    @db_session
    def _procesar_inscripcion_materia2(self, dto_data: dict):
        print("Entrando por proceso de inscripción de lista de materias.")
        print(dto_data)
        # 1. Obtener las entidades de la base de datos
        Inscripcion = self.dborm.db.Inscripcion
        Estudiante = self.dborm.db.Estudiante
        Periodo = self.dborm.db.Periodo
        InscripcionMateria = self.dborm.db.InscripcionMateria
        GrupoMateria = self.dborm.db.GrupoMateria

        # 2. Validaciones iniciales de los datos principales
        estudiante = Estudiante.get(registro=dto_data.get("estudiante_registro"))
        if not estudiante:
            raise ValueError("Estudiante no encontrado")

        periodo = Periodo.get(id=dto_data.get("periodo_id"))
        if not periodo:
            raise ValueError("Periodo no encontrado")

        grupos_ids = dto_data.get("grupos_ids", [])
        if not isinstance(grupos_ids, list) or not grupos_ids:
            raise ValueError("La lista 'grupos_ids' es requerida y no puede estar vacía")

        # 3. Validar todos los grupos y sus cupos ANTES de crear cualquier registro
        grupos_a_inscribir = []
        for grupo_id in grupos_ids:
            grupo = GrupoMateria.get(id=grupo_id)
            if not grupo:
                raise ValueError(f"El grupo con ID {grupo_id} no fue encontrado")
            if grupo.cupo is None or grupo.cupo <= 0:
                raise ValueError(f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})")
            grupos_a_inscribir.append(grupo)

        # 4. Crear la inscripción principal
        nueva_inscripcion = Inscripcion(
            fecha=datetime.date.today(),
            estudiante=estudiante,
            periodo=periodo
        )

        # 5. Crear las inscripciones a materias y descontar los cupos
        materias_inscritas_info = []
        for grupo in grupos_a_inscribir:
            InscripcionMateria(inscripcion=nueva_inscripcion, grupo=grupo)
            grupo.cupo -= 1  # Descontar el cupo

            materias_inscritas_info.append({
                "id_grupo": grupo.id,
                "nombre_grupo": grupo.nombre,
                "cupo_restante": grupo.cupo
            })

        # 6. Confirmar la transacción (opcional si @db_session lo maneja, pero explícito es más claro)
        commit()

        # 7. Devolver un diccionario con el resultado detallado
        return {
            "msg": "Inscripción completada exitosamente.",
            "inscripcion": {
                "id": nueva_inscripcion.id,
                "fecha": str(nueva_inscripcion.fecha),
                "estudiante": {"id": estudiante.id, "nombre": estudiante.nombre},
                "periodo": {"id": periodo.id, "numero": periodo.numero}
            },
            "materias_inscritas": materias_inscritas_info
        }
        
    @db_session
    def _procesar_inscripcion_materia3(self, dto_data: dict):
        logger.info("Iniciando proceso de inscripción de materias.")
        logger.debug(f"Datos recibidos: {dto_data}")

        try:
            # 1. Obtener las entidades de la base de datos
            Inscripcion = self.dborm.db.Inscripcion
            Estudiante = self.dborm.db.Estudiante
            Periodo = self.dborm.db.Periodo
            InscripcionMateria = self.dborm.db.InscripcionMateria
            GrupoMateria = self.dborm.db.GrupoMateria

            # 2. Validaciones iniciales
            estudiante_registro = dto_data.get("estudiante_registro")
            estudiante = Estudiante.get(registro=estudiante_registro)
            if not estudiante:
                raise ValueError(f"Estudiante no encontrado con registro: {estudiante_registro}")
            logger.info(f"Estudiante validado: {estudiante.nombre} (ID: {estudiante.id}) (Registro : {estudiante_registro})")

            periodo_id = dto_data.get("periodo_id")
            periodo = Periodo.get(id=periodo_id)
            if not periodo:
                raise ValueError(f"Período no encontrado con ID: {periodo_id}")
            logger.info(f"Período validado: ID {periodo.id}")

            grupos_ids = dto_data.get("grupos_ids", [])
            if not isinstance(grupos_ids, list) or not grupos_ids:
                raise ValueError("La lista 'grupos_ids' es requerida y no puede estar vacía")
            logger.info(f"Procesando inscripción para {len(grupos_ids)} grupos: {grupos_ids}")

            # 3. Validar todos los grupos y sus cupos ANTES de crear cualquier registro
            grupos_a_inscribir = []
            logger.info("Validando grupos y cupos...")
            for grupo_id in grupos_ids:
                grupo = GrupoMateria.get(id=grupo_id)
                if not grupo:
                    raise ValueError(f"El grupo con ID {grupo_id} no fue encontrado")
                if grupo.cupo is None or grupo.cupo <= 0:
                    raise ValueError(f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})")
                grupos_a_inscribir.append(grupo)
            logger.info("Todos los grupos y cupos han sido validados correctamente.")

            # 4. Crear la inscripción principal
            logger.info(f"Creando registro de inscripción para '{estudiante.nombre}'.")
            nueva_inscripcion = Inscripcion(
                fecha=date.today(),
                estudiante=estudiante,
                periodo=periodo
            )

            # 5. Crear las inscripciones a materias y descontar los cupos
            logger.info("Asociando materias a la inscripción y actualizando cupos...")
            materias_inscritas_info = []
            for grupo in grupos_a_inscribir:
                InscripcionMateria(inscripcion=nueva_inscripcion, grupo=grupo)
                logger.debug(f"Descontando cupo para grupo '{grupo.nombre}'. Cupo anterior: {grupo.cupo}")
                grupo.cupo -= 1
                materias_inscritas_info.append({
                    "id_grupo": grupo.id,
                    "nombre_grupo": grupo.nombre,
                    "cupo_restante": grupo.cupo
                })

            # 6. Confirmar la transacción
            commit()
            logger.info(f"Transacción confirmada. Inscripción ID: {nueva_inscripcion.id} con {len(materias_inscritas_info)} materias.")

            # 7. Devolver el resultado de éxito
            return {
                "msg": "Inscripción completada exitosamente.",
                "inscripcion": {
                    "id": nueva_inscripcion.id,
                    "fecha": str(nueva_inscripcion.fecha),
                },
                "materias_inscritas": materias_inscritas_info
            }
        except ValueError as e:
            logger.error(f"Error de validación durante la inscripción: {e}")
            rollback() # Deshacer cualquier cambio en la base de datos
            return {"error": str(e)}
        except Exception as e:
            logger.critical(f"Error inesperado durante el proceso de inscripción: {e}", exc_info=True)
            rollback() # Deshacer cualquier cambio
            return {"error": "Ocurrió un error inesperado en el servidor."}
    
    
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