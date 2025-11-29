FROM python:3.11-slim

# Snellere, schonere Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ffmpeg voor MoviePy
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Werkmap in de container
WORKDIR /app

# Python-deps installeren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code kopiëren
COPY . .

# Zorg dat alle mappen bestaan
RUN mkdir -p app/uploads app/clips clips clips/processed uploads

# Standaardpoort (Railway geeft zelf $PORT mee)
EXPOSE 8000

# Start FastAPI via Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
