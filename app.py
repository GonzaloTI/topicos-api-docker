import json
from flask import Flask, Response, render_template, request, jsonify, url_for
from pony.orm import Database, Required, Optional, PrimaryKey, db_session, Set , commit, rollback
from pony.orm.core import TransactionIntegrityError, ObjectNotFound
import datetime
from functools import wraps
import jwt
from DTO.InscripcionMasivaDTO import InscripcionMasivaDTO
from DTO.CarreraDTO import CarreraDTO
from DTO.MateriaDTO import MateriaDTO
from DTO.PrerequisitoDTO import PrerequisitoDTO
from DTO.NivelDTO import NivelDTO
from DTO.DocenteDTO import DocenteDTO
from DTO.ModuloDTO import ModuloDTO
from DTO.HorarioDTO import HorarioDTO
from DTO.InscripcionDTO import InscripcionDTO
from DTO.GrupoMateriaDTO import GrupoMateriaDTO
from DTO.NotaDTO import NotaDTO
from DTO.InscripcionMateriaDTO import InscripcionMateriaDTO
from DTO.EstudianteDTO import EstudianteDTO
from DTO.PlanDeEstudioDTO import PlanDeEstudioDTO
from DTO.AulasDTO import AulaDTO

from cola2 import Cola2
from cola_manager import ColaManager, RedisParams
from model_orm.ponyorm import DatabaseORM
import uuid

from tarea import Tarea,Metodo,Prioridad
from task_manager import WorkerManager

from flask_cors import CORS

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, send_file
import os

from app_except import AppError
from logger_class import Logger


app = Flask(__name__)

# =========================
# Configuración de la BD
# =========================
dborm = DatabaseORM(
    user="topicos",
    password="KuWI4SHngQeWVtNNiW7xBROdWBphX6K5",
    host="dpg-d40k08mmcj7s739cj9t0-a.oregon-postgres.render.com",
    database="topicos_t4hk"
)
'''
dborm = DatabaseORM(
    user="postgres",
    password="pgadmin123",
    host="localhost",
    database="topicosflask3"
)
'''
SECRET_KEY = "mi_clave_secreta"

'''
REDIS_HOST = "localhost"     # ej: "54.210.xxx.xxx"
REDIS_PORT = 6379
REDIS_PASSWORD = "contraseniasegura2025"
'''



REDIS_HOST = "18.222.233.236"     # ej: "54.210.xxx.xxx"
REDIS_PORT = 6379
REDIS_PASSWORD = "contraseniasegura2025"


LOG_FILE = "app.log"

logger = Logger.get_logger(name="app_logger", log_file=LOG_FILE)



cola = Cola2(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_password=REDIS_PASSWORD,  # tu password
    redis_db=2,
    nombre="cola"
)

cola3 = Cola2(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_password=REDIS_PASSWORD,  # tu password
    redis_db=2,
    nombre="cola"
)

RedisP = RedisParams(host=REDIS_HOST,port=REDIS_PORT,password=REDIS_PASSWORD,db=2)

colamanager = ColaManager(RedisP,dborm=dborm ,bzpop_timeout= 1)
colamanager.create_many(1,num_workers=1)

worker_manager = WorkerManager(cola2=cola3, dborm=dborm, num_workers=1, bzpop_timeout=1)
worker_manager.start()
 


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Token faltante"}), 401
        
        # Se espera: "Bearer <token>"
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({"error": "Formato de token inválido"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado, por favor haga login nuevamente"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401

        return f(*args, **kwargs)
    return decorated

# =========================
# Rutas de la API
# =========================
@app.route("/statusall", methods=["GET"])
def obtener_respuestaall():
    resultado = cola.obtener_todas_las_tareas()
    #print(resultado)
    if resultado:
        tareas_serializadas = [tarea.to_dict() for tarea in resultado]
        return jsonify({"resultado": tareas_serializadas}), 200
    else:
        # Si no hay resultado disponible aún
        return jsonify({"error": "Cola Vacia"}), 404
@app.route("/limpiarbd", methods=["GET"])
def vaciarbd():
    resultado = cola.vaciar_bd()
    #print(resultado)
    return jsonify({"pass": "vaciandobd"}), 201

# --- en tu app Flask ---
@app.get("/cola/resumen")
def cola_resumen():
    # Pendientes del ZSET (no se consumen)
    pendientes = cola.pendientes(limit=0, mayor_a_menor=True)

    # Realizadas/estado desde el hash :status
    realizadas_objs = cola.obtener_todas_las_tareas()  # devuelve lista de Tarea
    realizadas = [t.to_dict() for t in realizadas_objs]

    return jsonify({
        "cola": cola.nombre,
        "total_pendientes": len(pendientes),
        "total_realizadas": len(realizadas),
        "pendientes": pendientes,
        "realizadas": realizadas
    }), 200
@app.route("/ui/cola", methods=["GET"])
def ui_cola():
    return render_template("cola_resumen.html", cola_nombre=cola.nombre)
# --- en tu app Flask ---
@app.route("/cola/resumen2", methods=["GET"], endpoint="cola_resumen2")
def cola_resumen2():
    print("HIT /cola/resumen2")  # <-- debe verse en consola SIEMPRE que la llamen
    pend_page  = int(request.args.get("pend_page", 1))
    pend_size  = int(request.args.get("pend_size", 500))
    real_cursor= int(request.args.get("real_cursor", 0))
    real_count = int(request.args.get("real_count", 500))
    orden_desc = request.args.get("desc", "1") in ("1", "true", "True")

    total_pendientes = cola.count_pendientes()
    total_realizadas = cola.count_realizadas()

    pendientes_page = cola.pendientes_paginado(page=pend_page, page_size=pend_size, mayor_a_menor=orden_desc)
    real_cursor_next, realizadas_chunk = cola.realizadas_scan(cursor=real_cursor, count=real_count)

    print("pend:", len(pendientes_page), "real:", len(realizadas_chunk), "cursor_next:", real_cursor_next)

    return jsonify({
        "cola": cola.nombre,
        "total_pendientes": total_pendientes,
        "total_realizadas": total_realizadas,
        "pendientes": pendientes_page,
        "pend_page": pend_page,
        "pend_size": pend_size,
        "pend_total_pages": ((total_pendientes + pend_size - 1) // pend_size) if pend_size > 0 else 1,
        "realizadas": realizadas_chunk,
        "real_cursor_next": real_cursor_next,
        "real_count": real_count
    }), 200

@app.route("/ui/colapaginate", methods=["GET"])
def ui_colapaginate():
    return render_template("cola_resumen_paginate.html", cola_nombre=cola.nombre)


# === RESUMEN POR COLA (clon 1:1 del anterior) =========================================================
@app.route("/colas/<nombre_cola>/resumen2", methods=["GET"], endpoint="cola_resumen2_por_cola")
def cola_resumen2_por_cola(nombre_cola: str):
    print(f"HIT /colas/{nombre_cola}/resumen2")  # <-- debe verse en consola SIEMPRE

    # 1) Ubicar la cola
    slot = colamanager._get_slot(nombre_cola) if hasattr(colamanager, "_get_slot") else None
    if not slot:
        return jsonify({"error": f"cola '{nombre_cola}' no existe"}), 404
    cola = slot.cola

    # 2) Misma lectura de query params
    pend_page   = int(request.args.get("pend_page", 1))
    pend_size   = int(request.args.get("pend_size", 500))
    real_cursor = int(request.args.get("real_cursor", 0))
    real_count  = int(request.args.get("real_count", 500))
    orden_desc  = request.args.get("desc", "1") in ("1", "true", "True")

    # 3) Mismos conteos y paginaciones que antes
    total_pendientes = cola.count_pendientes()
    total_realizadas = cola.count_realizadas()

    pendientes_page = cola.pendientes_paginado(
        page=pend_page, page_size=pend_size, mayor_a_menor=orden_desc
    )
    real_cursor_next, realizadas_chunk = cola.realizadas_scan(
        cursor=real_cursor, count=real_count
    )
    # --- LIGERAR RESPUESTA ---
    # Realizadas: quitar 'resultado' y marcar que se puede pedir aparte
    for t in realizadas_chunk:
        if "resultado" in t:
            t.pop("resultado", None)
            t["resultado_disponible"] = True
        else:
            t["resultado_disponible"] = False

    print("pend:", len(pendientes_page), "real:", len(realizadas_chunk), "cursor_next:", real_cursor_next)

    # 4) Misma forma de respuesta
    return jsonify({
        "cola": cola.nombre,
        "total_pendientes": total_pendientes,
        "total_realizadas": total_realizadas,
        "pendientes": pendientes_page,
        "pend_page": pend_page,
        "pend_size": pend_size,
        "pend_total_pages": ((total_pendientes + pend_size - 1) // pend_size) if pend_size > 0 else 1,
        "realizadas": realizadas_chunk,
        "real_cursor_next": real_cursor_next,
        "real_count": real_count
    }), 200

# === UI por cola seleccionada =================================================================================
@app.route("/ui/colapaginate/<nombre_cola>", methods=["GET"])
def ui_colapaginate_por_cola(nombre_cola: str):
    # Pasamos el nombre y la URL del resumen de esa cola, para que el JS no dependa de una global
    return render_template(
        "cola_resumen_paginate_multicola.html",
        cola_nombre=nombre_cola,
        resumen_url=url_for("cola_resumen2_por_cola", nombre_cola=nombre_cola)
    )
@app.post("/colas/<nombre>/workers/add/<int:n>")
def colas_add_workers(nombre, n):
    out = colamanager.add_workers_to_queue(nombre, n)
    return jsonify(out), (200 if out.get("ok") else 400)

@app.post("/colas/<nombre>/workers/remove/<int:n>")
def colas_remove_workers(nombre, n):
    out = colamanager.remove_workers_from_queue(nombre, n)
    return jsonify(out), (200 if out.get("ok") else 400)


@app.route("/status/<id_tarea>", methods=["GET"])
def obtener_respuesta(id_tarea):
    #resultado = cola.obtener_todas_las_tareas()
    resultado = cola.obtener_resultado(id_tarea)
    #print(resultado)
    if resultado:
        return jsonify({"resultado": resultado}), 200
    else:
        # Si no hay resultado disponible aún
        return jsonify({"error": "Respuesta aún no disponible"}), 404
# LISTAR colas creadas en el manager
@app.get("/colas")
# @token_required
def colas_listar():
    nombres = colamanager.list_queues()
    return jsonify({
        "total": len(nombres),
        "colas": nombres
    }), 200
@app.post("/colas")
def crear_cola_por_nombre():
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    num_workers = data.get("numero_workers", 1)
    try:
        num_workers = int(num_workers)
    except (ValueError, TypeError):
        num_workers = 1

    if not nombre:
        return jsonify({"error": "Debes enviar {'nombre': '...', 'numero_workers': N}"}), 400
    for s in colamanager._slots:
        if s.cola.nombre == nombre:
            return jsonify({"mensaje": "La cola ya existe", "cola": nombre}), 200
    cola_creada = colamanager.create_queue(nombre, num_workers=num_workers)
    return jsonify({
        "mensaje": "Cola creada",
        "cola": cola_creada.nombre,
        "workers": num_workers
    }), 201
@app.delete("/colas/<nombre>")
def eliminar_cola(nombre: str):

    res = colamanager.delete_queue(nombre)
    
    if not res.get("removed"):
        reason = res.get("reason", "unknown")
        code = 409 if reason in ("queue-busy",) else 404
        return jsonify({"error": reason, "cola": nombre}), code

    return jsonify(res), 200


@app.post("/colas/pause")
def pause_many():
    '''{"colas":["cola_1","cola_2","cola_5"]}'''
    data = request.get_json(silent=True) or {}
    colas = data.get("colas")  # lista de nombres, si falta => todas
    if isinstance(colas, list) and colas:
        afectados = sum(colamanager.pause_workers(nombre) for nombre in colas)
    else:
        afectados = colamanager.pause_workers()  # todas
    return jsonify({"ok": True, "accion": "pause", "colas_afectadas": afectados}), 200


@app.post("/colas/resume")
def resume_many():
    '''{"colas":["cola_1","cola_2","cola_5"]}'''
    data = request.get_json(silent=True) or {}
    colas = data.get("colas")
    if isinstance(colas, list) and colas:
        afectados = sum(colamanager.resume_workers(nombre) for nombre in colas)
    else:
        afectados = colamanager.resume_workers()
    return jsonify({"ok": True, "accion": "resume", "colas_afectadas": afectados}), 200


@app.post("/colas/stop")
def stop_many():
    '''{"colas":["cola_1","cola_2","cola_5"]}'''
    data = request.get_json(silent=True) or {}
    colas = data.get("colas")
    if isinstance(colas, list) and colas:
        afectados = sum(colamanager.stop_workers(nombre) for nombre in colas)
    else:
        afectados = colamanager.stop_workers()
    return jsonify({"ok": True, "accion": "stop", "colas_afectadas": afectados}), 200



@app.get("/colas/<nombre_cola>/resultados/<id_tarea>")
def obtener_resultado_por_id(nombre_cola: str, id_tarea: str):
    # buscar en la cola específica
    slot = colamanager._get_slot(nombre_cola) if hasattr(colamanager, "_get_slot") else None
    if not slot:
        return jsonify({"error": f"cola '{nombre_cola}' no existe"}), 404

    resultado = slot.cola.obtener_resultado(id_tarea)
    if resultado is not None:
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "resultado": resultado
        }), 200

    return jsonify({
        "error": "Respuesta aún no disponible",
        "cola": nombre_cola,
        "id_tarea": id_tarea
    }), 404



@app.get("/colas/<nombre_cola>/resultados_estados/<id_tarea>")
def obtener_resultado_por_id_porestados(nombre_cola: str, id_tarea: str):
    try:
        # 1) Validar cola
        slot = getattr(colamanager, "_get_slot", None)
        slot = slot(nombre_cola) if callable(slot) else None

        if not slot:
            # Cola no existe -> lo consideramos 'error' pero siempre 200
            return jsonify({
                "cola": nombre_cola,
                "id_tarea": id_tarea,
                "estado": "error",
                "resultado": None,
                "mensaje": f"cola '{nombre_cola}' no existe"
            }), 200

        # 2) Consultar resultado
        try:
            resultado = slot.cola.obtener_resultado(id_tarea)
        except Exception as e:
            # Error al obtener el resultado
            return jsonify({
                "cola": nombre_cola,
                "id_tarea": id_tarea,
                "estado": "error",
                "resultado": {"error": str(e)},
                "mensaje": "Error al obtener el resultado"
            }), 200

        # 3) Armar respuesta según el caso
        if resultado is None:
            # Aún no disponible
            return jsonify({
                "cola": nombre_cola,
                "id_tarea": id_tarea,
                "estado": "espera",
                "resultado": None,
                "mensaje": "Respuesta aún no disponible"
            }), 200

        # Si la estructura que guardas en 'resultado' ya trae un campo de error
        if isinstance(resultado, dict) and "error" in resultado:
            return jsonify({
                "cola": nombre_cola,
                "id_tarea": id_tarea,
                "estado": "error",
                "resultado": resultado,
                "mensaje": "La tarea terminó con error"
            }), 200

        # Caso normal: completado
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "estado": "completado",
            "resultado": resultado,
            "mensaje": "OK"
        }), 200

    except Exception as e:
        # Falla inesperada en la propia API
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "estado": "error",
            "resultado": {"error": str(e)},
            "mensaje": "Error inesperado en el endpoint"
        }), 200
#logg errores , 



# user 2 , web movile, los dos incriben, en fis 1 , 
# al menos 2 excepciones y ver los logs


@app.get("/colas/<nombre_cola>/resultados_estados2/<id_tarea>")
def obtener_resultado_por_id_porestados2(nombre_cola: str, id_tarea: str):
    try:
        logger.info(f"Consultando cola='{nombre_cola}', id_tarea='{id_tarea}'")

        # 1) Validar disponibilidad del manager/slot
        slot_getter = getattr(colamanager, "_get_slot", None)
        if not callable(slot_getter):
            raise AppError(
                "Administrador de colas no disponible.",
                error_code="QUEUE_MANAGER_MISSING",
                status_code=503
            )

        slot = slot_getter(nombre_cola)
        if not slot:
            raise AppError(
                f"Cola '{nombre_cola}' no existe.",
                error_code="QUEUE_NOT_FOUND",
                status_code=404
            )

        # 2) Consultar resultado (si falla, envolver como AppError)
        try:
            resultado = slot.cola.obtener_resultado(id_tarea)
            logger.info(f"Resultado obtenido para tarea '{id_tarea}':")
        except Exception as e:
            logger.error(f"Error al obtener resultado de '{id_tarea}': {e}")
            raise AppError(
                "Error al obtener el resultado de la tarea.",
                error_code="TASK_RESULT_FETCH_ERROR",
                status_code=400
            ) from e

        # 3) Armar respuesta según el caso
        if resultado is None:
            logger.info(f"Tarea '{id_tarea}' aún en proceso en cola '{nombre_cola}'.")
            return jsonify({
                "cola": nombre_cola,
                "id_tarea": id_tarea,
                "estado": "espera",
                "resultado": None,
                "mensaje": "Respuesta aún no disponible"
            }), 202

        if isinstance(resultado, dict) and "error" in resultado:
            # Si tu cola ya empaqueta el error, puedes incluirlo en 'resultado'
            logger.error(f"Tarea '{id_tarea}' terminó con error: {resultado.get('error')}")
            raise AppError(
                "La tarea terminó con error.",
                error_code= resultado,
                status_code=422
            )

        logger.info(f"Tarea '{id_tarea}' completada exitosamente en cola '{nombre_cola}'.")
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "estado": "completado",
            "resultado": resultado,
            "mensaje": "OK"
        }), 201  # GET exitoso → 200

    except AppError as e:
        logger.warning(f"AppError {e.error_code}: {e}")
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "estado": "error",
            "resultado": e.error_code,
            "error": {
                "code": e.error_code,
                "message": str(e)
            }
        }), e.status_code

    except Exception as e:
        logger.exception("Error inesperado en el endpoint")
        return jsonify({
            "cola": nombre_cola,
            "id_tarea": id_tarea,
            "estado": "error",
            "resultado": None,
            "error": {
                "code": "UNEXPECTED_ERROR",
                "message": "Error interno del servidor"
            }
        }), 500
        
#logg errores , 
# Dos except: primero lo específico (AppError), luego lo genérico (Exception). Orden importa.

# Códigos HTTP:
# 404 si la cola no existe,
# 400 si falló obtener el resultado (input/estado inválido),
# 422 si la tarea terminó con error propio,
# 202 si sigue en proceso,
# 201 si finalizó OK,
# 500 para fallos inesperados.
# from e al relanzar preserva el traceback original.


@app.get("/logs")
def ver_logs():
    """Devuelve el archivo de logs si existe"""
    logger.info("Solicitud de archivo de logs recibida")
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, mimetype="text/plain")
    else:
        return jsonify({"mensaje": "No hay logs disponibles"}), 404




@app.route("/initdb", methods=["POST"])
@db_session
def initdb():
    """Ruta inicializadora que inserta datos de ejemplo"""
    try:
        # Acceso rápido a entidades
        Carrera = dborm.db.Carrera
        PlanDeEstudio = dborm.db.PlanDeEstudio
        Nivel = dborm.db.Nivel
        Materia = dborm.db.Materia
        Prerequisito = dborm.db.Prerequisito
        Docente = dborm.db.Docente
        GrupoMateria = dborm.db.GrupoMateria
        Aula = dborm.db.Aula
        Modulo = dborm.db.Modulo
        Horario = dborm.db.Horario
        Estudiante = dborm.db.Estudiante
        Gestion = dborm.db.Gestion
        TipoPeriodo = dborm.db.TipoPeriodo
        Periodo = dborm.db.Periodo
        Inscripcion = dborm.db.Inscripcion
        InscripcionMateria = dborm.db.InscripcionMateria
        Nota = dborm.db.Nota

        # Carrera
        carrera = Carrera(
            nombre="Ingeniería Informatica",
            codigo="187-003",
            otros="Carrera orientada a software y sistemas"
        )

        # Plan de estudio
        plan = PlanDeEstudio(
            nombre="Plan 2025",
            codigo="PLN-2025",
            fecha=datetime.date(2025, 1, 1),
            estado="Vigente",
            carrera=carrera
        )

        # Niveles
        niveles = [Nivel(nivel=i) for i in range(1, 6)]

        # Materias
        m1 = Materia(sigla="INF-101", nombre="Introducción a la Programación", creditos=5, plan=plan, nivel=niveles[0])
        m2 = Materia(sigla="MAT-102", nombre="Matemáticas I", creditos=6, plan=plan, nivel=niveles[0])
        m3 = Materia(sigla="INF-201", nombre="Estructuras de Datos", creditos=5, plan=plan, nivel=niveles[1])
        m4 = Materia(sigla="INF-301", nombre="Bases de Datos", creditos=5, plan=plan, nivel=niveles[2])
        m5 = Materia(sigla="INF-302", nombre="Sistemas Operativos", creditos=5, plan=plan, nivel=niveles[2])

        # Materias prerequisito
        Prerequisito(materia=m4, materia_requisito=m5)  # BD requiere SO

        # Docentes
        d1 = Docente(registro="12345678", ci="1234567", nombre="Juan Pérez", telefono="76543210", otros="Docente de programación")
        d2 = Docente(registro="123456789", ci="7654321", nombre="María Gómez", telefono="71234567", otros="Docente de sistemas")


        # Gestión
        gestion = Gestion(anio=2025)

        # TipoPeriodo
        tp = TipoPeriodo(nombre="Semestral")

        # Periodo
        periodo = Periodo(
            numero="1",
            descripcion="Primer semestre 2025",
            gestion=gestion,
            tipoperiodo=tp
        )

        # Grupos de materias
        g1 = GrupoMateria(grupo="A", nombre="Grupo A - Prog", estado="Activo", materia=m1, docente=d1,periodo=periodo,cupo=40)
        g2 = GrupoMateria(grupo="A", nombre="Grupo A - Mate", estado="Activo", materia=m2, docente=d1,periodo=periodo,cupo=40)
        g3 = GrupoMateria(grupo="A", nombre="Grupo A - Estructuras", estado="Activo", materia=m3, docente=d2,periodo=periodo,cupo=40)
        g4 = GrupoMateria(grupo="A", nombre="Grupo A - BD", estado="Activo", materia=m4, docente=d2,periodo=periodo,cupo=40)
        g5 = GrupoMateria(grupo="A", nombre="Grupo A - SO", estado="Activo", materia=m5, docente=d2,periodo=periodo,cupo=40)

        
        m1 = Modulo(numero="220", nombre="Edificio Principal")
        m2 = Modulo(numero="320", nombre="Edificio tecnologia")

        # ========================
        # Aulas (dentro de los módulos)
        # ========================
        a1 = Aula(numero="101", nombre="Laboratorio 1", modulo=m1)
        a2 = Aula(numero="102", nombre="Aula Magna", modulo=m1)
        a3 = Aula(numero="201", nombre="Sala de Conferencias", modulo=m2)
        
        # Horarios
        Horario(dia="Lunes", hora_inicio=datetime.time(8,0), hora_fin=datetime.time(10,0), grupo=g1, aula=a1)
        Horario(dia="Martes", hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g2, aula=a2)
        Horario(dia="Miércoles", hora_inicio=datetime.time(8,0), hora_fin=datetime.time(10,0), grupo=g3, aula=a1)
        Horario(dia="Jueves", hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g4, aula=a2)
        Horario(dia="Viernes", hora_inicio=datetime.time(8,0), hora_fin=datetime.time(10,0), grupo=g5, aula=a1)

        # Estudiante
        est1 = Estudiante(
            registro="12345678",
            ci="9876543",
            nombre="Carlos Ramírez",
            telefono="78965412",
            correo="carlos@correo.com",
            otros="Estudiante regular"
        )

       
        # Inscripción
        insc = Inscripcion(
            fecha=datetime.date(2025, 2, 1),
            estudiante=est1,
            periodo=periodo
        )

        # Inscripciones a materias (4 de 5)
        im1 = InscripcionMateria(inscripcion=insc, grupo=g1)
        im2 = InscripcionMateria(inscripcion=insc, grupo=g2)
        im3 = InscripcionMateria(inscripcion=insc, grupo=g3)
        im4 = InscripcionMateria(inscripcion=insc, grupo=g4)

        # Notas
        Nota(nota=85.5, inscripcionmateria=im1)
        Nota(nota=72.0, inscripcionmateria=im2)
        Nota(nota=90.0, inscripcionmateria=im3)
        Nota(nota=68.5, inscripcionmateria=im4)
        
        commit()
        return jsonify({"msg": "Base de datos inicializada con éxito"}), 201
    
    except TransactionIntegrityError as e:
        rollback()
        return jsonify({"error": "Error de integridad en la BD (posible duplicado de claves únicas)", "detalle": str(e)}), 400
    except Exception as e:
        rollback()
        return jsonify({"error": "Error inesperado al inicializar la BD", "detalle": str(e)}), 500

# Rutas Login
# =========================
@app.route("/Seeders", methods=["POST"])
@db_session
def Seeders():
    """Ruta inicializadora que inserta datos de ejemplo"""
    try:
        # Acceso rápido a entidades
        Carrera = dborm.db.Carrera
        PlanDeEstudio = dborm.db.PlanDeEstudio
        Nivel = dborm.db.Nivel
        Materia = dborm.db.Materia
        Prerequisito = dborm.db.Prerequisito
        Docente =dborm.db.Docente
        Periodo=dborm.db.Periodo
        GrupoMateria=dborm.db.GrupoMateria
        Horario=dborm.db.Horario
        Aula=dborm.db.Aula
        Modulo=dborm.db.Modulo
        

        # Carrera
        carrera = Carrera(
            nombre="Ingeniería en Sistemas",
            codigo="187-3",
            otros="Carrera orientada a software y sistemas"
        )

        # Plan de estudio
        plan = PlanDeEstudio(
            nombre="Plan ing sistemas 2025",
            codigo="PLN-300",
            fecha=datetime.date(2025, 1, 1),
            estado="Vigente",
            carrera=carrera
        )

        # Niveles/Semestres
        niveles = [Nivel(nivel=i) for i in range(1, 10)]  # Semestre 1 a 9

        # Materias (siglas basadas en la imagen)
        materias = [
            Materia(sigla="MAT101", nombre="Cálculo I", creditos=5, plan=plan, nivel=niveles[0]),
            Materia(sigla="INF119", nombre="Estructuras Discretas", creditos=5, plan=plan, nivel=niveles[0]),
            Materia(sigla="INF110", nombre="Introducción a la Informática", creditos=5, plan=plan, nivel=niveles[0]),
            Materia(sigla="FIS100", nombre="Física I", creditos=4, plan=plan, nivel=niveles[0]),
            Materia(sigla="LIN100", nombre="Inglés Técnico I", creditos=3, plan=plan, nivel=niveles[0]),
            #4
            Materia(sigla="MAT102", nombre="Cálculo II", creditos=5, plan=plan, nivel=niveles[1]),
            Materia(sigla="MAT103", nombre="Álgebra Lineal", creditos=5, plan=plan, nivel=niveles[1]),
            Materia(sigla="INF120", nombre="Programación I", creditos=5, plan=plan, nivel=niveles[1]),
            Materia(sigla="FIS102", nombre="Física II", creditos=4, plan=plan, nivel=niveles[1]),
            Materia(sigla="LIN101", nombre="Inglés Técnico II", creditos=3, plan=plan, nivel=niveles[1]),

        ]

        # Prerrequisitos (ejemplo)
        Prerequisito(materia=materias[5], materia_requisito=materias[0])  # MAT102 requiere MAT101
        Prerequisito(materia=materias[6], materia_requisito=materias[1])  # MAT103 requiere INF119
        Prerequisito(materia=materias[7], materia_requisito=materias[2])  # INF120 requiere INF110
        Prerequisito(materia=materias[8], materia_requisito=materias[3])  # FIS102 requiere FIS100
        Prerequisito(materia=materias[9], materia_requisito=materias[4])  # LIN101 requiere LIN100
        
        
        # =========================
        # SEMESTRE 3  (nivel = 3)
        # =========================
        m_mat207 = Materia(sigla="MAT207", nombre="Ecuaciones Diferenciales",       creditos=5, plan=plan, nivel=niveles[2])
        m_inf210 = Materia(sigla="INF210", nombre="Programación II",                creditos=5, plan=plan, nivel=niveles[2])
        m_inf211 = Materia(sigla="INF211", nombre="Arquitectura de Computadoras",   creditos=5, plan=plan, nivel=niveles[2])
        m_fis200 = Materia(sigla="FIS200", nombre="Física III",                     creditos=4, plan=plan, nivel=niveles[2])
        m_adm100 = Materia(sigla="ADM100", nombre="Administración",                 creditos=3, plan=plan, nivel=niveles[2])

        materias += [m_mat207, m_inf210, m_inf211, m_fis200, m_adm100]

        # =========================
        # SEMESTRE 4  (nivel = 4)
        # =========================
        m_mat202 = Materia(sigla="MAT202", nombre="Probabilidad y Estadística I",   creditos=4, plan=plan, nivel=niveles[3])
        m_mat205 = Materia(sigla="MAT205", nombre="Métodos Numéricos",              creditos=4, plan=plan, nivel=niveles[3])
        m_inf220 = Materia(sigla="INF220", nombre="Estructura de Datos I",          creditos=5, plan=plan, nivel=niveles[3])
        m_inf221 = Materia(sigla="INF221", nombre="Programación Ensamblador",       creditos=5, plan=plan, nivel=niveles[3])
        m_adm200 = Materia(sigla="ADM200", nombre="Contabilidad",                   creditos=3, plan=plan, nivel=niveles[3])

        materias += [m_mat202, m_mat205, m_inf220, m_inf221, m_adm200]

        # =========================
        # Helper por sigla (evita depender de índices)
        # =========================
        def _M(sigla: str):
            for m in materias:
                if m.sigla == sigla:
                    return m
            raise ValueError(f"Materia con sigla {sigla} no encontrada; revisa el orden de creación.")

        # =========================
        # PRERREQUISITOS — Semestre 3 (según el diagrama)
        # =========================
        # MAT207 (Ecuaciones Diferenciales) ← MAT102 (Cálculo II)
        Prerequisito(materia=_M("MAT207"), materia_requisito=_M("MAT102"))

        # INF210 (Programación II) ← INF120 (Programación I)
        Prerequisito(materia=_M("INF210"), materia_requisito=_M("INF120"))
        Prerequisito(materia=_M("INF210"), materia_requisito=_M("MAT103"))

        # INF211 (Arquitectura de Computadoras) ← INF120 (Programación I)
        Prerequisito(materia=_M("INF211"), materia_requisito=_M("INF120"))

        # FIS200 (Física III) ← FIS102 (Física II)
        Prerequisito(materia=_M("FIS200"), materia_requisito=_M("FIS102"))

        # ADM100 (Administración) — sin prerrequisito explícito en el plan (queda libre)

        # =========================
        # PRERREQUISITOS — Semestre 4 (según el diagrama)
        # =========================
        # MAT202 (Prob. y Estadística I) ← MAT102 (Cálculo II)
        Prerequisito(materia=_M("MAT202"), materia_requisito=_M("MAT102"))

        # MAT205 (Métodos Numéricos) ← MAT102 (Cálculo II) y MAT103 (Álgebra Lineal)
        Prerequisito(materia=_M("MAT205"), materia_requisito=_M("MAT102"))
        Prerequisito(materia=_M("MAT205"), materia_requisito=_M("MAT103"))

        # INF220 (Estructura de Datos I) ← INF210 (Programación II)
        Prerequisito(materia=_M("INF220"), materia_requisito=_M("INF210"))

        # INF221 (Programación Ensamblador) ← INF211 (Arquitectura de Computadoras)
        Prerequisito(materia=_M("INF221"), materia_requisito=_M("INF211"))

        # ADM200 (Contabilidad) ← ADM100 (Administración)
        Prerequisito(materia=_M("ADM200"), materia_requisito=_M("ADM100"))

                
        
        
         # ===== IDs manuales  =====
        d1 = Docente.get(id=1)
        d2 = Docente.get(id=2)
        
        
        p1 = Periodo.get(id=1)
        if not d1 or not p1:
            rollback()
            return jsonify({"error": "Docente id=1 o Periodo id=1 no encontrado"}), 404

        # ===== Infraestructura (si no tienes aulas previas, crea estas) =====
        mod1 = Modulo(numero="220", nombre="Edificio Principal")
        mod2 = Modulo(numero="320", nombre="Edificio Tecnología")

        a1 = Aula(numero="101", nombre="Laboratorio 1",  modulo=mod1)
        a2 = Aula(numero="102", nombre="Aula Magna",     modulo=mod1)
        a3 = Aula(numero="201", nombre="Sala de Conf.",  modulo=mod2)

        # ===== Grupos (1 por materia) — SIN bucles =====
        cupo = 40

        # MAT101
        g_mat101 = GrupoMateria(grupo="SA", nombre=f"Grupo SA - {materias[0].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[0], docente=d1, periodo=p1)
        Horario(dia="Lunes",   hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_mat101, aula=a1)
        Horario(dia="Jueves",  hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g_mat101, aula=a1)

        # INF119
        g_inf119 = GrupoMateria(grupo="TV", nombre=f"Grupo TV - {materias[1].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[1], docente=d1, periodo=p1)
        Horario(dia="Martes",  hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_inf119, aula=a2)
        Horario(dia="Viernes", hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g_inf119, aula=a2)

        # INF110
        g_inf110 = GrupoMateria(grupo="TS", nombre=f"Grupo TS - {materias[2].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[2], docente=d1, periodo=p1)
        Horario(dia="Miércoles", hora_inicio=datetime.time(15,0), hora_fin=datetime.time(17,0), grupo=g_inf110, aula=a1)
        Horario(dia="Viernes",   hora_inicio=datetime.time(15,0), hora_fin=datetime.time(17,0), grupo=g_inf110, aula=a1)

        # FIS100
        g_fis100 = GrupoMateria(grupo="SX", nombre=f"Grupo SX - {materias[3].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[3], docente=d1, periodo=p1)
        Horario(dia="Lunes",   hora_inicio=datetime.time(14,0), hora_fin=datetime.time(16,0), grupo=g_fis100, aula=a2)
        Horario(dia="Jueves",  hora_inicio=datetime.time(16,0), hora_fin=datetime.time(18,0), grupo=g_fis100, aula=a2)

        # LIN100
        g_lin100 = GrupoMateria(grupo="SA", nombre=f"Grupo SA - {materias[4].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[4], docente=d1, periodo=p1)
        Horario(dia="Martes",  hora_inicio=datetime.time(14,0), hora_fin=datetime.time(16,0), grupo=g_lin100, aula=a3)
        Horario(dia="Viernes", hora_inicio=datetime.time(16,0), hora_fin=datetime.time(18,0), grupo=g_lin100, aula=a3)

        # MAT102
        g_mat102 = GrupoMateria(grupo="SB", nombre=f"Grupo SB - {materias[5].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[5], docente=d1, periodo=p1)
        Horario(dia="Lunes",     hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g_mat102, aula=a1)
        Horario(dia="Miércoles", hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g_mat102, aula=a1)

        # MAT103
        g_mat103 = GrupoMateria(grupo="SB", nombre=f"Grupo SB - {materias[6].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[6], docente=d2, periodo=p1)
        Horario(dia="Martes",  hora_inicio=datetime.time(10,0), hora_fin=datetime.time(12,0), grupo=g_mat103, aula=a2)
        Horario(dia="Jueves",  hora_inicio=datetime.time(14,0), hora_fin=datetime.time(16,0), grupo=g_mat103, aula=a2)

        # INF120
        g_inf120 = GrupoMateria(grupo="SX", nombre=f"Grupo SX - {materias[7].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[7], docente=d2, periodo=p1)
        Horario(dia="Miércoles", hora_inicio=datetime.time(14,0), hora_fin=datetime.time(16,0), grupo=g_inf120, aula=a1)
        Horario(dia="Viernes",   hora_inicio=datetime.time(14,0), hora_fin=datetime.time(16,0), grupo=g_inf120, aula=a1)

        # FIS102
        g_fis102 = GrupoMateria(grupo="SC", nombre=f"Grupo SC - {materias[8].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[8], docente=d2, periodo=p1)
        Horario(dia="Lunes",   hora_inicio=datetime.time(16,0), hora_fin=datetime.time(18,0), grupo=g_fis102, aula=a2)
        Horario(dia="Jueves",  hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_fis102, aula=a2)

        # LIN101
        g_lin101 = GrupoMateria(grupo="SA", nombre=f"Grupo SA - {materias[9].nombre}", estado="Activo",
                                cupo=cupo, materia=materias[9], docente=d2, periodo=p1)
        Horario(dia="Martes",  hora_inicio=datetime.time(16,0), hora_fin=datetime.time(18,0), grupo=g_lin101, aula=a3)
        Horario(dia="Viernes", hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_lin101, aula=a3)
        
              
        # GRUPOS — SEMESTRE 3
        # =========================

        # MAT207 — Ecuaciones Diferenciales
        g_mat207 = GrupoMateria(
            grupo="SD",
            nombre=f"Grupo SD - {m_mat207.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_mat207,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Lunes",    hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat207, aula=a1)
        Horario(dia="Jueves",   hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat207, aula=a1)

        # INF210 — Programación II
        g_inf210 = GrupoMateria(
            grupo="SD",
            nombre=f"Grupo SD - {m_inf210.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_inf210,
            docente=d2,
            periodo=p1
        )
        Horario(dia="Miércoles", hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_inf210, aula=a2)
        Horario(dia="Viernes",   hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_inf210, aula=a2)

        # INF211 — Arquitectura de Computadoras
        g_inf211 = GrupoMateria(
            grupo="SD",
            nombre=f"Grupo SD - {m_inf211.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_inf211,
            docente=d2,
            periodo=p1
        )
        Horario(dia="Martes",    hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_inf211, aula=a3)
        Horario(dia="Miércoles", hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_inf211, aula=a3)

        # FIS200 — Física III
        g_fis200 = GrupoMateria(
            grupo="SD",
            nombre=f"Grupo SD - {m_fis200.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_fis200,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Lunes",   hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_fis200, aula=a2)
        Horario(dia="Jueves",  hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_fis200, aula=a2)

        # ADM100 — Administración
        g_adm100 = GrupoMateria(
            grupo="SD",
            nombre=f"Grupo SD - {m_adm100.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_adm100,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Martes",  hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_adm100, aula=a1)
        Horario(dia="Viernes", hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_adm100, aula=a1)

        # =========================
        # GRUPOS — SEMESTRE 4
        # =========================

        # MAT202 — Probabilidad y Estadística I
        g_mat202 = GrupoMateria(
            grupo="SE",
            nombre=f"Grupo SE - {m_mat202.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_mat202,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Martes",    hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat202, aula=a1)
        Horario(dia="Jueves",    hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat202, aula=a1)

        # MAT205 — Métodos Numéricos
        g_mat205 = GrupoMateria(
            grupo="SE",
            nombre=f"Grupo SE - {m_mat205.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_mat205,
            docente=d2,
            periodo=p1
        )
        Horario(dia="Lunes",     hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat205, aula=a3)
        Horario(dia="Miércoles", hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_mat205, aula=a3)

        # INF220 — Estructura de Datos I
        g_inf220 = GrupoMateria(
            grupo="SE",
            nombre=f"Grupo SE - {m_inf220.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_inf220,
            docente=d2,
            periodo=p1
        )
        Horario(dia="Martes",  hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_inf220, aula=a2)
        Horario(dia="Viernes", hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_inf220, aula=a2)

        # INF221 — Programación Ensamblador
        g_inf221 = GrupoMateria(
            grupo="SE",
            nombre=f"Grupo SE - {m_inf221.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_inf221,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Jueves",  hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_inf221, aula=a1)
        Horario(dia="Viernes", hora_inicio=datetime.time(12,0), hora_fin=datetime.time(14,0), grupo=g_inf221, aula=a1)

        # ADM200 — Contabilidad
        g_adm200 = GrupoMateria(
            grupo="SE",
            nombre=f"Grupo SE - {m_adm200.nombre}",
            estado="Activo",
            cupo=cupo,
            materia=m_adm200,
            docente=d1,
            periodo=p1
        )
        Horario(dia="Martes",  hora_inicio=datetime.time(16,0), hora_fin=datetime.time(18,0), grupo=g_adm200, aula=a3)
        Horario(dia="Viernes", hora_inicio=datetime.time(8,0),  hora_fin=datetime.time(10,0), grupo=g_adm200, aula=a3)
                

        # Aquí puedes continuar con todos los prerrequisitos y materias de semestres 6 a 9 según la imagen
        commit()
        return {"status": "success", "message": "Base de datos inicializada con el nuevo plan"}
    except Exception as e: 
        rollback()  # Revierte todos los cambios si hay error (por ejemplo, llave duplicada)
        return jsonify({"status": "error", "message": f"Error al insertar datos: {str(e)}"}), 400
        




@app.route("/login", methods=["POST"])
@db_session
def login():
    data = request.json
    registro = data.get("usuario")
    ci = data.get("password")

    Estudiante = dborm.db.Estudiante

    estudiante = Estudiante.get(registro=registro, ci=ci)
    if estudiante:
        token = jwt.encode(
            {
                "user": estudiante.registro,
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        return jsonify({
            "token": token,
            "usuario": estudiante.nombre,
            "registro": estudiante.registro
        })
    
    return jsonify({"error": "Credenciales incorrectas"}), 401
# Rutas Carrera
# =========================
@app.route("/carreras", methods=["POST"])
#@token_required
@db_session
def agregar_carrera():
    Carrera = dborm.db.Carrera
    data = request.json
    
    try:
        carrera = Carrera(
            nombre=data["nombre"],
            codigo=data["codigo"],
            otros=data.get("otros", "")
        )
        commit()
        return jsonify({"msg": "Carrera agregada con éxito", "id": carrera.id}), 201
 
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400



@app.route("/carreras", methods=["GET"])
#@token_required
@db_session
def listar_carreras():
    #tarea.guardar_tarea(instruccion="GET", modelo="Carrera", datos='')
    
    Carrera = dborm.db.Carrera
    carreras = Carrera.select()[:]
    data = [c.to_full_dict() for c in carreras]
    return jsonify(data), 200
    
@app.route("/carrerasasync", methods=["POST"])
#@token_required
def agregar_carreraasync():
    data = request.json
    try:
        # Crear el DTO con los datos de la carrera
        dto = CarreraDTO(
            nombre=data["nombre"],
            codigo=data["codigo"],
            otros=data.get("otros", "")
        )
        
        # Agregar la tarea a la cola para procesarla de manera asincrónica
       # tarea_id = cola.agregar(
        #    metodo=Metodo.POST,
       #     prioridad=Prioridad.ALTA,
       #     payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
       # ) 
        
        tarea_id = colamanager.agregar_tarea_Round_Robin( 
        metodo=Metodo.POST,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/carrerasasync", methods=["PUT"])
#@token_required
def actualizar_carrera():
    data = request.json
    try:
        # Crear el DTO con los datos de la carrera para actualización
        dto = CarreraDTO(
            id=data.get("id", None),
            nombre=data.get("nombre", None),
            codigo=data.get("codigo", None),
            otros=data.get("otros", "")
        )
        
        # Agregar la tarea de actualización a la cola
       # tarea_id = cola.agregar(
        #    metodo=Metodo.PUT,
        #    prioridad=Prioridad.ALTA,
       #     payload=json.dumps(dto.to_dictid())  # Usar to_dictid para mantener 'id' en el payload
       # ) 
        
        
        tarea_id = colamanager.agregar_tarea_Round_Robin( 
        metodo=Metodo.PUT,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
@app.route("/carrerasasync", methods=["GET"])
#@token_required
def listar_carrerasasync():
    dto = CarreraDTO()  # Crear un DTO vacío para representar la búsqueda general de carreras
    
    # Agregar la tarea para listar todas las carreras a la cola
   # tarea_id = cola.agregar(
   #     metodo=Metodo.GET,
   # #    prioridad=Prioridad.ALTA,
   #     payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
   # ) 
    
    tarea_id = colamanager.agregar_tarea_Round_Robin( 
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  )

    return jsonify({"id_tarea": tarea_id}), 202
    
    
    
# =========================
# Rutas Worker manager
# ========================= 
    
    return jsonify(data), 200
@app.route("/stop", methods=["POST"])
def stop_workers():
    """Detiene todos los workers"""
    try:
        worker_manager.stop_all()
        return jsonify({"message": "Workers detenido "}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/restart", methods=["POST"])
def restart_workers():
    """Detiene todos los workers"""
    try:
        worker_manager.start()
        return jsonify({"message": "Workers detenido "}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/pause", methods=["POST"])
def pause_workers():
    """Pausa todos los workers"""
    try:
        worker_manager.pause_all()
        return jsonify({"message": "Workers pausado "}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/resume", methods=["POST"])
def resume_workers():
    """Reanuda todos los workers"""
    try:
        worker_manager.resume_all()
        return jsonify({"message": "Workers continuado "}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# =========================
# Rutas PlanDeEstudio
# =========================
@app.route("/planes", methods=["POST"])
#@token_required
@db_session
def agregar_plan():
    PlanDeEstudio = dborm.db.PlanDeEstudio
    Carrera = dborm.db.Carrera
    data = request.json
    try:
        carrera = Carrera[data["carrera_id"]]
        plan = PlanDeEstudio(
            nombre=data["nombre"],
            codigo=data["codigo"],
            fecha=datetime.date.fromisoformat(data["fecha"]),
            estado=data["estado"],
            carrera=carrera
        )
        commit()
        return jsonify({"msg": "Plan de estudio agregado", "id": plan.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/planesasync", methods=["POST"])
#@token_required
def agregar_planasync():
   
    data = request.json
    try:
        dto = PlanDeEstudioDTO(
            nombre=data["nombre"],
            codigo=data["codigo"],
            fecha=datetime.date.fromisoformat(data["fecha"]),
            estado=data["estado"],
            carrera_id=data["carrera_id"])
        
        tarea_id = cola.agregar(
        metodo=Metodo.POST,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
        ) 
        return jsonify({"msg": "tarea procesandose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/planesasync", methods=["PUT"])
#@token_required
def agregar_planupdateasync():
   
    data = request.json
    try:
        dto = PlanDeEstudioDTO(
            id=data.get("id",None),
            nombre=data.get("nombre", None), 
            codigo=data.get("codigo", None),  
            fecha=datetime.date.fromisoformat(data["fecha"]) if "fecha" in data else None, 
            estado=data.get("estado", None), 
            carrera_id=data.get("carrera_id", None) 
        )
        
        tarea_id = cola.agregar(
        metodo=Metodo.PUT,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dictid())
        ) 
        return jsonify({"msg": "tarea procesandose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/planesasync", methods=["GET"])
#@token_required
def listar_planesasync():
    dto = PlanDeEstudioDTO()
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
    ) 
    return jsonify({"id_tarea": tarea_id}), 202


@app.route("/planes", methods=["GET"])
#@token_required
@db_session
def listar_planes():
    PlanDeEstudio = dborm.db.PlanDeEstudio
    planes = PlanDeEstudio.select()[:]
    data = [p.to_full_dict() for p in planes]
    cola.agregar( metodo=Metodo.GET, prioridad=Prioridad.ALTA, payload=data)
    tarea = cola.obtener()
    #print("Tarea obtenida de la cola:", tarea)
    return jsonify(data), 200



# =========================
# Rutas Materia (uno por uno)
# =========================
@app.route("/materias", methods=["POST"])
#@token_required
@db_session
def agregar_materia():
    Materia = dborm.db.Materia
    PlanDeEstudio = dborm.db.PlanDeEstudio
    Nivel = dborm.db.Nivel
    data = request.json
    try:
        plan = PlanDeEstudio[data["plan_id"]]
        nivel = Nivel[data["nivel_id"]]
        materia = Materia(
            sigla=data["sigla"],
            nombre=data["nombre"],
            creditos=data["creditos"],
            plan=plan,
            nivel=nivel
        )
        commit()
        return jsonify({"msg": "Materia agregada", "id": materia.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/materias", methods=["GET"])
#@token_required
@db_session
def listar_materias():
    Materia = dborm.db.Materia
    materias = Materia.select()[:]  
    data = [m.to_full_dict() for m in materias]  
    
    return jsonify(data), 200

@app.route("/materiasasync", methods=["POST"])
#@token_required
def agregar_materia_async():
    data = request.json
    try:
        dto = MateriaDTO(
            sigla=data["sigla"],
            nombre=data["nombre"],
            creditos=data["creditos"],
            plan_id=data["plan_id"],
            nivel_id=data["nivel_id"]
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict()) 
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/materiasasync", methods=["PUT"])
#@token_required
def actualizar_materia_async():
    data = request.json
    try:

        dto = MateriaDTO(
            id=data.get("id", None),
            sigla=data.get("sigla", None),
            nombre=data.get("nombre", None),
            creditos=data.get("creditos", None),
            plan_id=data.get("plan_id", None),
            nivel_id=data.get("nivel_id", None)
        )

        
        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/materiasasync", methods=["GET"])
#@token_required
def listar_materias_async():
    dto = MateriaDTO() 

    
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  
    )

    return jsonify({"id_tarea": tarea_id}), 202












# =========================
@app.route("/prerrequisitos", methods=["POST"])
#@token_required
@db_session
def agregar_prerrequisito():
    Materia = dborm.db.Materia
    Prerequisito = dborm.db.Prerequisito
    data = request.json
    try:
        materia = Materia[data["materia_id"]]
        materia_requisito = Materia[data["materia_requisito_id"]]
        pr = Prerequisito(materia=materia, materia_requisito=materia_requisito)
        commit()
        return jsonify({"msg": "Prerrequisito agregado", "id": pr.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/prerrequisitos", methods=["GET"])
#@token_required
@db_session
def listar_prerrequisitos():
    Prerequisito = dborm.db.Prerequisito
    #print(Prerequisito)
    #print(Prerequisito.select())
    prerequisitos = [n.to_full_dict() for n in Prerequisito.select()]
    
    return jsonify(prerequisitos), 200

@app.route("/prerrequisitosasync", methods=["GET"])
#@token_required
def listar_prerrequisitosasync():
    dto = PrerequisitoDTO()
   
    tarea_id = cola.agregar(metodo=Metodo.GET,prioridad=Prioridad.ALTA,payload=json.dumps(dto.to_dict()))
    return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
  
@app.route("/prerrequisitosasync", methods=["POST"])
#@token_required
def agregar_prerrequisito_async():
    data = request.json
    try:
        # Crear el DTO con los datos del prerrequisito
        dto = PrerequisitoDTO(
            materia_id=data["materia_id"],
            materia_requisito_id=data["materia_requisito_id"]
        )

        # Agregar la tarea a la cola para procesarla de manera asincrónica
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
    
    
    
    
    

# ---------- NIVELES ----------
@app.route("/niveles", methods=["POST"])
#@token_required
@db_session
def agregar_nivel():
    Nivel = dborm.db.Nivel
    data = request.json
    try:
        nivel = Nivel(nivel=data["nivel"])
        commit()
        return jsonify({"msg": "Nivel agregado", "id": nivel.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/niveles", methods=["GET"])
#@token_required
@db_session
def listar_niveles():
    Nivel = dborm.db.Nivel
    niveles = [n.to_full_dict() for n in Nivel.select()]
    
    return jsonify(niveles), 200


@app.route("/nivelesasync", methods=["POST"])
#@token_required
def agregar_nivelasync():
    data = request.json
    try:
        dto = NivelDTO(
            nivel=data["nivel"]
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/nivelesasync", methods=["GET"])
#@token_required
def listar_nivelesasync():
    dto = NivelDTO()  # Crear un DTO vacío para representar la búsqueda general de niveles

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
    )

    return jsonify({"id_tarea": tarea_id}), 202



# =========================
# Rutas Docente
# =========================
@app.route("/docentes", methods=["POST"])
#@token_required
@db_session
def agregar_docente():
    Docente = dborm.db.Docente
    data = request.json
    try:
        docente = Docente(
            registro=data["registro"],
            ci=data["ci"],
            nombre=data["nombre"],
            telefono=data["telefono"],
            otros=data.get("otros", "")
        )
        commit()
        return jsonify({"msg": "Docente agregado", "id": docente.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/docentes", methods=["GET"])
#@token_required
@db_session
def listar_docentes():
    Docente = dborm.db.Docente
    docentes = [n.to_full_dict() for n in Docente.select()]
    
    return jsonify(docentes), 200

@app.route("/docentesasync", methods=["POST"])
#@token_required
def agregar_docente_async():
    data = request.json
    try:
        dto = DocenteDTO(
            registro=data["registro"],
            ci=data["ci"],
            nombre=data["nombre"],
            telefono=data["telefono"],
            otros=data.get("otros", "")
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/docentesasync", methods=["PUT"])
#@token_required
def actualizar_docente_async():
    data = request.json
    try:
        dto = DocenteDTO(
            id=data.get("id", None),
            registro=data.get("registro", None),
            ci=data.get("ci", None),
            nombre=data.get("nombre", None),
            telefono=data.get("telefono", None),
            otros=data.get("otros", "")
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar el método `to_dictid` para incluir 'id' en el payload
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/docentesasync", methods=["GET"])
#@token_required
def listar_docentes_async():
    dto = DocenteDTO()  # Crear un DTO vacío para representar la búsqueda general de docentes

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    )

    return jsonify({"id_tarea": tarea_id}), 202



# ---------- ESTUDIANTES ----------
@app.route("/estudiantes", methods=["POST"])
#@token_required
@db_session
def agregar_estudiante():
    Estudiante = dborm.db.Estudiante
    data = request.json
    try:
        estudiante = Estudiante(
            registro=data["registro"],
            ci=data["ci"],
            nombre=data["nombre"],
            telefono=data.get("telefono", ""),
            correo=data.get("correo", ""),
            otros=data.get("otros", "")
        )
        commit()
        return jsonify({"msg": "Estudiante agregado", "id": estudiante.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/estudiantes", methods=["GET"])
#@token_required
@db_session
def listar_estudiantes():
    Estudiante = dborm.db.Estudiante
    estudiantes = [n.to_full_dict() for n in Estudiante.select()]
   
    return jsonify(estudiantes), 200
@app.route("/estudiantesasync", methods=["POST"])
#@token_required
def agregar_estudiante_async():
    data = request.json
    try:
        dto = EstudianteDTO(
            registro=data["registro"],
            ci=data["ci"],
            nombre=data["nombre"],
            telefono=data.get("telefono", ""),
            correo=data.get("correo", ""),
            otros=data.get("otros", "")
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/estudiantesasync", methods=["PUT"])
#@token_required
def actualizar_estudiante_async():
    data = request.json
    try:
        dto = EstudianteDTO(
            id=data.get("id", None),
            registro=data.get("registro", None),
            ci=data.get("ci", None),
            nombre=data.get("nombre", None),
            telefono=data.get("telefono", None),
            correo=data.get("correo", None),
            otros=data.get("otros", "")
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar el método `to_dictid` para incluir 'id' en el payload
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
@app.route("/estudiantesasync", methods=["GET"])
#@token_required
def listar_estudiantes_async():
    dto = EstudianteDTO()  # Crear un DTO vacío para representar la búsqueda general de estudiantes

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    )

    return jsonify({"id_tarea": tarea_id}), 202



# =========================
# Rutas para Modulo
# =========================

@app.route("/modulos", methods=["GET"])
#@token_required
@db_session
def listar_modulos():
    Modulo = dborm.db.Modulo
    modulos = [n.to_full_dict() for n in Modulo.select()]
    
    return jsonify(modulos), 200


@app.route("/modulos", methods=["POST"])
#@token_required
@db_session
def agregar_modulo():
    Modulo = dborm.db.Modulo
    data = request.json
    try:
        modulo = Modulo(
            numero=data["numero"],
            nombre=data.get("nombre")
        )
        return jsonify({
            "msg": "Módulo agregado con éxito",
            "modulo": {
                "id": modulo.id,
                "numero": modulo.numero,
                "nombre": modulo.nombre
            }
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/modulosasync", methods=["POST"])
#@token_required
def agregar_modulo_async():
    data = request.json
    try:
        dto = ModuloDTO(
            numero=data["numero"],
            nombre=data.get("nombre", "")
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/modulosasync", methods=["PUT"])
#@token_required
def actualizar_modulo_async():
    data = request.json
    try:
        dto = ModuloDTO(
            id=data.get("id", None),
            numero=data.get("numero", None),
            nombre=data.get("nombre", None)
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar el método `to_dictid` para incluir 'id' en el payload
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/modulosasync", methods=["GET"])
#@token_required
def listar_modulos_async():
    dto = ModuloDTO()  # Crear un DTO vacío para representar la búsqueda general de módulos

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    )
    
 
    return jsonify({"id_tarea": tarea_id}), 202


# =========================
# Rutas para Aula
# =========================

@app.route("/aulas", methods=["GET"])
#@token_required
@db_session
def listar_aulas():
    Aula = dborm.db.Aula
    aulas = [n.to_full_dict() for n in Aula.select()]
    return jsonify(aulas), 200


@app.route("/aulas", methods=["POST"])
@db_session
def agregar_aula():
    data = request.json
    Modulo = dborm.db.Modulo
    Aula = dborm.db.Aula
    try:
        modulo = Modulo[data["modulo_id"]]
        aula = Aula(
            numero=data["numero"],
            nombre=data.get("nombre"),
            modulo=modulo
        )
        return jsonify({
            "msg": "Aula agregada con éxito",
            "aula": {
                "id": aula.id,
                "numero": aula.numero,
                "nombre": aula.nombre,
                "modulo_id": modulo.id
            }
        }), 201
    except ObjectNotFound:
        return jsonify({"error": "Módulo no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
@app.route("/aulasasync", methods=["POST"])
#@token_required
def agregar_aula_async():
    data = request.json
    try:
        dto = AulaDTO(
            numero=data["numero"],
            nombre=data.get("nombre", ""),
            modulo_id=data["modulo_id"]
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/aulasasync", methods=["PUT"])
#@token_required
def actualizar_aula_async():
    data = request.json
    try:
        dto = AulaDTO(
            id=data.get("id", None),
            numero=data.get("numero", None),
            nombre=data.get("nombre", None),
            modulo_id=data.get("modulo_id", None)
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar el método `to_dictid` para incluir 'id' en el payload
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
    
@app.route("/aulasasync", methods=["GET"])
#@token_required
def listar_aulas_async():
    dto = AulaDTO()  # Crear un DTO vacío para representar la búsqueda general de aulas

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    )

    return jsonify({"id_tarea": tarea_id}), 202
    
    
#-------------horarios----------    
    

@app.route("/horarios", methods=["POST"])
@db_session
def agregar_horario():
    Horario = dborm.db.Horario
    GrupoMateria = dborm.db.GrupoMateria
    Aula = dborm.db.Aula
    data = request.json
    try:
        grupo = GrupoMateria[data["grupo_id"]]
        aula = Aula[data["aula_id"]] if "aula_id" in data else None

        horario = Horario(
            dia=data["dia"],
            hora_inicio=datetime.time.fromisoformat(data["hora_inicio"]),
            hora_fin=datetime.time.fromisoformat(data["hora_fin"]),
            grupo=grupo,
            aula=aula
        )
        commit()
        return jsonify({
            "msg": "Horario agregado con éxito",
            "horario": {
                "id": horario.id,
                "dia": horario.dia,
                "hora_inicio": str(horario.hora_inicio),
                "hora_fin": str(horario.hora_fin),
                "grupo": {"id": grupo.id, "nombre": grupo.nombre},
                "aula": {"id": aula.id, "numero": aula.numero} if aula else None
            }
        }), 201
    except ObjectNotFound:
        return jsonify({"error": "Grupo o Aula no encontrado"}), 404
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/horarios", methods=["GET"])
@db_session
def listar_horarios():
    Horario = dborm.db.Horario
    horarios = [n.to_full_dict() for n in Horario.select()]
    return jsonify({"horarios": horarios}), 200

@app.route("/horariosasync", methods=["POST"])
#@token_required
def agregar_horario_async():
    data = request.json
    try:
        # Crear el DTO para el horario
        dto = HorarioDTO(
            dia=data["dia"],
            hora_inicio=data["hora_inicio"],
            hora_fin=data["hora_fin"],
            grupo_id=data["grupo_id"],
            aula_id=data.get("aula_id", None)
        )

        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/horariosasync", methods=["PUT"])
#@token_required
def actualizar_horario_async():
    data = request.json
    try:
        dto = HorarioDTO(
            id=data.get("id", None),
            dia=data.get("dia", None),
            hora_inicio=data.get("hora_inicio", None),
            hora_fin=data.get("hora_fin", None),
            grupo_id=data.get("grupo_id", None),
            aula_id=data.get("aula_id", None)
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar to_dictid para mantener 'id' en el payload
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/horariosasync", methods=["GET"])
#@token_required
def listar_horarios_async():
    dto = HorarioDTO()  # Crear un DTO vacío para representar la búsqueda general de horarios

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    )

    return jsonify({"id_tarea": tarea_id}), 202

# =========================
# Gestión
# =========================
@app.route("/gestiones", methods=["POST"])
@db_session
def agregar_gestion():
    Gestion = dborm.db.Gestion
    data = request.json
    try:
        gestion = Gestion(anio=data["anio"])
        commit()
        return jsonify({
            "msg": "Gestión agregada con éxito",
            "gestion": {"id": gestion.id, "anio": gestion.anio}
        }), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/gestiones", methods=["GET"])
@db_session
def listar_gestiones():
    Gestion = dborm.db.Gestion
    gestiones = [n.to_full_dict() for n in Gestion.select()]
    return jsonify(gestiones), 200

# =========================
# TipoPeriodo
# =========================
@app.route("/tipoperiodos", methods=["POST"])
@db_session
def agregar_tipoperiodo():
    TipoPeriodo = dborm.db.TipoPeriodo
    data = request.json
    try:
        tp = TipoPeriodo(nombre=data["nombre"])
        commit()
        return jsonify({
            "msg": "Tipo de periodo agregado",
            "tipoperiodo": {"id": tp.id, "nombre": tp.nombre}
        }), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/tipoperiodos", methods=["GET"])
@db_session
def listar_tipoperiodos():
    TipoPeriodo = dborm.db.TipoPeriodo
    tps = [n.to_full_dict() for n in TipoPeriodo.select()]
    return jsonify(tps), 200
    
# =========================
# Periodo
# =========================
@app.route("/periodos", methods=["POST"])
@db_session
def agregar_periodo():
    Periodo = dborm.db.Periodo
    Gestion = dborm.db.Gestion
    TipoPeriodo = dborm.db.TipoPeriodo
    data = request.json
    try:
        gestion = Gestion[data["gestion_id"]]
        tipoperiodo = TipoPeriodo[data["tipoperiodo_id"]]
        periodo = Periodo(
            numero=data["numero"],
            descripcion=data.get("descripcion", ""),
            gestion=gestion,
            tipoperiodo=tipoperiodo
        )
        commit()
        return jsonify({
            "msg": "Periodo agregado",
            "periodo": {
                "id": periodo.id,
                "numero": periodo.numero,
                "descripcion": periodo.descripcion,
                "gestion": {"id": gestion.id, "anio": gestion.anio},
                "tipoperiodo": {"id": tipoperiodo.id, "nombre": tipoperiodo.nombre}
            }
        }), 201
    except ObjectNotFound:
        rollback()
        return jsonify({"error": "Gestión o TipoPeriodo no encontrado"}), 404
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/periodos", methods=["GET"])
@db_session
def listar_periodos():
    Periodo = dborm.db.Periodo
    periodos = [n.to_full_dict() for n in Periodo.select()]
    return jsonify(periodos), 200


# =========================
# GrupoMateria
# =========================
@app.route("/gruposmateria", methods=["POST"])
@db_session
def agregar_grupo_materia():
    GrupoMateria = dborm.db.GrupoMateria
    Materia = dborm.db.Materia
    Docente = dborm.db.Docente
    Periodo = dborm.db.Periodo
    data = request.json
    try:
        materia = Materia[data["materia_id"]]
        docente = Docente[data["docente_id"]]
        periodo = Periodo[data["periodo_id"]]

        grupo = GrupoMateria(
            grupo=data["grupo"],
            nombre=data.get("nombre", ""),
            estado=data.get("estado", ""),
            materia=materia,
            docente=docente,
            periodo=periodo  # 🔑 Asociamos el periodo
        )
        commit()
        return jsonify(grupo.to_full_dict()), 201
        # return jsonify({
        #     "msg": "GrupoMateria agregado",
        #     "grupo": {
        #         "id": grupo.id,
        #         "grupo": grupo.grupo,
        #         "nombre": grupo.nombre,
        #         "estado": grupo.estado,
        #         "materia": {"id": materia.id, "nombre": materia.nombre},
        #         "docente": {"id": docente.id, "nombre": docente.nombre},
        #         "periodo": {"id": periodo.id, "numero": periodo.numero, "descripcion": periodo.descripcion}
        #     }
        # }), 201
    except ObjectNotFound:
        rollback()
        return jsonify({"error": "Materia, Docente o Periodo no encontrado"}), 404
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400


@app.route("/gruposmateria", methods=["GET"])
@db_session
def listar_grupos_materia():
    GrupoMateria = dborm.db.GrupoMateria
    grupos = [n.to_full_dict() for n in GrupoMateria.select()]
    
    return jsonify(grupos), 200
  
@app.route("/gruposmateriaasync", methods=["POST"])
#@token_required
def grupomateriaasync():
    data = request.json
    try:
        # Crear el DTO
        dto = GrupoMateriaDTO(
            grupo=data["grupo"],
            nombre=data.get("nombre", ""),
            estado=data.get("estado", ""),
            materia_id=data["materia_id"],
            docente_id=data["docente_id"],
            periodo_id=data["periodo_id"]
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/gruposmateriaasync", methods=["PUT"])
#@token_required
def actualizar_grupo_materia_async():
    data = request.json
    try:
        # Crear el DTO para actualización
        dto = GrupoMateriaDTO(
            id=data.get("id", None),
            grupo=data.get("grupo", None),
            nombre=data.get("nombre", None),
            estado=data.get("estado", None),
            materia_id=data.get("materia_id", None),
            docente_id=data.get("docente_id", None),
            periodo_id=data.get("periodo_id", None)
        )

        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/gruposmateriaasync", methods=["GET"])
#@token_required
def listar_grupos_materia_async():
    dto = GrupoMateriaDTO()

    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar DTO serializado
    )

    return jsonify({"id_tarea": tarea_id}), 202


# =========================
# Inscripcion
# =========================
@app.route("/inscripciones", methods=["POST"])
@db_session
def agregar_inscripcion():
    Inscripcion = dborm.db.Inscripcion
    Estudiante = dborm.db.Estudiante
    Periodo = dborm.db.Periodo
    data = request.json
    try:
        # Buscar estudiante por registro
        estudiante = Estudiante.get(registro=data["estudiante_registro"])
        if not estudiante:
            return jsonify({"error": "Estudiante no encontrado"}), 404

        periodo = Periodo.get(id=data["periodo_id"])
        if not periodo:
            return jsonify({"error": "Periodo no encontrado"}), 404

        # Crear inscripción
        inscripcion = Inscripcion(
            fecha=datetime.date.fromisoformat(data["fecha"]),
            estudiante=estudiante,
            periodo=periodo
        )
        commit()

        return jsonify({
            "msg": "Inscripción agregada",
            "inscripcion": {
                "id": inscripcion.id,
                "fecha": str(inscripcion.fecha),
                "estudiante": {"id": estudiante.id, "nombre": estudiante.nombre},
                "periodo": {"id": periodo.id, "numero": periodo.numero}
            }
        }), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400


@app.route("/inscripciones", methods=["GET"])
@db_session
def listar_inscripciones():
    Inscripcion = dborm.db.Inscripcion
    inscripciones =[n.to_full_dict() for n in Inscripcion.select()]
   
    return jsonify(inscripciones), 200



#----------inscripciones ----------

@app.route("/inscripcionesasync", methods=["POST"])
#@token_required
def agregar_inscripcionasync():
    data = request.json
    try:
        dto = InscripcionDTO(
            fecha=datetime.date.fromisoformat(data["fecha"]),
            estudiante_id=data["estudiante_id"],
            periodo_id=data["periodo_id"]
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        ) 
        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/inscripcionesasync", methods=["PUT"])
#@token_required
def actualizar_inscripcionasync():
    data = request.json
    try:
        dto = InscripcionDTO(
            id=data.get("id", None),
            fecha=datetime.date.fromisoformat(data["fecha"]) if "fecha" in data else None,
            estudiante_id=data.get("estudiante_id", None),
            periodo_id=data.get("periodo_id", None)
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())
        ) 
        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/inscripcionesasync", methods=["GET"])
#@token_required
def listar_inscripcionesasync():
    dto = InscripcionDTO()  # Crear un DTO vacío para representar la búsqueda general de inscripciones
    
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    ) 

    return jsonify({"id_tarea": tarea_id}), 202





# =========================
# InscripcionMateria
# =========================


@app.route("/inscripcionmaterialist", methods=["POST"])
@db_session
def inscripcionmaterialist():
    """
    Crea una inscripción para un estudiante en un período específico,
    inscribiéndolo en múltiples materias (GrupoMateria) a la vez.
    La operación es atómica: si falla la inscripción a una materia,
    se revierte toda la transacción.

    JSON esperado:
    {
        "estudiante_registro": "219000111",
        "periodo_id": 1,
        "grupos_ids": [101, 102]
    }
    """
    Inscripcion = dborm.db.Inscripcion
    Estudiante = dborm.db.Estudiante
    Periodo = dborm.db.Periodo
    InscripcionMateria = dborm.db.InscripcionMateria
    GrupoMateria = dborm.db.GrupoMateria
    
    data = request.json
    
    try:
        # 1. Validaciones iniciales
        estudiante = Estudiante.get(registro=data["estudiante_registro"])
        if not estudiante:
            return jsonify({"error": "Estudiante no encontrado"}), 404

        periodo = Periodo.get(id=data["periodo_id"])
        if not periodo:
            return jsonify({"error": "Periodo no encontrado"}), 404

        grupos_ids = data.get("grupos_ids", [])
        if not isinstance(grupos_ids, list) or not grupos_ids:
            return jsonify({"error": "La lista 'grupos_ids' es requerida y no puede estar vacía"}), 400

        # 2. Validar todos los grupos y cupos ANTES de crear nada
        grupos_a_inscribir = []
        for grupo_id in grupos_ids:
            grupo = GrupoMateria.get(id=grupo_id)
            if not grupo:
                return jsonify({"error": f"El grupo con ID {grupo_id} no fue encontrado"}), 404
            if grupo.cupo is None or grupo.cupo <= 0:
                return jsonify({"error": f"No hay cupos disponibles en el grupo '{grupo.nombre}' (ID: {grupo_id})"}), 400
            grupos_a_inscribir.append(grupo)
            
        # 3. Crear la inscripción principal
        # Usamos la fecha actual del servidor para la inscripción.
        nueva_inscripcion = Inscripcion(
            fecha=datetime.date.today(),
            estudiante=estudiante,
            periodo=periodo
        )
        
        # 4. Crear las inscripciones a materias y descontar cupos
        materias_inscritas_info = []
        for grupo in grupos_a_inscribir:
            InscripcionMateria(inscripcion=nueva_inscripcion, grupo=grupo)
            grupo.cupo -= 1  # Descontar cupo
            
            materias_inscritas_info.append({
                "id_grupo": grupo.id,
                "nombre_grupo": grupo.nombre,
                "cupo_restante": grupo.cupo
            })

        # 5. Si todo salió bien, confirmar la transacción
        commit()

        # 6. Devolver una respuesta exitosa y detallada
        return jsonify({
            "msg": "Inscripción completada exitosamente.",
            "inscripcion": {
                "id": nueva_inscripcion.id,
                "fecha": str(nueva_inscripcion.fecha),
                "estudiante": {"id": estudiante.id, "nombre": estudiante.nombre},
                "periodo": {"id": periodo.id, "numero": periodo.numero}
            },
            "materias_inscritas": materias_inscritas_info
        }), 201

    except Exception as e:
        # Si ocurre cualquier error, revertir todos los cambios en la BD
        rollback()
        # Es buena práctica registrar el error real en logs del servidor
        # print(f"Error en la inscripción: {e}") 
        return jsonify({"error": "Ocurrió un error interno al procesar la inscripción.", "detalle": str(e)}), 500


@app.route("/inscripcionmaterialistasync", methods=["POST"])
@db_session
def inscripcionmaterialistasync():
    
    data = request.json
    print(data)
    try:
        dto = InscripcionMasivaDTO(
            fecha=datetime.date.fromisoformat(data["fecha"]) if "fecha" in data else None,
            estudiante_registro=data.get("estudiante_registro", None),
            periodo_id= data.get("periodo_id", None),
            grupos_ids= data.get("grupos_ids", []) 
        )
        
        tarea_id = colamanager.agregar_tarea_Round_Robin( 
        metodo=Metodo.POST,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  )
        
        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

        # 6. Devolver una respuesta exitosa y detallada
    


@app.route("/inscripcionmateria", methods=["POST"])
@db_session
def agregar_inscripcion_materia():
    InscripcionMateria = dborm.db.InscripcionMateria
    Inscripcion = dborm.db.Inscripcion
    GrupoMateria = dborm.db.GrupoMateria
    data = request.json
    try:
        # Obtener inscripción y grupo
        inscripcion = Inscripcion.get(id=data["inscripcion_id"])
        grupo = GrupoMateria.get(id=data["grupo_id"])
        if not inscripcion or not grupo:
            return jsonify({"error": "Inscripcion o GrupoMateria no encontrado"}), 404

        # Validar cupo
        if grupo.cupo is None or grupo.cupo <= 0:
            return jsonify({"error": "No hay cupos disponibles en este grupo"}), 400

        # Crear InscripcionMateria
        im = InscripcionMateria(inscripcion=inscripcion, grupo=grupo)

        # Descontar cupo
        grupo.cupo -= 1
        commit()

        return jsonify({
            "msg": "InscripcionMateria agregada",
            "inscripcionmateria": {
                "id": im.id,
                "inscripcion": {"id": inscripcion.id, "estudiante": inscripcion.estudiante.nombre},
                "grupo": {"id": grupo.id, "nombre": grupo.nombre, "cupo_restante": grupo.cupo}
            }
        }), 201

    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400


@app.route("/inscripcionmateria", methods=["GET"])
@db_session
def listar_inscripcion_materia():
    InscripcionMateria = dborm.db.InscripcionMateria
    inscripciones_materia = [n.to_full_dict() for n in InscripcionMateria.select()]
   
    return jsonify(inscripciones_materia), 200




@app.route("/inscripcionmateriaasync", methods=["POST"])
#@token_required
def agregar_inscripcion_materiaasync():
    data = request.json
    try:
        dto = InscripcionMateriaDTO(
            inscripcion_id=data["inscripcion_id"],
            grupo_id=data["grupo_id"]
        )
        
        # tarea_id = cola.agregar(
        #     metodo=Metodo.POST,
        #     prioridad=Prioridad.ALTA,
        #     payload=json.dumps(dto.to_dict())
        # )
        
        tarea_id = colamanager.agregar_tarea_Round_Robin( 
        metodo=Metodo.POST,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  )
        
        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/inscripcionmateriaasync", methods=["PUT"])
#@token_required
def actualizar_inscripcion_materiaasync():
    data = request.json
    try:
        dto = InscripcionMateriaDTO(
            id=data.get("id", None),
            inscripcion_id=data.get("inscripcion_id", None),
            grupo_id=data.get("grupo_id", None)
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())
        )
        
        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/inscripcionmateriaasync", methods=["GET"])
#@token_required
def listar_inscripcion_materiaasync():
    dto = InscripcionMateriaDTO()  # DTO vacío para listar todas las inscripciones
    
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
    )
    
    return jsonify({"id_tarea": tarea_id}), 202


# =========================
# POST - Agregar nota
# =========================
@app.route("/notas", methods=["POST"])
@db_session
def agregar_nota():
    Nota = dborm.db.Nota
    InscripcionMateria = dborm.db.InscripcionMateria
    data = request.json
    try:
        im = InscripcionMateria[data["inscripcion_materia_id"]]
        nota = Nota(
            nota=float(data["nota"]),
            inscripcionmateria=im
        )
        commit()
        return jsonify({
            "msg": "Nota agregada",
            "nota": {
                "id": nota.id,
                "valor": nota.nota,
                "inscripcion_materia": {
                    "id": im.id,
                    "estudiante": im.inscripcion.estudiante.nombre,
                    "grupo": im.grupo.nombre,
                    "materia": im.grupo.materia.nombre
                }
            }
        }), 201
    except ObjectNotFound:
        rollback()
        return jsonify({"error": "InscripcionMateria no encontrada"}), 404
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/notasasync", methods=["POST"])
#@token_required
def agregar_nota_async():
    data = request.json
    try:
        dto = NotaDTO(
            nota=float(data["nota"]),
            inscripcionmateria_id=data["InscripcionMateria_id"]
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/notasasync", methods=["PUT"])
#@token_required
def actualizar_nota_async():
    data = request.json
    try:
        dto = NotaDTO(
            id=data.get("id", None),
            nota=float(data["nota"]) if "nota" in data else None,
            inscripcionmateria_id=data.get("InscripcionMateria_id", None)
        )
        
        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())
        )

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/notasasync", methods=["GET"])
#@token_required
def listar_notas_async():
    dto = NotaDTO()  # DTO vacío para listar todas las notas
    
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
    )
    
    return jsonify({"id_tarea": tarea_id}), 202

# =========================
# GET - Listar notas
# =========================
@app.route("/notas", methods=["GET"])
@db_session
def listar_notas():
    Nota = dborm.db.Nota
    notas = [n.to_full_dict() for n in Nota.select()]
    return jsonify(notas), 200

@app.route("/notasxregistro", methods=["GET"])
@db_session
def obtener_notas_estudiante():
    estudiante_registro = request.args.get("registro")
    if not estudiante_registro:
        return jsonify({"error": "Debes enviar registro del estudiante"}), 400

    Nota = dborm.db.Nota

    notas = [
        {
            "id": n.id,
            "valor": n.nota,
            "grupo": n.inscripcionmateria.grupo.grupo,
            "materia": n.inscripcionmateria.grupo.materia.nombre,
            "docente": n.inscripcionmateria.grupo.docente.nombre
        }
        for n in Nota.select(lambda n: n.inscripcionmateria.inscripcion.estudiante.registro == estudiante_registro)
    ]

    if not notas:
        return jsonify({"registro": estudiante_registro, "notas": [], "msg": "No se encontraron notas"}), 200

    return jsonify({
        "registro": estudiante_registro,
        "notas": notas
    }), 200

@app.route("/materiasxregistro", methods=["GET"])
@db_session
def obtener_materias_estudiante():
    estudiante_registro = request.args.get("registro")
    if not estudiante_registro:
        return jsonify({"error": "Debes enviar registro del estudiante"}), 400

    Estudiante = dborm.db.Estudiante
    Nota       = dborm.db.Nota

    try:
        estudiante = Estudiante.get(registro=estudiante_registro)
        if not estudiante:
            return jsonify({"error": "Estudiante no encontrado"}), 404

        # resultado indexado por id_materia
        resultado = {}  # { id_materia: { materia_fields..., "nota": <float|null>, "__fecha": date } }

        for insc in estudiante.inscripciones:
            for im in insc.materias:  # im = InscripcionMateria
                mat = im.grupo.materia
                mid = mat.id

                # Obtener la última nota (si existiera) para esta InscripcionMateria
                if im.notas:
                    # última por id (asumiendo id incremental)
                    ultima_nota = max(im.notas, key=lambda n: n.id).nota
                else:
                    ultima_nota = None  # sin nota

                # Si aún no está o esta inscripción es más reciente, sobrescribe
                if (mid not in resultado) or (insc.fecha > resultado[mid]["__fecha"]):
                    # Armamos el dict base de la materia y sumamos la nota
                    data_materia = mat.to_dict()
                    data_materia["nota"] = ultima_nota  # float o None

                    # Guardamos fecha para resolver empates y luego la quitamos
                    data_materia["__fecha"] = insc.fecha
                    resultado[mid] = data_materia

        # Remover la clave interna "__fecha" antes de responder
        for v in resultado.values():
            v.pop("__fecha", None)

        return jsonify(resultado), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


CORS(app)


if __name__ == "__main__":
        

    app.run(host="0.0.0.0", 
            port=8000,
            use_reloader=False,
            threaded=True,       # Permite múltiples hilos
            processes=1          # Un proceso con múltiples hilos
            )
