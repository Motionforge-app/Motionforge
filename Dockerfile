# Gebruik Python image
FROM python:3.11-slim

# Snellere Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ffmpeg installeren
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Werkdirectory
WORKDIR /app

# Dependencies kopiëren en installeren
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Applicatie kopiëren
COPY . /app

# Start FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
