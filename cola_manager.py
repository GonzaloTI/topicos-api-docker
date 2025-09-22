from __future__ import annotations
from dataclasses import dataclass
from threading import RLock, Condition
from typing import List, Optional, Tuple
import time
import redis

from cola2 import Cola2
from tarea import Metodo, Prioridad

@dataclass
class RedisParams:
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0

@dataclass
class ColaSlot:
    cola: Cola2
    ocupada: bool = False

class ColaManager:
    """
    Crea y administra internamente múltiples colas Cola2.
    - create_queue(nombre)
    - create_many(n, prefix)
    - delete_queue(nombre, drop_data=False, drop_status=False)
    - list_queues()
    - agregar_tarea(metodo, prioridad, payload, timeout=2.0, strategy='first_free')
    """
    def __init__(self, params: RedisParams):
        self._p = params
        self._slots: List[ColaSlot] = []
        self._lock = RLock()
        self._cv = Condition(self._lock)
        self._r = redis.Redis(
            host=params.host, port=params.port,
            password=params.password, db=params.db,
            decode_responses=True
        )

    # ---------- creación / eliminación ----------
    def create_queue(self, nombre: str) -> Cola2:
        if not nombre:
            raise ValueError("Nombre de cola inválido")
        with self._lock:
            for s in self._slots:
                if s.cola.nombre == nombre:
                    return s.cola
            cola = Cola2(
                redis_host=self._p.host,
                redis_port=self._p.port,
                redis_password=self._p.password,
                redis_db=self._p.db,
                nombre=nombre,
            )
            self._slots.append(ColaSlot(cola=cola))
            self._cv.notify_all()
            return cola

    def create_many(self, n: int, prefix: str = "cola") -> List[str]:
        names = []
        with self._lock:
            for i in range(1, max(1, n) + 1):
                name = f"{prefix}_{i}"
                if not any(s.cola.nombre == name for s in self._slots):
                    cola = Cola2(
                        redis_host=self._p.host,
                        redis_port=self._p.port,
                        redis_password=self._p.password,
                        redis_db=self._p.db,
                        nombre=name,
                    )
                    self._slots.append(ColaSlot(cola=cola))
                    names.append(name)
            if names:
                self._cv.notify_all()
        return names

    def delete_queue(self, nombre: str, drop_data: bool = False, drop_status: bool = False) -> bool:
        with self._lock:
            idx = next((i for i, s in enumerate(self._slots) if s.cola.nombre == nombre), None)
            if idx is None or self._slots[idx].ocupada:
                return False
            self._slots.pop(idx)
            self._cv.notify_all()
        keys = []
        if drop_data:   keys.append(nombre)
        if drop_status: keys.append(f"{nombre}:status")
        if keys: self._r.delete(*keys)
        return True

    def list_queues(self) -> List[str]:
        with self._lock:
            return [s.cola.nombre for s in self._slots]

    # ---------- selección de cola ----------
    def _pick_first_free(self) -> Optional[ColaSlot]:
        for s in self._slots:
            if not s.ocupada:
                return s
        return None

    def _pick_least_backlog(self) -> Optional[ColaSlot]:
        libres = [s for s in self._slots if not s.ocupada]
        if not libres:
            return None
        # menor número de pendientes en el ZSET
        return min(libres, key=lambda s: s.cola.count_pendientes())

    # ---------- API principal: asignar y encolar ----------
    def agregar_tarea(
        self,
        metodo: Metodo,
        prioridad: Prioridad,
        payload=None,
        timeout: float = 2.0,
        strategy: str = "first_free",  # "first_free" | "least_backlog"
    ) -> Tuple[str, str]:
        """
        Elige una cola 'libre', la marca ocupada, encola la tarea y libera.
        Devuelve (nombre_cola, id_tarea).
        Lanza RuntimeError si no hay colas o si se agota el timeout.
        """
        chooser = self._pick_first_free if strategy == "first_free" else self._pick_least_backlog
        end = time.time() + (timeout if timeout is not None else 0)

        with self._lock:
            while True:
                if not self._slots:
                    raise RuntimeError("No hay colas creadas en el manager")
                slot = chooser()
                if slot:
                    slot.ocupada = True
                    cola = slot.cola
                    break
                if timeout is None:
                    self._cv.wait(timeout=0.25)
                else:
                    rem = end - time.time()
                    if rem <= 0:
                        raise RuntimeError("No hay colas libres (timeout)")
                    self._cv.wait(timeout=min(0.25, rem))

        # fuera del lock: realizar el encolado real
        try:
            tarea_id = cola.agregar(metodo=metodo, prioridad=prioridad, payload=payload)
            return cola.nombre, tarea_id
        finally:
            with self._lock:
                slot.ocupada = False
                self._cv.notify()
