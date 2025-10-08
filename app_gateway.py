import json
from flask import Flask, Response, render_template, request, jsonify, url_for
import datetime
from functools import wraps
import jwt
import os, requests

app = Flask(__name__)

SECRET_KEY = "mi_clave_secreta"

SVC_1 = os.getenv("SVC_1", "http://localhost:8100")
TIMEOUT = float(os.getenv("SVC_1_TIMEOUT", "10.0"))

# Solo IP:PUERTO (los paths se conservan tal cual en el backend)
SVC_REDIS = os.getenv("SVC_REDIS", "http://localhost:8700")
TIMEOUT    = float(os.getenv("SVC_TIMEOUT", "10.0"))




SVC_ = os.getenv("SVC_REDIS", "http://localhost:8500")
SVC_DOCENTE_MODULO = os.getenv("SVC_DOCENTE_MODULO", "http://localhost:8200")


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
def _proxy_request(base_url: str, path: str):
    """
    Reenvía la petición actual a base_url/path
    - Conserva método, querystring, body/json, headers (filtrando hop-by-hop)
    - Devuelve el status y body del backend
    """
    # Construir URL destino
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    # Filtrar headers hop-by-hop
    excluded = {"host", "content-length", "transfer-encoding", "connection"}
    fwd_headers = {k: v for k, v in request.headers if k.lower() not in excluded}

    # Payload según content-type / método
    files = None
    data_bytes = None
    json_data = None

    if request.files:
        files = {k: (f.filename, f.stream, f.mimetype) for k, f in request.files.items()}
        # Además de files, incluir campos de form
        data_bytes = request.form.to_dict(flat=True)
    else:
        if request.is_json:
            json_data = request.get_json(silent=True)
        else:
            # Para GET típicamente no se envía body; igual, si llega algo, lo reenviamos crudo
            data_bytes = request.get_data()

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            params=request.args,      # querystring
            headers=fwd_headers,
            data=data_bytes,
            json=json_data,
            files=files,
            timeout=TIMEOUT,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return Response('{"error":"timeout en backend"}', status=504, mimetype="application/json")
    except requests.exceptions.ConnectionError:
        return Response('{"error":"backend no disponible"}', status=502, mimetype="application/json")
    except Exception as e:
        return Response(f'{{"error":"proxy error","detalle":"{str(e)}"}}', status=500, mimetype="application/json")

    # No devolver headers hop-by-hop
    resp_excluded = {"content-encoding", "transfer-encoding", "connection"}
    out_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in resp_excluded]

    return Response(resp.content, status=resp.status_code, headers=out_headers)

# ========= Rutas del Gateway =========
# Ejemplo: /statusall -> se reenvía a SVC_REDIS /statusall
@app.route("/statusall", methods=["GET"])
# @token_required  # <-- activa esto si quieres que el gateway valide JWT
def gw_statusall():
    return _proxy_request(SVC_REDIS, "/statusall")

    

# ========= Rutas al microservicio 1 (SVC_1) =========

@app.route("/health_estudent", methods=["GET"])
# @token_required
def gw_health():
    return _proxy_request(SVC_1, "/health")


# ----- Estudiantes (sync) -----
@app.route("/estudiantes", methods=["GET"])
# @token_required
def gw_estudiantes_list():
    return _proxy_request(SVC_1, "/estudiantes")

@app.route("/estudiantes", methods=["POST"])
# @token_required
def gw_estudiantes_create():
    return _proxy_request(SVC_1, "/estudiantes")

@app.route("/estudiantes/<int:id>", methods=["GET"])
# @token_required
def gw_estudiantes_get(id):
    return _proxy_request(SVC_1, f"/estudiantes/{id}")

@app.route("/estudiantes/<int:id>", methods=["PUT"])
# @token_required
def gw_estudiantes_update(id):
    return _proxy_request(SVC_1, f"/estudiantes/{id}")


# ----- Estudiantes (async) -----
@app.route("/estudiantesasync", methods=["GET"])
# @token_required
def gw_estudiantes_list_async():
    return _proxy_request(SVC_1, "/estudiantesasync")

@app.route("/estudiantesasync", methods=["POST"])
# @token_required
def gw_estudiantes_create_async():
    return _proxy_request(SVC_1, "/estudiantesasync")

@app.route("/estudiantesasync", methods=["PUT"])
# @token_required
def gw_estudiantes_update_async():
    return _proxy_request(SVC_1, "/estudiantesasync")


#========================================================================


# Rutas DOCENTE
# =========================

# =========================
# RUTAS MICRO DOCENTE-MODULO
# =========================
@app.route("/materias", methods=["GET", "POST"])
@app.route("/materias/<path:path>", methods=["GET", "POST", "PUT"])
def gw_materias_proxy(path=""):
    return _proxy_request(SVC_DOCENTE_MODULO, f"/materias/{path}")

@app.route("/materiasasync", methods=["GET", "POST", "PUT"])
def gw_materias_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/materiasasync")

@app.route("/prerrequisitos", methods=["GET", "POST"])
def gw_prerrequisitos():
    return _proxy_request(SVC_DOCENTE_MODULO, "/prerrequisitos")

@app.route("/prerrequisitosasync", methods=["GET", "POST"])
def gw_prerrequisitos_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/prerrequisitosasync")

@app.route("/docentes", methods=["GET", "POST"])
def gw_docentes():
    return _proxy_request(SVC_DOCENTE_MODULO, "/docentes")

@app.route("/docentesasync", methods=["GET", "POST", "PUT"])
def gw_docentes_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/docentesasync")

@app.route("/modulos", methods=["GET", "POST"])
def gw_modulos():
    return _proxy_request(SVC_DOCENTE_MODULO, "/modulos")

@app.route("/modulosasync", methods=["GET", "POST", "PUT"])
def gw_modulos_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/modulosasync")

@app.route("/aulas", methods=["GET", "POST"])
def gw_aulas():
    return _proxy_request(SVC_DOCENTE_MODULO, "/aulas")

@app.route("/aulasasync", methods=["GET", "POST", "PUT"])
def gw_aulas_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/aulasasync")

@app.route("/gruposmateria", methods=["GET", "POST"])
def gw_gruposmateria():
    return _proxy_request(SVC_DOCENTE_MODULO, "/gruposmateria")

@app.route("/gruposmateriaasync", methods=["GET", "POST", "PUT"])
def gw_gruposmateria_async():
    return _proxy_request(SVC_DOCENTE_MODULO, "/gruposmateriaasync")

@app.route("/health_docente_modulo", methods=["GET"])
def gw_health_docente_modulo():
    return _proxy_request(SVC_DOCENTE_MODULO, "/health")



if __name__ == "__main__":
        

    app.run(host="0.0.0.0", 
            port=8500,
            use_reloader=False,
            threaded=True,       # Permite múltiples hilos
            processes=1          # Un proceso con múltiples hilos
            )
