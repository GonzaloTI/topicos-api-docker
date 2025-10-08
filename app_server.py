from waitress import serve
from gevent import monkey
# Patch para hacer operaciones async-friendly en Windows
monkey.patch_all()

from app import app

if __name__ == '__main__':
    print("🚀 Iniciando servidor Flask con Waitress...")
    print("📍 Servidor corriendo en: http://localhost:8000")
    print("⚡ Configurado para alta concurrencia")
    print("🔄 Threads: 20 | Conexiones: 500+ simultáneas")
    print("-" * 50)
    
    # Configuración para alta concurrencia en Windows
    serve(
        app,
        host='0.0.0.0',
        port=8000,
        threads=20,           # Número de threads
        backlog=2048,         # Cola de conexiones pendientes  
        connection_limit=10000, # Límite de conexiones
        cleanup_interval=30,   # Cleanup cada 30 segundos
        channel_timeout=120,   # Timeout de canal
        log_untrusted_proxy_headers=False,
        clear_untrusted_proxy_headers=True,
        # Para debugging
        # expose_tracebacks=True  # Solo en desarrollo
    )