import redis
import json
from dataclasses import dataclass, asdict


# ⚠️ Ajusta estos datos a tu servidor
REDIS_HOST = "18.191.219.182"     # ej: "54.210.xxx.xxx"
REDIS_PORT = 6379
REDIS_PASSWORD = "contraseniasegura2025"


@dataclass
class Usuario:
    id: str
    nombre: str
    edad: int

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(s: str) -> "Usuario":
        data = json.loads(s)
        return Usuario(**data)

def test_connection():
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=0,
            socket_connect_timeout=5  # segundos de espera
        )

        # Guardar un valor con expiración de 10 segundos
        #r.set("prueba", "Hola desde Python!")

        # Recuperar el valor
        value = r.get("prueba")
        
        u = Usuario(id="u:1", nombre="Melissa", edad=28)
        r.set(u.id, u.to_json(), ex=3600)  # TTL opcional

        # Leer
        raw = r.get("u:1")
        if raw:
            u2 = Usuario.from_json(raw.decode())
            print(u2)

        if value:
            print("✅ Conexión exitosa, Redis respondió:", value.decode("utf-8"))
        else:
            print("⚠️ No se pudo recuperar el valor")

    except Exception as e:
        print("❌ Error al conectar con Redis:", e)

if __name__ == "__main__":
    test_connection()
