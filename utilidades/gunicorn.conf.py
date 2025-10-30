import multiprocessing

# Configuración del servidor
bind = "0.0.0.0:8000"
backlog = 2048

# Configuración de workers
workers = multiprocessing.cpu_count() * 2 + 1  # Fórmula recomendada
worker_class = "gevent"
worker_connections = 1000  # Conexiones por worker
max_requests = 1000        # Requests antes de reciclar worker
max_requests_jitter = 50   # Variación random

# Timeouts
timeout = 30
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "-"           # Log a stdout
errorlog = "-"           # Log de errores a stdout
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Proceso
user = None
group = None
tmp_upload_dir = None
daemon = False
pidfile = "/tmp/gunicorn.pid"

# SSL (si necesitas HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Configuración específica para alta concurrencia
preload_app = True        # Carga la app antes de hacer fork
enable_stdio_inheritance = True