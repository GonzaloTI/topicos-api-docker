from flask import Flask, request, jsonify
from pony.orm import Database, Required, Optional, PrimaryKey, db_session, Set , commit, rollback
from pony.orm.core import TransactionIntegrityError, ObjectNotFound
import datetime
from functools import wraps
import jwt
from ponyorm import DatabaseORM
from pila import PilaManager
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

pila_manager = PilaManager(dborm.db)


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
        d1 = Docente(registro="DOC-001", ci="1234567", nombre="Juan Pérez", telefono="76543210", otros="Docente de programación")
        d2 = Docente(registro="DOC-002", ci="7654321", nombre="María Gómez", telefono="71234567", otros="Docente de sistemas")


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
            registro="EST-001",
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
        Nota(nota=85.5, inscripcion_materia=im1)
        Nota(nota=72.0, inscripcion_materia=im2)
        Nota(nota=90.0, inscripcion_materia=im3)
        Nota(nota=68.5, inscripcion_materia=im4)
        
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
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
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

        # Guardar la tarea en la pila
        tarea = pila_manager
        tarea_pila =tarea.guardar_tarea(instruccion="POST", modelo="Carrera", datos=datos_serializados)
        
        #carrera = Carrera(
         #   nombre=data["nombre"],
          #  codigo=data["codigo"],
           # otros=data.get("otros", "")
        #)
        #commit()
        #return jsonify({"msg": "Carrera agregada con éxito", "id": carrera.id}), 201
        return jsonify({"msg": "Carrera agregada con éxito", "id": tarea_pila.id}), 201
    
    except Exception as e:
        rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/carreras", methods=["GET"])
@token_required
@db_session
def listar_carreras():
    tarea = pila_manager
    tarea.guardar_tarea(instruccion="GET", modelo="Carrera", datos='')
    Carrera = dborm.db.Carrera
    carreras = [{
        "id": c.id,
        "nombre": c.nombre,
        "codigo": c.codigo,
        "otros": c.otros
    } for c in Carrera.select()]
    return jsonify(carreras), 200



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

@app.route("/planes", methods=["GET"])
@token_required
@db_session
def listar_planes():
    PlanDeEstudio = dborm.db.PlanDeEstudio
    planes = [{
        "id": p.id,
        "nombre": p.nombre,
        "codigo": p.codigo,
        "fecha": str(p.fecha),
        "estado": p.estado,
        "carrera": p.carrera.nombre
    } for p in PlanDeEstudio.select()]
    return jsonify(planes), 200


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
    materias = [{
        "id": m.id,
        "sigla": m.sigla,
        "nombre": m.nombre,
        "creditos": m.creditos,
        "plan": m.plan.nombre,
        "nivel": m.nivel.nivel
    } for m in Materia.select()]
    return jsonify(materias), 200

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
    prereqs = [{
        "id": p.id,
        "materia": p.materia.nombre,
        "prerequisito": p.materia_requisito.nombre  # 🔑 corregido
    } for p in Prerequisito.select()]
    return jsonify(prereqs), 200

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
    niveles = [{"id": n.id, "nivel": n.nivel} for n in Nivel.select()]
    return jsonify(niveles), 200

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
    docentes = [{
        "id": d.id,
        "registro": d.registro,
        "ci": d.ci,
        "nombre": d.nombre,
        "telefono": d.telefono
    } for d in Docente.select()]
    return jsonify(docentes), 200


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
    estudiantes = [{"id": e.id, "nombre": e.nombre, "registro": e.registro} for e in Estudiante.select()]
    return jsonify(estudiantes), 200


# =========================
# Rutas para Modulo
# =========================

@app.route("/modulos", methods=["GET"])
@token_required
@db_session
def listar_modulos():
    Modulo = dborm.db.Modulo
    modulos = [
        {
            "id": m.id,
            "numero": m.numero,
            "nombre": m.nombre,
            "aulas": [{"id": a.id, "numero": a.numero, "nombre": a.nombre} for a in m.aulas]
        }
        for m in Modulo.select()
    ]
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


# =========================
# Rutas para Aula
# =========================

@app.route("/aulas", methods=["GET"])
@token_required
@db_session
def listar_aulas():
    Aula = dborm.db.Aula
    aulas = [
        {
            "id": a.id,
            "numero": a.numero,
            "nombre": a.nombre,
            "modulo": {"id": a.modulo.id, "numero": a.modulo.numero}
        }
        for a in Aula.select()
    ]
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
    horarios = [{
        "id": h.id,
        "dia": h.dia,
        "hora_inicio": str(h.hora_inicio),
        "hora_fin": str(h.hora_fin),
        "grupo": {
            "id": h.grupo.id,
            "nombre": h.grupo.nombre,
            "materia": h.grupo.materia.nombre,
            "docente": h.grupo.docente.nombre
        },
        "aula": {
            "id": h.aula.id,
            "numero": h.aula.numero,
            "modulo": h.aula.modulo.numero
        } if h.aula else None
    } for h in Horario.select()]
    return jsonify(horarios), 200


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
    gestiones = [{"id": g.id, "anio": g.anio} for g in Gestion.select()]
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
    tps = [{"id": tp.id, "nombre": tp.nombre} for tp in TipoPeriodo.select()]
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
    periodos = [{
        "id": p.id,
        "numero": p.numero,
        "descripcion": p.descripcion,
        "gestion": {"id": p.gestion.id, "anio": p.gestion.anio},
        "tipoperiodo": {"id": p.tipoperiodo.id, "nombre": p.tipoperiodo.nombre}
    } for p in Periodo.select()]
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
    grupos = [{
        "id": g.id,
        "grupo": g.grupo,
        "nombre": g.nombre,
        "estado": g.estado,
        "materia": {"id": g.materia.id, "nombre": g.materia.nombre},
        "docente": {"id": g.docente.id, "nombre": g.docente.nombre},
        "periodo": {"id": g.periodo.id, "numero": g.periodo.numero, "descripcion": g.periodo.descripcion}
    } for g in GrupoMateria.select()]
    return jsonify(grupos), 200




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
    inscripciones = [{
        "id": i.id,
        "fecha": str(i.fecha),
        "estudiante": {"id": i.estudiante.id, "nombre": i.estudiante.nombre},
        "periodo": {"id": i.periodo.id, "numero": i.periodo.numero}
    } for i in Inscripcion.select()]
    return jsonify(inscripciones), 200

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
    inscripciones_materia = [{
        "id": im.id,
        "inscripcion": {
            "id": im.inscripcion.id,
            "estudiante": im.inscripcion.estudiante.nombre
        },
        "grupo": {
            "id": im.grupo.id,
            "nombre": im.grupo.nombre,
            "materia": im.grupo.materia.nombre,
            "docente": im.grupo.docente.nombre
        }
    } for im in InscripcionMateria.select()]
    return jsonify(inscripciones_materia), 200





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

# =========================
# GET - Listar notas
# =========================
@app.route("/notas", methods=["GET"])
@db_session
def listar_notas():
    Nota = dborm.db.Nota
    notas = [{
        "id": n.id,
        "valor": n.nota,
        "inscripcion_materia": {
            "id": n.inscripcion_materia.id,
            "estudiante": n.inscripcion_materia.inscripcion.estudiante.nombre,
            "grupo": n.inscripcion_materia.grupo.nombre,
            "materia": n.inscripcion_materia.grupo.materia.nombre,
            "docente": n.inscripcion_materia.grupo.docente.nombre
        }
    } for n in Nota.select()]
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

        materias = [
            {
                "id": im.grupo.materia.id,
                "sigla": im.grupo.materia.sigla,
                "nombre": im.grupo.materia.nombre,
                "grupo": im.grupo.grupo,
                "docente": im.grupo.docente.nombre,
                "periodo": im.grupo.periodo.numero
            }
            for insc in estudiante.inscripciones
            for im in insc.materias
        ]

        return jsonify({
            "registro": estudiante_registro,
            "nombre": estudiante.nombre,
            "materias_inscritas": materias
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
