from typing import Optional
import uuid
import redis
import json
from enum import Enum
from queue import PriorityQueue
from tarea import Metodo,Tarea , Prioridad


class Cola:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_password="cola_tareas", redis_db=0, nombre="cola_tareas"):
        self.redis = redis.Redis(host=redis_host, port=redis_port, password=redis_password ,db=redis_db, decode_responses=True)
        self.nombre = nombre
        self.cola = PriorityQueue()
        self._status_hash = f"{self.nombre}:status" 
        self._cargar_tareas_desde_redis()

    def _cargar_tareas_desde_redis(self):
        """Carga las tareas almacenadas en Redis a la cola en memoria"""
        tareas = self.redis.zrange(self.nombre, 0, -1, withscores=True)
        for tarea_json, prioridad in tareas:
            data = json.loads(tarea_json)
            tarea = Tarea.from_dict(data)
            self.cola.put((tarea.prioridad, tarea))

    def agregar(self, metodo: Metodo, prioridad: Prioridad, payload=None):
        """Agrega tarea a memoria y Redis"""
        id_tarea=str(uuid.uuid4())  # id unico para cada tarea
        tarea = Tarea(
            id=str(id_tarea), 
            metodo=metodo,
            prioridad=prioridad,
            payload=payload
        )
        self.cola.put((tarea.prioridad, tarea))
        self.redis.zadd(self.nombre, {json.dumps(tarea.to_dict()): tarea.prioridad.value})
        return id_tarea

    def obtener(self):
        """Saca la tarea con mayor prioridad (de memoria y de Redis)"""
        if self.cola.empty():
            return None
        prioridad, tarea = self.cola.get()
        self.redis.zrem(self.nombre, json.dumps(tarea.to_dict()))
        return tarea
   
    def obtener_bloqueante(self, timeout: int = 1) -> Optional[Tarea]:
        """
        Saca la tarea de MAYOR prioridad de forma BLOQUEANTE desde Redis.
        BZPOPMAX YA elimina el elemento del ZSET en Redis.
        """
        # Devuelve (key, member, score) o None si expira el timeout
        res = self.redis.bzpopmax(self.nombre, timeout=timeout)
        if not res:
            return None

        _key, tarea_json, _score = res  # decode_responses=True => strings
        data = json.loads(tarea_json)
        return Tarea.from_dict(data)


    def mostrar(self):
        """Lista tareas en memoria"""
        return [t[1] for t in list(self.cola.queue)]

    def obtener_resultado2(self, tarea_id: str):
        """
        Recupera el resultado de una tarea completada desde Redis usando su ID.
        """
        tarea_data = self.redis.hget(self._status_hash, tarea_id)
        if tarea_data:
            tarea = Tarea.from_dict(json.loads(tarea_data))  # Convertimos los datos a un objeto Tarea
            return tarea.resultado  # Retorna el resultado de la tarea
        return None

    def obtener_resultado(self, tarea_id: str):
        """
        Recupera el resultado de una tarea completada desde Redis usando su ID.
        """
        tarea_data = self.redis.hget(self._status_hash, tarea_id)
        if tarea_data:
            print(f"Datos recuperados de Redis para tarea {tarea_id}: {tarea_data}")
            tarea = Tarea.from_dict(json.loads(tarea_data))  # Convertimos los datos a un objeto Tarea
            print(f"Resultado de tarea {tarea_id}: {tarea.resultado}")
            return tarea.resultado  # Retorna el resultado de la tarea
        return None
    def obtener_todas_las_tareas(self):
        """
        Recupera todas las tareas completadas desde Redis.
        """
        # Obtiene todos los registros del hash de status
        todas_las_tareas_data = self.redis.hgetall(self._status_hash)
        
        # Si no hay tareas, retorna una lista vacía
        if not todas_las_tareas_data:
            return []

        # Deserializa las tareas y retorna el resultado
        tareas = [Tarea.from_dict(json.loads(tarea_data)) for tarea_data in todas_las_tareas_data.values()]
        
        return tareas
    
    def vaciar_bd(self, asincrono: bool = True) -> None:
        """
        Vacía COMPLETAMENTE la base de datos seleccionada en este cliente Redis.
        (Equivalente a FLUSHDB en la DB = self.redis.connection_pool.connection_kwargs['db'])

        Parámetros:
        asincrono: si True, usa FLUSHDB ASYNC (no bloquea Redis).
        """
        # Vacía la BD en Redis
        try:
            if asincrono:
                # redis-py >= 3.0 soporta 'asynchronous'
                self.redis.flushdb(asynchronous=True)
            else:
                self.redis.flushdb()
        except TypeError:
            # Por si tu versión de redis-py no soporta 'asynchronous'
            self.redis.flushdb()

      
        try:
            while not self.cola.empty():
                self.cola.get_nowait()
        except Exception:
            pass
