from __future__ import annotations
from dataclasses import dataclass
from threading import RLock, Condition
from typing import List, Optional, Tuple
import time
import redis

from cola2 import Cola2
from tarea import Metodo, Prioridad
from task_manager import WorkerManager

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
    worker_manager: Optional[WorkerManager] = None   # define un worquermanager para cada cola

class ColaManager:
    """
    Crea y administra internamente múltiples colas Cola2.
    - create_queue(nombre)
    - create_many(n, prefix)
    - delete_queue(nombre, drop_data=False, drop_status=False)
    - list_queues()
    - agregar_tarea(metodo, prioridad, payload, timeout=2.0, strategy='first_free')
    """
    def __init__(self, params: RedisParams,dborm,bzpop_timeout: int = 1):
        self._p = params
        self._slots: List[ColaSlot] = []
        self._lock = RLock()
        self._cv = Condition(self._lock)
        self._r = redis.Redis(
            host=params.host, port=params.port,
            password=params.password, db=params.db,
            decode_responses=True
        )
        self._rr_idx = 0  # <- puntero de round-robin
        self.bzpop_timeout=bzpop_timeout
        self.dborm = dborm

    # ---------- creación / eliminación ----------
    def create_queue(self, nombre: str,num_workers: int = 1) -> Cola2:
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
            wm = None
            if num_workers > 0 and self.dborm is not None:
                wm = WorkerManager(
                    cola2=cola,
                    dborm=self.dborm,
                    num_workers=num_workers,
                    bzpop_timeout=self.bzpop_timeout
                )
                wm.start()

            self._slots.append(ColaSlot(cola=cola, worker_manager=wm))
            self._cv.notify_all()
            return cola

    def create_many(self, n: int, prefix: str = "cola", num_workers: int = 1) -> List[str]:
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
                    wm = None
                    if num_workers > 0 and self.dborm is not None:
                        wm = WorkerManager(
                            cola2=cola,
                            dborm=self.dborm,
                            num_workers=num_workers,
                            bzpop_timeout=self.bzpop_timeout
                        )
                        wm.start()

                    self._slots.append(ColaSlot(cola=cola, worker_manager=wm))
                    names.append(name)
                
            if names:
                self._cv.notify_all()
        return names

    def delete_queue(self, nombre: str, drop_data: bool = False, drop_status: bool = False) -> dict:
        """
        Elimina una cola de forma segura:
        1) La retira del manager para que no sea elegible.
        2) Detiene todos sus workers.
        3) Borra keys de Redis opcionalmente.
        Devuelve un dict con detalles de lo realizado.
        """
        slot = None

        # 1) localizar y retirar el slot bajo lock (para que nadie la use)
        with self._lock:
            idx = next((i for i, s in enumerate(self._slots) if s.cola.nombre == nombre), None)
            if idx is None:
                return {"removed": False, "reason": "queue-not-found"}

            # si está marcada ocupada por una asignación en curso, no borramos
            if self._slots[idx].ocupada:
                return {"removed": False, "reason": "queue-busy"}

            # sacar el slot del manager para que no pueda ser elegido
            slot = self._slots.pop(idx)
            self._cv.notify_all()

        stopped = False
        # 2) detener los workers FUERA del lock
        if slot.worker_manager is not None:
            slot.worker_manager.stop_all()
            stopped = True

        # 3) borrar keys en Redis (opcional)
        deleted_keys = []
        if drop_data:
            deleted_keys.append(nombre)  # zset/list principal de tu Cola2 (ajusta si usas otro nombre)
        if drop_status:
            deleted_keys.append(f"{nombre}:status")

        if deleted_keys:
            # ignorar si no existen, Redis delete devuelve 0/1 sin lanzar error
            try:
                self._r.delete(*deleted_keys)
            except Exception:
                pass

        return {
            "removed": True,
            "queue": nombre,
            "workers_stopped": stopped,
            "deleted_keys": deleted_keys
        }


    def list_queues(self) -> List[dict]:
        resultado = []
        with self._lock:
            for s in self._slots:
                wm = s.worker_manager
                if wm and getattr(wm, "workers", None):
                    num_workers = len(wm.workers)

                    # Determinar estado global:
                    estados = []
                    for w in wm.workers:
                        if getattr(w, "_stop_event", None) and w._stop_event.is_set():
                            estados.append("stopped")
                        elif not w.is_alive():
                            estados.append("dead")
                        elif getattr(w, "_run_event", None) and not w._run_event.is_set():
                            estados.append("paused")
                        else:
                            estados.append("running")
                    # Si todos iguales → ese estado, si no → mixed
                    estado_global = estados[0] if estados and all(st == estados[0] for st in estados) else "mixed"

                else:
                    num_workers = 0
                    estado_global = "no-workers"

                resultado.append({
                    "cola": s.cola.nombre,
                    "workers_total": num_workers,
                    "estado": estado_global
                })
        return resultado

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
    def _pick_round_robin(self) -> Optional[ColaSlot]:
        """Devuelve el siguiente slot NO ocupado en orden circular."""
        n = len(self._slots)
        if n == 0:
            return None
        start = self._rr_idx
        for k in range(n):
            idx = (start + k) % n
            s = self._slots[idx]
            if not s.ocupada:
                # avanza el puntero para la próxima asignación
                self._rr_idx = (idx + 1) % n
                return s
        return None
    def agregar_tarea_Round_Robin(
        self,
        metodo: Metodo,
        prioridad: Prioridad,
        payload=None,
        timeout: float = 2.0
        ) -> Tuple[str, str]:
        chooser = self._pick_round_robin
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

        try:
            tarea_id = cola.agregar(metodo=metodo, prioridad=prioridad, payload=payload)
            return cola.nombre, tarea_id
        finally:
            with self._lock:
                slot.ocupada = False
                self._cv.notify()

    # --- helpers internos ---
    def _get_slot(self, nombre: str) -> Optional[ColaSlot]:
        with self._lock:
            for s in self._slots:
                if s.cola.nombre == nombre:
                    return s
        return None

    # --- controlar workers por cola o global ---
    def pause_workers(self, nombre: Optional[str] = None) -> int:
        """
        Pausa los workers. Si 'nombre' es None, pausa en todas las colas.
        Devuelve WorkerManager afectados.
        """
        afectados = 0
        with self._lock:
            slots = self._slots if nombre is None else [self._get_slot(nombre)]
            for s in slots:
                if s and s.worker_manager:
                    s.worker_manager.pause_all()
                    afectados += 1
        return afectados

    def resume_workers(self, nombre: Optional[str] = None) -> int:
        """
        Reanuda los workers. Si 'nombre' es None, reanuda en todas las colas.
        Devuelve WorkerManager afectados.
        """
        afectados = 0
        with self._lock:
            slots = self._slots if nombre is None else [self._get_slot(nombre)]
            for s in slots:
                if s and s.worker_manager:
                    s.worker_manager.resume_all()
                    afectados += 1
        return afectados

    def stop_workers(self, nombre: Optional[str] = None) -> int:
        """
        Detiene (stop + join) los workers. Si 'nombre' es None, detiene en todas las colas.
        Devuelve WorkerManager afectados.
        """
        afectados = 0
        targets = []
        with self._lock:
            slots = self._slots if nombre is None else [self._get_slot(nombre)]
            for s in slots:
                if s and s.worker_manager:
                    targets.append(s.worker_manager)

        for wm in targets:
            wm.stop_all()
            afectados += 1
        return afectados
