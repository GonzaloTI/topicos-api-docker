# task_manager.py
from datetime import datetime, date
import datetime
import json
import threading
from typing import Optional, Dict, Any, Callable

from pony.orm import db_session, commit, rollback
from app_except import AppError
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


    
    def _validar_grupos_y_cupos(self, grupos_ids: list):
        """
        Valida que los grupos existan y tengan cupos disponibles.
        Retorna la lista de objetos 'GrupoMateria' si todo es correcto.
        Lanza un ValueError si algo falla.
        """
        GrupoMateria = self.dborm.db.GrupoMateria
        grupos_a_inscribir = []
        
        logger.info("Validando grupos y cupos...")
        
        if not isinstance(grupos_ids, list) or not grupos_ids:
            raise ValueError("La lista 'grupos_ids' es requerida y no puede estar vacía")
            # raise AppError(
            #         "La lista 'grupos_ids' es requerida y no puede estar vacía",
            #         error_code="Error not found",
            #         status_code=408
            #         )
        for grupo_id in grupos_ids:
            # ESTA LÍNEA (GrupoMateria.get) ES LA QUE "MOCKEAREMOS" EN LA PRUEBA
            grupo = GrupoMateria.get(id=grupo_id)
            
            if not grupo:
                raise ValueError(f"El grupo con ID {grupo_id} no fue encontrado")
                # raise AppError(
                # f"El grupo con ID {grupo_id} no fue encontrado",
                # error_code="Error not found",
                # status_code=404
                # )
            if grupo.cupo is None or grupo.cupo <= 0:
                raise ValueError(f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})")
                # raise AppError(
                # f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})",
                # error_code="Error not cupos disponibles",
                # status_code=440
                # )
            
            grupos_a_inscribir.append(grupo)
            
        logger.info("Todos los grupos y cupos han sido validados correctamente.")
        return grupos_a_inscribir
    
    def _validar_choque_horarios(self, grupos_ids: list) -> bool:
        """
        Valida choques de horario EXCLUSIVAMENTE entre los grupos indicados.
        - Lanza AppError con error_code='CHOQUE_DE_HORARIO' si hay conflicto.
        - Retorna True si no hay choques.
        """
        GrupoMateria = self.dborm.db.GrupoMateria

        logger.info("Validando choques de horarios (solo entre grupos seleccionados)...")

        if not isinstance(grupos_ids, list) or not grupos_ids:
            # raise AppError(
            #     "La lista 'grupos_ids' es requerida y no puede estar vacía",
            #     error_code="Error not found",
            #     status_code=408
            # )
            raise ValueError(f"La lista 'grupos_ids' es requerida y no puede estar vacía")

        # Cargar grupos existentes
        grupos = []
        for gid in grupos_ids:
            g = GrupoMateria.get(id=gid)
            if not g:
                # raise AppError(
                #     f"El grupo con ID {gid} no fue encontrado",
                #     error_code="Error not found",
                #     status_code=404
                # )
                raise ValueError(f"El grupo con ID {gid} no fue encontrado")
            grupos.append(g)

        # Helpers
        def _norm_dia(d: str) -> str:
            return (d or "").strip().casefold()

        def _se_solapan(hini1, hfin1, hini2, hfin2) -> bool:
            # contiguos NO chocan
            return (hini1 < hfin2) and (hfin1 > hini2)

        # Construir slots
        slots = []
        for g in grupos:
            for h in g.horarios:
                slots.append((
                    g,
                    _norm_dia(h.dia),
                    h.hora_inicio,
                    h.hora_fin,
                    h.dia,  # día original para mostrar
                    f"{g.nombre or f'Grupo {g.grupo}'} — {g.materia.nombre}",
                    h.hora_inicio.strftime('%H:%M'),
                    h.hora_fin.strftime('%H:%M'),
                ))

        # Agrupar por día
        por_dia = {}
        for g, d_norm, ini, fin, d_show, label, sinitxt, sfinxt in slots:
            por_dia.setdefault(d_norm, []).append((g, ini, fin, d_show, label, sinitxt, sfinxt))

        conflictos_legibles = []  # líneas para mostrar
        # (Si quisieras, aquí podrías construir también una lista de dicts estructurados)

        # Comparar pares en el mismo día
        for d_norm, items in por_dia.items():
            n = len(items)
            for i in range(n):
                g_i, ini_i, fin_i, d_show_i, lbl_i, s_ini_i, s_fin_i = items[i]
                for j in range(i + 1, n):
                    g_j, ini_j, fin_j, d_show_j, lbl_j, s_ini_j, s_fin_j = items[j]

                    # Evitar comparar el mismo grupo consigo mismo
                    if g_i.id == g_j.id:
                        continue

                    if _se_solapan(ini_i, fin_i, ini_j, fin_j):
                        # Mismo día visual (pueden venir iguales)
                        dia_mostrar = d_show_i or d_show_j
                        conflictos_legibles.append(
                            f"- {dia_mostrar}: {lbl_i} [{s_ini_i}–{s_fin_i}]  ↔  {lbl_j} [{s_ini_j}–{s_fin_j}]"
                        )

        if conflictos_legibles:
            detalle = "\n".join(conflictos_legibles)
            # raise AppError(
            #     "[CHOQUE_DE_HORARIO] Se detectaron choques de horario entre los grupos seleccionados.\n" + detalle,
            #     error_code="CHOQUE_DE_HORARIO",
            #     status_code=441
            #)
            raise ValueError(f"[CHOQUE_DE_HORARIO] Se detectaron choques de horario entre los grupos seleccionados.\n" + detalle)

        logger.info("No se encontraron choques de horario entre los grupos seleccionados.")
        return True
    
    def _validar_prerequisito_vencido(self, estudiante, grupos_ids: list):
        """
        Verifica que el estudiante haya vencido (aprobado) todos los prerequisitos
        de las materias que intenta inscribir.
        - Recibe los IDs de los grupos, no los objetos.
        - Lanza ValueError si falta aprobar algún prerequisito.
        """
        GrupoMateria = self.dborm.db.GrupoMateria
        Prerequisito = self.dborm.db.Prerequisito
        InscripcionMateria = self.dborm.db.InscripcionMateria
        Nota = self.dborm.db.Nota

        logger.info("Validando prerequisitos vencidos...")

        if not isinstance(grupos_ids, list) or not grupos_ids:
            raise ValueError("La lista 'grupos_ids' es requerida y no puede estar vacía")

        for grupo_id in grupos_ids:
            grupo = GrupoMateria.get(id=grupo_id)
            if not grupo:
                raise ValueError(f"El grupo con ID {grupo_id} no fue encontrado")

            materia_actual = grupo.materia
            prereqs = Prerequisito.select(lambda p: p.materia == materia_actual)[:]

            if not prereqs:
                logger.debug(f"La materia '{materia_actual.nombre}' no tiene prerequisitos.")
                continue

            for prereq in prereqs:
                materia_requerida = prereq.materia_requisito
                logger.debug(f"Validando prerequisito '{materia_requerida.nombre}' para '{materia_actual.nombre}'")

                # Buscar si el estudiante ya cursó esa materia
                inscripciones_previas = InscripcionMateria.select(
                    lambda im: im.inscripcion.estudiante == estudiante and im.grupo.materia == materia_requerida
                )[:]

                if not inscripciones_previas:
                    raise ValueError(
                        f"El estudiante no tiene registrada la materia prerequisito '{materia_requerida.nombre}' "
                        f"requerida para inscribir '{materia_actual.nombre}'."
                    )

                # Validar si alguna inscripción de esa materia tiene nota >= 51
                aprobo = any(
                    (nota := Nota.get(inscripcionmateria=im)) and nota.nota >= 51
                    for im in inscripciones_previas
                )

                if not aprobo:
                    raise ValueError(
                        f"No se puede inscribir '{materia_actual.nombre}' porque no se ha vencido "
                        f"el prerequisito '{materia_requerida.nombre}' (nota < 51)."
                    )

        logger.info("Todos los prerequisitos han sido validados correctamente.")
        return True
    
    def _validar_bloqueo_estudiante(self, estudiante):
        """
        Verifica si el estudiante está bloqueado.
        Lanza ValueError si el campo 'bloqueo' está en True.
        """
        if estudiante is None:
            raise ValueError("El estudiante proporcionado no existe o no fue encontrado.")

        if getattr(estudiante, "bloqueo", False):
            raise ValueError(
                f"El estudiante '{estudiante.nombre}' (CI: {estudiante.ci}) "
                f"tiene un bloqueo activo y no puede realizar inscripciones."
            )

        logger.info(f"Validación de bloqueo completada: estudiante '{estudiante.nombre}' no está bloqueado.")
        return True
    
    
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
            # grupos_a_inscribir = []
            # logger.info("Validando grupos y cupos...")
            # for grupo_id in grupos_ids:
            #     grupo = GrupoMateria.get(id=grupo_id)
            #     if not grupo:
            #         raise ValueError(f"El grupo con ID {grupo_id} no fue encontrado")
            #     if grupo.cupo is None or grupo.cupo <= 0:
            #         raise ValueError(f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})")
            #     grupos_a_inscribir.append(grupo)
            # logger.info("Todos los grupos y cupos han sido validados correctamente.")

            # 3. Validar grupos y cupos (LLAMADA A LA NUEVA FUNCIÓN)
            
            grupos_a_inscribir = self._validar_grupos_y_cupos(grupos_ids=grupos_ids)
            
            self._validar_choque_horarios(grupos_ids=grupos_ids)
            
            self._validar_prerequisito_vencido(estudiante=estudiante,grupos_ids=grupos_ids )

            self._validar_bloqueo_estudiante(estudiante=estudiante)


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