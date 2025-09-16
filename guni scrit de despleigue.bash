#!/bin/bash

# =================================
# INSTALACIÓN Y CONFIGURACIÓN
# =================================

# 1. Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt

# =================================
# COMANDOS DE EJECUCIÓN
# =================================

# 2a. OPCIÓN 1: Ejecutar con archivo de configuración
echo "Iniciando con archivo de configuración..."
gunicorn --config gunicorn.conf.py app:app

# 2b. OPCIÓN 2: Ejecutar con parámetros en línea de comandos
echo "Iniciando con parámetros manuales..."
gunicorn \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class gevent \
  --worker-connections 250 \
  --timeout 30 \
  --keepalive 2 \
  --max-requests 1000 \
  --preload \
  --access-logfile - \
  --error-logfile - \
  app:app

# =================================
# CONFIGURACIONES PARA DIFERENTES CARGAS
# =================================

# Para 500 conexiones simultáneas
echo "Configuración para 500 conexiones simultáneas:"
echo "gunicorn --workers 2 --worker-class gevent --worker-connections 250 app:app"

# Para 1000 conexiones simultáneas  
echo "Configuración para 1000 conexiones simultáneas:"
echo "gunicorn --workers 4 --worker-class gevent --worker-connections 250 app:app"

# Para 2000 conexiones simultáneas
echo "Configuración para 2000 conexiones simultáneas:"
echo "gunicorn --workers 4 --worker-class gevent --worker-connections 500 app:app"
gunicorn --workers 4 --worker-class gevent --worker-connections 250 app:app
# Para 5000 conexiones simultáneas
echo "Configuración para 5000 conexiones simultáneas:"
echo "gunicorn --workers 10 --worker-class gevent --worker-connections 500 app:app"

# =================================
# MONITOREO Y DEBUGGING
# =================================

# Ver procesos activos
echo "Ver procesos de Gunicorn:"
echo "ps aux | grep gunicorn"

# Matar todos los procesos
echo "Matar procesos:"
echo "pkill -f gunicorn"

# Reload graceful (sin downtime)
echo "Reload sin downtime:"
echo "kill -HUP \$(pgrep -f 'gunicorn.*app:app')"

# =================================
# OPTIMIZACIÓN DEL SISTEMA OPERATIVO
# =================================

# Aumentar límites del sistema
echo "Optimizaciones del SO:"
echo "ulimit -n 65536"  # Más file descriptors
echo "echo 'net.core.somaxconn = 4096' >> /etc/sysctl.conf"
echo "echo 'net.ipv4.tcp_max_syn_backlog = 4096' >> /etc/sysctl.conf"
echo "sysctl -p"