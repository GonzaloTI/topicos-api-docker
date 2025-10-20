import logging
from logging.handlers import RotatingFileHandler
import os
import sys

class Logger:
    """
    Clase para configurar un logger que siempre guarda el archivo de log
    en el mismo directorio donde se encuentra este script (logger_setup.py).
    """
    _loggers = {}
    LOG_FILE_PATH = None # Variable para almacenar la ruta absoluta del log

    @staticmethod
    def get_logger(name="flask_app", log_file="app.log", level=logging.INFO):
        # Usamos la ruta del archivo de log como clave para asegurar una única instancia por archivo
        if Logger.LOG_FILE_PATH in Logger._loggers:
            return Logger._loggers[Logger.LOG_FILE_PATH]

        # --- INICIO DE LA CORRECCIÓN ---
        # 1. Determinar el directorio base (donde está este archivo)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Crear la ruta absoluta para el archivo de log
        log_file_path = os.path.join(base_dir, log_file)
        Logger.LOG_FILE_PATH = log_file_path # Guardamos la ruta para que sea accesible desde fuera
        # --- FIN DE LA CORRECCIÓN ---

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False # Evita que los logs se dupliquen en loggers padres

        if logger.hasHandlers():
            logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        
        # Usamos la ruta absoluta que calculamos
        handler = RotatingFileHandler(
            log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Opcional: Añadir handler para la consola para ver logs en la terminal
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        Logger._loggers[Logger.LOG_FILE_PATH] = logger
        return logger

