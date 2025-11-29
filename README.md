# MotionForge – Clip Generator (v0.1)

## Benodigdheden

- Python 3.10 of hoger
- ffmpeg geïnstalleerd

## Installatie

```bash
# Ga naar de map waar je MotionForge hebt staan
cd motionforge

# (optioneel) virtuele omgeving
python3 -m venv .venv
source .venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt
```

## Server starten

```bash
cd app
uvicorn main:app --reload --port 8000
```

Daarna:

1. Open je browser  
2. Ga naar: `http://127.0.0.1:8000`  
3. Upload een mp4-video  
4. Kies de clip length (bijv. 6–8 seconden)  
5. Klik op **Generate clips**  
6. Onderaan verschijnen de clips met preview en download-links  
