import json
from flask import Flask, Response, render_template, request, jsonify
from pony.orm import Database, Required, Optional, PrimaryKey, db_session, Set , commit, rollback
from pony.orm.core import TransactionIntegrityError, ObjectNotFound
import datetime
from functools import wraps
import jwt
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
from ponyorm import DatabaseORM
import uuid

from tarea import Tarea,Metodo,Prioridad
from task_manager import WorkerManager


app = Flask(__name__)

# =========================
# Configuración de la BD
# =========================
dborm = DatabaseORM(
    user="topicos_ytxp_user",
    password="FR0EU36yrtu6u7HngTa1PxBhIHKnFx16",
    host="dpg-d2n0rgh5pdvs739dmlug-a.oregon-postgres.render.com",
    database="topicos_ytxp"
)

SECRET_KEY = "mi_clave_secreta"

REDIS_HOST = "18.191.219.182"     # ej: "54.210.xxx.xxx"
REDIS_PORT = 6379
REDIS_PASSWORD = "contraseniasegura2025"


cola = Cola2(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_password=REDIS_PASSWORD,  # tu password
    redis_db=1,
    nombre="cola"
)

worker_manager = WorkerManager(cola=cola, dborm=dborm, num_workers=1, bzpop_timeout=1)
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
    pendientes = cola.pendientes(limit=200, mayor_a_menor=True)

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
        g1 = GrupoMateria(grupo="A", nombre="Grupo A - Prog", estado="Activo", materia=m1, docente=d1,periodo=periodo)
        g2 = GrupoMateria(grupo="A", nombre="Grupo A - Mate", estado="Activo", materia=m2, docente=d1,periodo=periodo)
        g3 = GrupoMateria(grupo="A", nombre="Grupo A - Estructuras", estado="Activo", materia=m3, docente=d2,periodo=periodo)
        g4 = GrupoMateria(grupo="A", nombre="Grupo A - BD", estado="Activo", materia=m4, docente=d2,periodo=periodo)
        g5 = GrupoMateria(grupo="A", nombre="Grupo A - SO", estado="Activo", materia=m5, docente=d2,periodo=periodo)

        
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
@token_required
@db_session
def agregar_carrera():
    Carrera = dborm.db.Carrera
    data = request.json
    
    try:
        datos_serializados = {
            "nombre": data["nombre"],
            "codigo": data["codigo"],
            "otros": data.get("otros", "")
        }

        
    
        #carrera = Carrera(
         #   nombre=data["nombre"],
          #  codigo=data["codigo"],
           # otros=data.get("otros", "")
        #)
        #commit()
        #return jsonify({"msg": "Carrera agregada con éxito", "id": carrera.id}), 201
        return jsonify({"msg": "Carrera agregada con éxito"}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/carreras", methods=["GET"])
@token_required
@db_session
def listar_carreras():
    #tarea.guardar_tarea(instruccion="GET", modelo="Carrera", datos='')
    
    
    Carrera = dborm.db.Carrera
    carreras = Carrera.select()[:]
    data = [c.to_full_dict() for c in carreras]
    
@app.route("/carrerasasync", methods=["POST"])
@token_required
@db_session
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
        tarea_id = cola.agregar(
            metodo=Metodo.POST,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
        ) 

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
    
@app.route("/carrerasasync", methods=["PUT"])
@token_required
@db_session
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
        tarea_id = cola.agregar(
            metodo=Metodo.PUT,
            prioridad=Prioridad.ALTA,
            payload=json.dumps(dto.to_dictid())  # Usar to_dictid para mantener 'id' en el payload
        ) 

        return jsonify({"msg": "tarea procesándose...", "id_tarea": tarea_id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400
@app.route("/carrerasasync", methods=["GET"])
@token_required
@db_session
def listar_carrerasasync():
    dto = CarreraDTO()  # Crear un DTO vacío para representar la búsqueda general de carreras
    
    # Agregar la tarea para listar todas las carreras a la cola
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())  # Enviar el DTO serializado
    ) 

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
@token_required
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
def listar_planesasync():
    dto = PlanDeEstudioDTO()
    tarea_id = cola.agregar(
        metodo=Metodo.GET,
        prioridad=Prioridad.ALTA,
        payload=json.dumps(dto.to_dict())
    ) 
    return jsonify({"id_tarea": tarea_id}), 202


@app.route("/planes", methods=["GET"])
@token_required
@db_session
def listar_planes():
    PlanDeEstudio = dborm.db.PlanDeEstudio
    planes = PlanDeEstudio.select()[:]
    data = [p.to_full_dict() for p in planes]
    cola.agregar( metodo=Metodo.GET, prioridad=Prioridad.ALTA, payload=data)
    tarea = cola.obtener()
    print("Tarea obtenida de la cola:", tarea)
    return jsonify(data), 200



# =========================
# Rutas Materia (uno por uno)
# =========================
@app.route("/materias", methods=["POST"])
@token_required
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
@token_required
@db_session
def listar_materias():
    Materia = dborm.db.Materia
    materias = Materia.select()[:]  
    data = [m.to_full_dict() for m in materias]  
    
    return jsonify(data), 200

@app.route("/materiasasync", methods=["POST"])
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
def agregar_prerrequisito():
    Materia = dborm.db.Materia
    Prerequisito = dborm.db.Prerequisito
    data = request.json
    try:
        materia = Materia[data["materia_id"]]
        prereq = Materia[data["prereq_id"]]
        pr = Prerequisito(materia=materia, materia_requisito=prereq)
        commit()
        return jsonify({"msg": "Prerrequisito agregado", "id": pr.id}), 201
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/prerrequisitos", methods=["GET"])
@token_required
@db_session
def listar_prerrequisitos():
    Prerequisito = dborm.db.Prerequisito
    print(Prerequisito)
    print(Prerequisito.select())
    prerequisitos = [n.to_full_dict() for n in Prerequisito.select()]
    
    return jsonify(prerequisitos), 200
    
@app.route("/prerrequisitosasync", methods=["POST"])
@token_required
@db_session
def agregar_prerrequisito_async():
    data = request.json
    try:
        # Crear el DTO con los datos del prerrequisito
        dto = PrerequisitoDTO(
            materia_id=data["materia_id"],
            materia_id_requisito=data["prereq_id"]
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
@token_required
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
@token_required
@db_session
def listar_niveles():
    Nivel = dborm.db.Nivel
    niveles = [n.to_full_dict() for n in Nivel.select()]
    
    return jsonify(niveles), 200


@app.route("/nivelesasync", methods=["POST"])
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
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
@token_required
@db_session
def listar_docentes():
    Docente = dborm.db.Docente
    docentes = [n.to_full_dict() for n in Docente.select()]
    
    return jsonify(docentes), 200

@app.route("/docentesasync", methods=["POST"])
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
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
@token_required
@db_session
def listar_estudiantes():
    Estudiante = dborm.db.Estudiante
    estudiantes = [n.to_full_dict() for n in Estudiante.select()]
   
    return jsonify(estudiantes), 200
@app.route("/estudiantesasync", methods=["POST"])
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
def listar_modulos():
    Modulo = dborm.db.Modulo
    modulos = [n.to_full_dict() for n in Modulo.select()]
    
    return jsonify(modulos), 200


@app.route("/modulos", methods=["POST"])
@token_required
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
        return jsonify({
            "msg": "GrupoMateria agregado",
            "grupo": {
                "id": grupo.id,
                "grupo": grupo.grupo,
                "nombre": grupo.nombre,
                "estado": grupo.estado,
                "materia": {"id": materia.id, "nombre": materia.nombre},
                "docente": {"id": docente.id, "nombre": docente.nombre},
                "periodo": {"id": periodo.id, "numero": periodo.numero, "descripcion": periodo.descripcion}
            }
        }), 201
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
        estudiante = Estudiante[data["estudiante_id"]]
        periodo = Periodo[data["periodo_id"]]
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
    except ObjectNotFound:
        rollback()
        return jsonify({"error": "Estudiante o Periodo no encontrado"}), 404
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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
@app.route("/inscripcionmateria", methods=["POST"])
@db_session
def agregar_inscripcion_materia():
    InscripcionMateria = dborm.db.InscripcionMateria
    Inscripcion = dborm.db.Inscripcion
    GrupoMateria = dborm.db.GrupoMateria
    data = request.json
    try:
        inscripcion = Inscripcion[data["inscripcion_id"]]
        grupo = GrupoMateria[data["grupo_id"]]
        im = InscripcionMateria(inscripcion=inscripcion, grupo=grupo)
        commit()
        return jsonify({
            "msg": "InscripcionMateria agregada",
            "inscripcionmateria": {
                "id": im.id,
                "inscripcion": {"id": inscripcion.id, "estudiante": inscripcion.estudiante.nombre},
                "grupo": {"id": grupo.id, "nombre": grupo.nombre}
            }
        }), 201
    except ObjectNotFound:
        rollback()
        return jsonify({"error": "Inscripcion o GrupoMateria no encontrado"}), 404
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
@token_required
@db_session
def agregar_inscripcion_materiaasync():
    data = request.json
    try:
        dto = InscripcionMateriaDTO(
            inscripcion_id=data["inscripcion_id"],
            grupo_id=data["grupo_id"]
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

@app.route("/inscripcionmateriaasync", methods=["PUT"])
@token_required
@db_session
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
@token_required
@db_session
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
            inscripcion_materia=im
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
@token_required
@db_session
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
@token_required
@db_session
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
@token_required
@db_session
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

    # Filtrar solo las notas del estudiante
    notas = [ 
        {
            "id": n.id,
            "valor": n.nota,
            "grupo": n.inscripcion_materia.grupo.grupo,
            "materia": n.inscripcion_materia.grupo.materia.nombre,
            "docente": n.inscripcion_materia.grupo.docente.nombre
        }
        for n in Nota.select(lambda n: n.inscripcion_materia.inscripcion.estudiante.registro == estudiante_registro)
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
    try:
        estudiante = Estudiante.get(registro=estudiante_registro)
        if not estudiante:
            return jsonify({"error": "Estudiante no encontrado"}), 404
        materias = {
            m.grupo.materia.id: m.grupo.materia.to_dict()  #Usa el ID de la materia como clave (para evitar duplicados) Usa el diccionario de la materia como valor (to_dict())
            for insc in estudiante.inscripciones
            for m in insc.materias # aqui materias es = InscripcionMateria
        }
        return jsonify( materias ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
        

    app.run(host="0.0.0.0", port=8000,use_reloader=False)
