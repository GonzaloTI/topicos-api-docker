from typing import Dict, Optional, List, Tuple
import uuid
import redis
import json
from tarea import Metodo, Tarea, Prioridad


class Cola2:
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: str = "cola_tareas",
        redis_db: int = 0,
        nombre: str = "cola_tareas",
    ):
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True,
        )
        self.nombre = nombre                 # ZSET donde se encolan las tareas (member = JSON, score = prioridad)
        self._status_hash = f"{self.nombre}:status"   # HASH opcional para estados/resultado

    # ----------------- PRODUCTOR -----------------
    def agregar(self, metodo: Metodo, prioridad: Prioridad, payload=None) -> str:
        """
        Encola una tarea en el ZSET:
          - member: JSON de la tarea
          - score : prioridad.value (mayor => sale antes con ZPOPMAX/BZPOPMAX)
        """
        id_tarea = str(uuid.uuid4())
        tarea = Tarea(
            id=id_tarea,
            metodo=metodo,
            prioridad=prioridad,
            payload=payload
        )
        tarea_json = json.dumps(tarea.to_dict(), ensure_ascii=False)
        # mayor score = mayor prioridad
        self.redis.zadd(self.nombre, {tarea_json: prioridad.value})
        return id_tarea

    # ------------- CONSUMIDOR (NO BLOQUEANTE) -------------
    def obtener(self) -> Optional[Tarea]:
        """
        Saca la tarea de MAYOR prioridad de forma NO bloqueante.
        Usa ZPOPMAX (quita y devuelve el mayor score).
        """
        res = self.redis.zpopmax(self.nombre, count=1)
        if not res:
            return None
        tarea_json, _score = res[0]  # redis-py devuelve [(member, score)]
        data = json.loads(tarea_json)
        return Tarea.from_dict(data)

    # ------------- CONSUMIDOR (BLOQUEANTE) -------------
    def obtener_bloqueante(self, timeout: int = 1) -> Optional[Tarea]:
        """
        Saca la tarea de MAYOR prioridad de forma BLOQUEANTE.
        BZPOPMAX devuelve (key, member, score) y YA elimina del ZSET.
        """
        res = self.redis.bzpopmax(self.nombre, timeout=timeout)
        if not res:
            return None
        _key, tarea_json, _score = res
        data = json.loads(tarea_json)
        return Tarea.from_dict(data)

    # ----------------- UTILIDADES -----------------
    def mostrar(self) -> List[Tarea]:
        """
        Lista todas las tareas pendientes (ordenadas de mayor a menor prioridad).
        """
        members = self.redis.zrevrange(self.nombre, 0, -1)  # solo members (JSONs)
        return [Tarea.from_dict(json.loads(m)) for m in members]

    def obtener_resultado2(self, tarea_id: str):
        """
        Recupera el resultado de una tarea completada desde Redis usando su ID.
        (Mismo comportamiento que tu versión)
        """
        tarea_data = self.redis.hget(self._status_hash, tarea_id)
        if tarea_data:
            tarea = Tarea.from_dict(json.loads(tarea_data))
            return tarea.resultado
        return None

    def obtener_resultado(self, tarea_id: str):
        """
        Recupera el resultado de una tarea completada desde Redis usando su ID.
        (Incluye prints como en tu versión)
        """
        tarea_data = self.redis.hget(self._status_hash, tarea_id)
        if tarea_data:
            #print(f"Datos recuperados de Redis para tarea {tarea_id}: {tarea_data}")
            tarea = Tarea.from_dict(json.loads(tarea_data))
            print(f"Resultado de tarea {tarea_id}: {tarea.resultado}")
            return tarea.resultado
        return None

    def obtener_todas_las_tareas(self):
        """
        Recupera todas las tareas completadas desde Redis (HASH :status).
        """
        todas = self.redis.hgetall(self._status_hash)
        if not todas:
            return []
        return [Tarea.from_dict(json.loads(v)) for v in todas.values()]
    def pendientes(self, limit: int = 0, mayor_a_menor: bool = True) -> List[Dict]:
            """
            Lee el ZSET de pendientes SIN sacarlas de la cola.
            Devuelve lista de dicts: {..., estado: 'pendiente', prioridad: <score>}
            """
            start = 0
            end = (limit - 1) if limit and limit > 0 else -1
            fn = self.redis.zrevrange if mayor_a_menor else self.redis.zrange
            members = fn(self.nombre, start, end, withscores=True)

            out: List[Dict] = []
            for member, score in members:
                try:
                    t = json.loads(member)
                except Exception:
                    t = {"raw": member}
                t.setdefault("estado", "pendiente")
                t["prioridad"] = score
                out.append(t)
            return out
    def vaciar_bd(self, asincrono: bool = True) -> None:
        """
        Vacía COMPLETAMENTE la base de datos configurada para este cliente Redis.
        (FLUSHDB)
        """
        try:
            if asincrono:
                self.redis.flushdb(asynchronous=True)
            else:
                self.redis.flushdb()
        except TypeError:
            self.redis.flushdb()

    # ---- PENDIENTES (ZSET) ----
    def count_pendientes(self) -> int:
        return self.redis.zcard(self.nombre)

    def pendientes_paginado(self, page: int = 1, page_size: int = 500, mayor_a_menor: bool = True) -> List[Dict]:
        """
        Pagina el ZSET sin consumirlo.
        """
        page = max(1, page)
        start = (page - 1) * page_size
        end = start + page_size - 1
        fn = self.redis.zrevrange if mayor_a_menor else self.redis.zrange
        members = fn(self.nombre, start, end, withscores=True)

        out: List[Dict] = []
        for member, score in members:
            try:
                t = json.loads(member)
            except Exception:
                t = {"raw": member}
            t.setdefault("estado", "pendiente")
            t["prioridad"] = score
            out.append(t)
        return out

    # ---- REALIZADAS (HASH :status) ----
    def count_realizadas(self) -> int:
        return self.redis.hlen(self._status_hash)

    def realizadas_scan(self, cursor: int = 0, count: int = 500) -> Tuple[int, List[Dict]]:
        """
        Paginación eficiente por cursor sobre el HASH (orden no garantizado).
        Devuelve (cursor_siguiente, lista_de_tareas_dict).
        Usa esto cuando prefieres eficiencia antes que orden fijo.
        """
        cursor_next, chunk = self.redis.hscan(self._status_hash, cursor=cursor, count=count)
        items = []
        for _k, v in chunk.items():
            try:
                t = json.loads(v)
            except Exception:
                t = {"raw": v}
            items.append(t)
        return cursor_next, items
