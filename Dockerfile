FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalamos dependencias del sistema necesarias para psycopg2
# gunicorn -w 4 --threads 2 -b 0.0.0.0:8000 app:app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install -r requirements.txt

#COPY app.py .

# COPY ponyorm.py .

# COPY cola2.py .

# COPY DTO /app/DTO

COPY . .

EXPOSE 8000

#CMD ["gunicorn", "-b", "--timeout 120", "0.0.0.0:8000", "app:app"]
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--timeout", "120", "app:app"]
