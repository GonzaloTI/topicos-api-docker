# serial.py
import base64
import cloudpickle

def dumps_obj(obj) -> str:
    """Serializa un objeto Python (clase, tupla, etc.) a texto base64."""
    return base64.b64encode(cloudpickle.dumps(obj)).decode("utf-8")

def loads_obj(s: str):
    """Deserializa desde base64 a objeto Python."""
    return cloudpickle.loads(base64.b64decode(s.encode("utf-8")))
