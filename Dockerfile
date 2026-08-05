FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Puerto en el que corre la API (ej. FastAPI o Flask)
EXPOSE 8000

# Comando para arrancar el servidor (ajusta según tu framework, ej: uvicorn main:app)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}]