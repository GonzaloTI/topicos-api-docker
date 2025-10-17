# simple_logger.py
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

class AppLogger:
    """
    Logger simple con rotación.
    - Instancia una vez: AppLogger("app.log")
    - Obtén loggers en cualquier clase: app_logger.get("cola_logger.claseA")
      o hijos: app_logger.child("cola_logger", "claseA")

    Evita duplicar handlers aunque lo importes en varios módulos.
    """

    def __init__(
        self,
        log_file: str = "app.log",
        level: int = logging.INFO,
        root_name: str = "cola_logger",
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
        fmt: str = "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    ):
        self.root_name = root_name
        self._configure_once(log_file, level, max_bytes, backup_count, fmt)

    def _configure_once(
        self, log_file: str, level: int, max_bytes: int, backup_count: int, fmt: str
    ):
        root = logging.getLogger(self.root_name)

        # Si ya tiene handlers, no vuelvas a configurarlo
        if root.handlers:
            root.setLevel(level)
            root.propagate = False
            return

        root.setLevel(level)
        root.propagate = False

        handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)

    def get(self, name: Optional[str] = None) -> logging.Logger:
        """Devuelve el logger raíz o uno con nombre específico."""
        if not name or name == self.root_name:
            return logging.getLogger(self.root_name)
        # Si no comienza con el root, lo creamos como hijo
        if not name.startswith(self.root_name + "."):
            name = f"{self.root_name}.{name}"
        return logging.getLogger(name)

    def child(self, parent_or_root: str, child_suffix: str) -> logging.Logger:
        """Atajo para crear 'parent_or_root.child_suffix'."""
        if not parent_or_root.startswith(self.root_name):
            parent_or_root = f"{self.root_name}.{parent_or_root}"
        return logging.getLogger(f"{parent_or_root}.{child_suffix}")
