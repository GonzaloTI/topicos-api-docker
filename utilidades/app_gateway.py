import json
from flask import Flask, Response, render_template, request, jsonify, url_for
import datetime
from functools import wraps
import jwt
import os, requests

app = Flask(__name__)

SECRET_KEY = "mi_clave_secreta"

MICROSERVICIO_1 = os.getenv("MICROSERVICIO_1", "http://localhost:8100")
TIMEOUT_MS1 = float(os.getenv("MICROSERVICIO_1_TIMEOUT", "20.0"))

# Solo IP:PUERTO (los paths se conservan tal cual en el backend)
MICROSERVICIO_2REDIS_INSCRIPCION = os.getenv("MICROSERVICIO_2REDIS", "http://localhost:8700")

TIMEOUT_MS2    = float(os.getenv("MICROSERVICIO_2_TIMEOUT", "20.0"))


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

# ========= Helper de proxy =========
def _proxy_request(base_url: str, path: str, timeout: float | None = None):
    """
    Reenvía la petición actual a base_url/path
    - Conserva método, querystring, body/json, files y headers (filtrando hop-by-hop)
    - Usa timeout específico si se provee, sino no-bloca por defecto de requests
    """
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    excluded = {"host", "content-length", "transfer-encoding", "connection"}
    fwd_headers = {k: v for k, v in request.headers if k.lower() not in excluded}

    files = None
    data_bytes = None
    json_data = None

    if request.files:
        files = {k: (f.filename, f.stream, f.mimetype) for k, f in request.files.items()}
        data_bytes = request.form.to_dict(flat=True)
    else:
        if request.is_json:
            json_data = request.get_json(silent=True)
        else:
            data_bytes = request.get_data()

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            headers=fwd_headers,
            data=data_bytes,
            json=json_data,
            files=files,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return Response('{"error":"timeout en backend"}', status=504, mimetype="application/json")
    except requests.exceptions.ConnectionError:
        return Response('{"error":"backend no disponible"}', status=502, mimetype="application/json")
    except Exception as e:
        return Response(f'{{"error":"proxy error","detalle":"{str(e)}"}}', status=500, mimetype="application/json")

    resp_excluded = {"content-encoding", "transfer-encoding", "connection"}
    out_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in resp_excluded]
    return Response(resp.content, status=resp.status_code, headers=out_headers)



def unir_proxyrequest(p1, p2, etiqueta1="ms2", etiqueta2="ms1"):
    """Une dos Responses de Flask en un solo JSON con estados y cuerpos parseados.
       - p1 y p2: objetos flask.Response devueltos por _proxy_request
       - etiqueta1/etiqueta2: claves para identificar cada microservicio en la salida
       Retorna: (json_response, http_status)
    """
    import json as _json

    def _extraer(resp):
        if resp is None:
            return {"status": 599, "ok": False, "body": None, "raw": None}
        try:
            status = getattr(resp, "status_code", 500)
        except Exception:
            status = 500
        try:
            raw = resp.get_data(as_text=True)
        except Exception:
            raw = ""
        # intentar parsear JSON; si no es JSON, devolver texto
        try:
            body = _json.loads(raw) if raw else None
        except Exception:
            body = raw if raw else None
        ok = 200 <= int(status) < 300
        return {"status": status, "ok": ok, "body": body, "raw": raw}

    r1 = _extraer(p1)
    r2 = _extraer(p2)

    combinado = {
        etiqueta1: {"status": r1["status"], "ok": r1["ok"], "body": r1["body"]},
        etiqueta2: {"status": r2["status"], "ok": r2["ok"], "body": r2["body"]},
    }

    # Mensaje y status HTTP global
    ok1, ok2 = r1["ok"], r2["ok"]
    if ok1 and ok2:
        combinado["mensaje"] = "Operación exitosa en ambos microservicios."
        http_status = 200
    elif ok1 != ok2:
        combinado["mensaje"] = "Uno de los microservicios falló."
        http_status = 207  # Multi-Status: éxito parcial
    else:
        combinado["mensaje"] = "Ambos microservicios fallaron."
        # devolver el peor status (el mayor; típicamente 5xx)
        http_status = max(int(r1["status"]), int(r2["status"]))

    return jsonify(combinado), http_status




# ========= Rutas del Gateway =========
# Ejemplo: /statusall -> se reenvía a MICROSERVICIO_2REDIS_INSCRIPCION /statusall
@app.route("/statusall", methods=["GET"])
# @token_required  # <-- activa esto si quieres que el gateway valide JWT
def gw_statusall():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/statusall")

    
# ========= Rutas al microservicio duales ,las de colas  =========
# =========================
@app.route("/limpiarbd", methods=["GET"])
# @token_required
def gw_colas_add_workersdual():
    p1 = _proxy_request(MICROSERVICIO_1, "/limpiarbd", TIMEOUT_MS1)
    p2 =  _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/limpiarbd", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)  # estado de ambas, “uno encima del otro”

# =========================
# ---------- Workers: add / remove ----------
@app.route("/colas/<nombre>/workers/add/<int:n>", methods=["POST"])
# @token_required
def gw_dual_colas_add_workers(nombre, n):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}/workers/add/{n}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}/workers/add/{n}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

@app.route("/colas/<nombre>/workers/remove/<int:n>", methods=["POST"])
# @token_required
def gw_dual_colas_remove_workers(nombre, n):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}/workers/remove/{n}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}/workers/remove/{n}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)


# ---------- Control global: pause / resume / stop ----------
@app.route("/colas/pause", methods=["POST"])
# @token_required
def gw_dual_colas_pause():
    p1 = _proxy_request(MICROSERVICIO_1, "/colas/pause", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/pause", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

@app.route("/colas/resume", methods=["POST"])
# @token_required
def gw_dual_colas_resume():
    p1 = _proxy_request(MICROSERVICIO_1, "/colas/resume", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/resume", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

@app.route("/colas/stop", methods=["POST"])
# @token_required
def gw_dual_colas_stop():
    p1 = _proxy_request(MICROSERVICIO_1, "/colas/stop", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/stop", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)


# ---------- Listar/crear colas (GET/POST) ----------
@app.route("/colas", methods=["GET", "POST"])
# @token_required
def gw_dual_colas():
    p1 = _proxy_request(MICROSERVICIO_1, "/colas", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

# ---------- Eliminar cola por nombre ----------
@app.route("/colas/<nombre>", methods=["DELETE"])
# @token_required
def gw_dual_colas_eliminar(nombre):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)


# ---------- Status de tarea por id (en ambos) ----------
@app.route("/status/<id_tarea>", methods=["GET"])
# @token_required
def gw_dual_status_tarea(id_tarea):
    p1 = _proxy_request(MICROSERVICIO_1, f"/status/{id_tarea}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/status/{id_tarea}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)


# ---------- Resultados por cola + id_tarea ----------
@app.route("/colas/<nombre_cola>/resultados/<id_tarea>", methods=["GET"])
# @token_required
def gw_dual_resultado_por_id(nombre_cola, id_tarea):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

# (Opcionales si te sirven con estados enriquecidos del MS2)
@app.route("/colas/<nombre_cola>/resultados_estados/<id_tarea>", methods=["GET"])
def gw_dual_resultado_por_id_estados(nombre_cola, id_tarea):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados_estados/{id_tarea}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)

@app.route("/colas/<nombre_cola>/resultados_estados2/<id_tarea>", methods=["GET"])
def gw_dual_resultado_por_id_estados2(nombre_cola, id_tarea):
    p1 = _proxy_request(MICROSERVICIO_1, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS1)
    p2 = _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados_estados2/{id_tarea}", TIMEOUT_MS2)
    return unir_proxyrequest(p1, p2)


# ========= Rutas al microservicio 1 (MICROSERVICIO_1) =========
# =========================
# MICROSERVICIO_1 (Estudiantes y todo lo demás)
# =========================

# Health
@app.route("/health_estudent", methods=["GET"])
# @token_required
def gw_health():
    return _proxy_request(MICROSERVICIO_1, "/health", TIMEOUT_MS1)

@app.route("/health_inscripcion", methods=["GET"])
# @token_required
def gw_healthINS():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/health", TIMEOUT_MS1)


# ---------- Cola / Workers / Admin ----------
@app.route("/statusall_ms1", methods=["GET"])
# @token_required
def gw_statusall_ms1():
    return _proxy_request(MICROSERVICIO_1, "/statusall", TIMEOUT_MS1)



@app.route("/limpiarbdMS1", methods=["GET"])
# @token_required
def gw_limpiarbd():
    return _proxy_request(MICROSERVICIO_1, "/limpiarbd", TIMEOUT_MS1)

@app.route("/cola/resumenMS1", methods=["GET"])
# @token_required
def gw_cola_resumen():
    return _proxy_request(MICROSERVICIO_1, "/cola/resumen", TIMEOUT_MS1)

@app.route("/cola/resumen2MS1", methods=["GET"])
# @token_required
def gw_cola_resumen2():
    return _proxy_request(MICROSERVICIO_1, "/cola/resumen2", TIMEOUT_MS1)

@app.route("/ui/colaMS1", methods=["GET"])
def gw_ui_cola():
    return _proxy_request(MICROSERVICIO_1, "/ui/cola", TIMEOUT_MS1)

@app.route("/ui/colapaginateMS1", methods=["GET"])
def gw_ui_colapaginate():
    return _proxy_request(MICROSERVICIO_1, "/ui/colapaginate", TIMEOUT_MS1)

@app.route("/colasMS1/<nombre_cola>/resumen2", methods=["GET"])
# @token_required
def gw_cola_resumen2_por_cola(nombre_cola):
    return _proxy_request(MICROSERVICIO_1, f"/colas/{nombre_cola}/resumen2", TIMEOUT_MS1)

@app.route("/ui/colapaginateMS1/<nombre_cola>", methods=["GET"])
def gw_ui_colapaginate_por_cola(nombre_cola):
    return _proxy_request(MICROSERVICIO_1, f"/ui/colapaginate/{nombre_cola}", TIMEOUT_MS1)

@app.route("/colasMS1/<nombre>/workers/add/<int:n>", methods=["POST"])
# @token_required
def gw_colas_add_workers(nombre, n):
    return _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}/workers/add/{n}", TIMEOUT_MS1)

@app.route("/colasMS1/<nombre>/workers/remove/<int:n>", methods=["POST"])
# @token_required
def gw_colas_remove_workers(nombre, n):
    return _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}/workers/remove/{n}", TIMEOUT_MS1)

@app.route("/statusMS1/<id_tarea>", methods=["GET"])
# @token_required
def gw_status_tarea(id_tarea):
    return _proxy_request(MICROSERVICIO_1, f"/status/{id_tarea}", TIMEOUT_MS1)

@app.route("/colasMS1", methods=["GET", "POST"])
# @token_required
def gw_colas():
    return _proxy_request(MICROSERVICIO_1, "/colas", TIMEOUT_MS1)

@app.route("/colasMS1/<nombre>", methods=["DELETE"])
# @token_required
def gw_colas_eliminar(nombre):
    return _proxy_request(MICROSERVICIO_1, f"/colas/{nombre}", TIMEOUT_MS1)

@app.route("/colasMS1/pause", methods=["POST"])
# @token_required
def gw_colas_pause():
    return _proxy_request(MICROSERVICIO_1, "/colas/pause", TIMEOUT_MS1)

@app.route("/colasMS1/resume", methods=["POST"])
# @token_required
def gw_colas_resume():
    return _proxy_request(MICROSERVICIO_1, "/colas/resume", TIMEOUT_MS1)

@app.route("/colasMS1/stop", methods=["POST"])
# @token_required
def gw_colas_stop():
    return _proxy_request(MICROSERVICIO_1, "/colas/stop", TIMEOUT_MS1)

@app.route("/logs", methods=["GET"])
# @token_required
def gw_logs():
    return _proxy_request(MICROSERVICIO_1, "/logs", TIMEOUT_MS1)

@app.route("/colasMS1/<nombre_cola>/resultados/<id_tarea>", methods=["GET"])
# @token_required
def gw_resultado_por_id(nombre_cola, id_tarea):
    return _proxy_request(MICROSERVICIO_1, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS1)


# ---------- Auth ----------
@app.route("/login", methods=["POST"])
def gw_login():
    return _proxy_request(MICROSERVICIO_1, "/login", TIMEOUT_MS1)

# ---------- Carreras ----------
@app.route("/carreras", methods=["GET", "POST"])
# @token_required
def gw_carreras():
    return _proxy_request(MICROSERVICIO_1, "/carreras", TIMEOUT_MS1)

@app.route("/carrerasasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_carreras_async():
    return _proxy_request(MICROSERVICIO_1, "/carrerasasync", TIMEOUT_MS1)

# ---------- Planes de Estudio ----------
@app.route("/planes", methods=["GET", "POST"])
# @token_required
def gw_planes():
    return _proxy_request(MICROSERVICIO_1, "/planes", TIMEOUT_MS1)

@app.route("/planesasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_planes_async():
    return _proxy_request(MICROSERVICIO_1, "/planesasync", TIMEOUT_MS1)

# ---------- Materias ----------
@app.route("/materias", methods=["GET", "POST"])
# @token_required
def gw_materias():
    return _proxy_request(MICROSERVICIO_1, "/materias", TIMEOUT_MS1)

@app.route("/materiasasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_materias_async():
    return _proxy_request(MICROSERVICIO_1, "/materiasasync", TIMEOUT_MS1)

# ---------- Prerrequisitos ----------
@app.route("/prerrequisitos", methods=["GET", "POST"])
# @token_required
def gw_prerrequisitos():
    return _proxy_request(MICROSERVICIO_1, "/prerrequisitos", TIMEOUT_MS1)

@app.route("/prerrequisitosasync", methods=["GET", "POST"])
# @token_required
def gw_prerrequisitos_async():
    return _proxy_request(MICROSERVICIO_1, "/prerrequisitosasync", TIMEOUT_MS1)

# ---------- Niveles ----------
@app.route("/niveles", methods=["GET", "POST"])
# @token_required
def gw_niveles():
    return _proxy_request(MICROSERVICIO_1, "/niveles", TIMEOUT_MS1)

@app.route("/nivelesasync", methods=["GET", "POST"])
# @token_required
def gw_niveles_async():
    return _proxy_request(MICROSERVICIO_1, "/nivelesasync", TIMEOUT_MS1)

# ---------- Docentes ----------
@app.route("/docentes", methods=["GET", "POST"])
# @token_required
def gw_docentes():
    return _proxy_request(MICROSERVICIO_1, "/docentes", TIMEOUT_MS1)

@app.route("/docentesasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_docentes_async():
    return _proxy_request(MICROSERVICIO_1, "/docentesasync", TIMEOUT_MS1)

# ---------- Módulos ----------
@app.route("/modulos", methods=["GET", "POST"])
# @token_required
def gw_modulos():
    return _proxy_request(MICROSERVICIO_1, "/modulos", TIMEOUT_MS1)

@app.route("/modulosasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_modulos_async():
    return _proxy_request(MICROSERVICIO_1, "/modulosasync", TIMEOUT_MS1)

# ---------- Aulas ----------
@app.route("/aulas", methods=["GET", "POST"])
# @token_required
def gw_aulas():
    return _proxy_request(MICROSERVICIO_1, "/aulas", TIMEOUT_MS1)

@app.route("/aulasasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_aulas_async():
    return _proxy_request(MICROSERVICIO_1, "/aulasasync", TIMEOUT_MS1)

# ---------- Horarios ----------
@app.route("/horarios", methods=["GET", "POST"])
# @token_required
def gw_horarios():
    return _proxy_request(MICROSERVICIO_1, "/horarios", TIMEOUT_MS1)

@app.route("/horariosasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_horarios_async():
    return _proxy_request(MICROSERVICIO_1, "/horariosasync", TIMEOUT_MS1)

# ---------- Gestiones ----------
@app.route("/gestiones", methods=["GET", "POST"])
# @token_required
def gw_gestiones():
    return _proxy_request(MICROSERVICIO_1, "/gestiones", TIMEOUT_MS1)

# ---------- TipoPeriodo ----------
@app.route("/tipoperiodos", methods=["GET", "POST"])
# @token_required
def gw_tipoperiodos():
    return _proxy_request(MICROSERVICIO_1, "/tipoperiodos", TIMEOUT_MS1)

# ---------- Periodos ----------
@app.route("/periodos", methods=["GET", "POST"])
# @token_required
def gw_periodos():
    return _proxy_request(MICROSERVICIO_1, "/periodos", TIMEOUT_MS1)


# ---------- Estudiantes (sync + async) ----------
@app.route("/estudiantes", methods=["GET", "POST"])
# @token_required
def gw_estudiantes():
    return _proxy_request(MICROSERVICIO_1, "/estudiantes", TIMEOUT_MS1)

# (Opcional: solo si mantienes rutas por ID en tu MS1; si no existen, responderán 404 del backend)
@app.route("/estudiantes/<int:id>", methods=["GET", "PUT"])
# @token_required
def gw_estudiantes_id(id):
    return _proxy_request(MICROSERVICIO_1, f"/estudiantes/{id}", TIMEOUT_MS1)

@app.route("/estudiantesasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_estudiantes_async():
    return _proxy_request(MICROSERVICIO_1, "/estudiantesasync", TIMEOUT_MS1)


# ---------- GrupoMateria ----------
@app.route("/gruposmateria", methods=["GET", "POST"])
# @token_required
def gw_gruposmateria():
    return _proxy_request(MICROSERVICIO_1, "/gruposmateria", TIMEOUT_MS1)

@app.route("/gruposmateriaasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_gruposmateria_async():
    return _proxy_request(MICROSERVICIO_1, "/gruposmateriaasync", TIMEOUT_MS1)

# ---------- Notas ----------
@app.route("/notas", methods=["GET", "POST"])
# @token_required
def gw_notas():
    return _proxy_request(MICROSERVICIO_1, "/notas", TIMEOUT_MS1)

@app.route("/notasasync", methods=["GET", "POST", "PUT"])
# @token_required
def gw_notas_async():
    return _proxy_request(MICROSERVICIO_1, "/notasasync", TIMEOUT_MS1)

@app.route("/notasxregistro", methods=["GET"])
# @token_required
def gw_notas_x_registro():
    return _proxy_request(MICROSERVICIO_1, "/notasxregistro", TIMEOUT_MS1)

@app.route("/materiasxregistro", methods=["GET"])
# @token_required
def gw_materias_x_registro():
    return _proxy_request(MICROSERVICIO_1, "/materiasxregistro", TIMEOUT_MS1)


# =========================
# MICROSERVICIO_2REDIS_INSCRIPCION — TODAS LAS RUTAS
# (Con sufijo MS2 solo cuando hay conflicto con MS1)
# =========================

# ----- Admin/colas (conflicto con MS1 => sufijo MS2) -----
@app.route("/limpiarbdMS2", methods=["GET"])
def ms2_limpiarbd():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/limpiarbd", TIMEOUT_MS2)

@app.route("/cola/resumenMS2", methods=["GET"])
def ms2_cola_resumen():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/cola/resumen", TIMEOUT_MS2)

@app.route("/cola/resumen2MS2", methods=["GET"])
def ms2_cola_resumen2():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/cola/resumen2", TIMEOUT_MS2)

@app.route("/ui/colaMS2", methods=["GET"])
def ms2_ui_cola():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/ui/cola", TIMEOUT_MS2)

@app.route("/ui/colapaginateMS2", methods=["GET"])
def ms2_ui_colapaginate():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/ui/colapaginate", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre_cola>/resumen2", methods=["GET"])
def ms2_cola_resumen2_por_cola(nombre_cola):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resumen2", TIMEOUT_MS2)

@app.route("/ui/colapaginateMS2/<nombre_cola>", methods=["GET"])
def ms2_ui_colapaginate_por_cola(nombre_cola):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/ui/colapaginate/{nombre_cola}", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre>/workers/add/<int:n>", methods=["POST"])
def ms2_colas_add_workers(nombre, n):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}/workers/add/{n}", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre>/workers/remove/<int:n>", methods=["POST"])
def ms2_colas_remove_workers(nombre, n):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}/workers/remove/{n}", TIMEOUT_MS2)

@app.route("/statusMS2/<id_tarea>", methods=["GET"])
def ms2_status_tarea(id_tarea):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/status/{id_tarea}", TIMEOUT_MS2)

@app.route("/colasMS2", methods=["GET", "POST"])
def ms2_colas():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre>", methods=["DELETE"])
def ms2_colas_eliminar(nombre):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre}", TIMEOUT_MS2)

@app.route("/colasMS2/pause", methods=["POST"])
def ms2_colas_pause():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/pause", TIMEOUT_MS2)

@app.route("/colasMS2/resume", methods=["POST"])
def ms2_colas_resume():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/resume", TIMEOUT_MS2)

@app.route("/colasMS2/stop", methods=["POST"])
def ms2_colas_stop():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/colas/stop", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre_cola>/resultados/<id_tarea>", methods=["GET"])
def ms2_resultado_por_id(nombre_cola, id_tarea):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados/{id_tarea}", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre_cola>/resultados_estados/<id_tarea>", methods=["GET"])
def ms2_resultado_por_id_estados(nombre_cola, id_tarea):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados_estados/{id_tarea}", TIMEOUT_MS2)

@app.route("/colasMS2/<nombre_cola>/resultados_estados2/<id_tarea>", methods=["GET"])
def ms2_resultado_por_id_estados2(nombre_cola, id_tarea):
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, f"/colas/{nombre_cola}/resultados_estados2/{id_tarea}", TIMEOUT_MS2)

@app.route("/logsMS2", methods=["GET"])
def ms2_logs():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/logs", TIMEOUT_MS2)

# ----- DB seed/init (no existen en MS1 => sin sufijo) -----
@app.route("/initdb", methods=["POST"])
def ms2_initdb():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/initdb", TIMEOUT_MS2)

@app.route("/Seeders", methods=["POST"])
def ms2_seeders():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/Seeders", TIMEOUT_MS2)

# ----- Auth (conflicto con MS1 => sufijo MS2) -----
@app.route("/loginMS2", methods=["POST"])
def ms2_login():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/login", TIMEOUT_MS2)

# ----- Worker manager (no existen en MS1 => sin sufijo) -----
@app.route("/stop", methods=["POST"])
def ms2_stop_workers():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/stop", TIMEOUT_MS2)

@app.route("/restart", methods=["POST"])
def ms2_restart_workers():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/restart", TIMEOUT_MS2)

@app.route("/pause", methods=["POST"])
def ms2_pause_workers():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/pause", TIMEOUT_MS2)

@app.route("/resume", methods=["POST"])
def ms2_resume_workers():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/resume", TIMEOUT_MS2)

# ----- Inscripciones (no existen en MS1 => sin sufijo) -----
@app.route("/inscripciones", methods=["POST", "GET"])
def ms2_inscripciones():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripciones", TIMEOUT_MS2)

@app.route("/inscripcionesasync", methods=["GET", "POST", "PUT"])
def ms2_inscripciones_async():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripcionesasync", TIMEOUT_MS2)

# ----- InscripcionMateria (no existen en MS1 => sin sufijo) -----
@app.route("/inscripcionmaterialist", methods=["POST"])
def ms2_inscripcionmaterialist():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripcionmaterialist", TIMEOUT_MS2)

@app.route("/inscripcionmaterialistasync", methods=["POST"])
def ms2_inscripcionmaterialistasync():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripcionmaterialistasync", TIMEOUT_MS2)

@app.route("/inscripcionmateria", methods=["GET", "POST"])
def ms2_inscripcionmateria():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripcionmateria", TIMEOUT_MS2)

@app.route("/inscripcionmateriaasync", methods=["GET", "POST", "PUT"])
def ms2_inscripcionmateria_async():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/inscripcionmateriaasync", TIMEOUT_MS2)

# ----- Notas (conflicto con MS1 => sufijo MS2) -----
@app.route("/notasMS2", methods=["GET", "POST"])
def ms2_notas():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/notas", TIMEOUT_MS2)

@app.route("/notasasyncMS2", methods=["GET", "POST", "PUT"])
def ms2_notas_async():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/notasasync", TIMEOUT_MS2)

@app.route("/notasxregistroMS2", methods=["GET"])
def ms2_notas_x_registro():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/notasxregistro", TIMEOUT_MS2)

@app.route("/materiasxregistroMS2", methods=["GET"])
def ms2_materias_x_registro():
    return _proxy_request(MICROSERVICIO_2REDIS_INSCRIPCION, "/materiasxregistro", TIMEOUT_MS2)


if __name__ == "__main__":
        

    app.run(host="0.0.0.0", 
            port=8500,
            use_reloader=False,
            threaded=True,       # Permite múltiples hilos
            processes=1          # Un proceso con múltiples hilos
            )
