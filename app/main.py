from fastapi import FastAPI, File, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import shutil
from pathlib import Path

from moviepy.editor import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

# Basis-pad (project root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Mappen (in de projectroot)
UPLOAD_DIR = BASE_DIR / "uploads"
CLIPS_DIR = BASE_DIR / "clips"
PROCESSED_DIR = CLIPS_DIR / "processed"

for p in (UPLOAD_DIR, CLIPS_DIR, PROCESSED_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MotionForge API")

# Clips statisch serveren
app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")


# -----------------------------------------------------------
# VIDEO SPLIT FUNCTIE - MEERDERE CLIPS (SAFE VOOR RAILWAY)
# -----------------------------------------------------------
def split_video(
    input_path: Path,
    output_dir: Path,
    clip_length: int = 8,
    max_clips: int = 10,
):
    """
    Knipt de video in meerdere stukken met ffmpeg (stabieler dan .subclip()).
    - clip_length = lengte per clip in seconden
    - max_clips = veiligheidslimiet
    """
    # Eerst alleen de duur bepalen met VideoFileClip
    with VideoFileClip(str(input_path)) as video:
        duration = int(video.duration)

    clips: list[Path] = []
    start = 0
    clip_index = 1

    while start < duration and clip_index <= max_clips:
        end = min(start + clip_length, duration)
        output_path = output_dir / f"clip_{clip_index}.mp4"

        print(f"DEBUG: generating clip {clip_index} from {start}s to {end}s")

        # Gebruik ffmpeg_extract_subclip i.p.v. video.subclip()
        ffmpeg_extract_subclip(
            str(input_path),
            start,
            end,
            targetname=str(output_path),
        )

        clips.append(output_path)
        start += clip_length
        clip_index += 1

    return clips


# -----------------------------------------------------------
# PROCESS PIPELINE - STABIELE BASIS (KOPIE NAAR /processed)
# -----------------------------------------------------------
def process_clip(input_path: Path) -> Path:
    """
    Verwerkt één clip.
    Nu: maak een kopie in clips/processed/ met suffix _processed.
    Later: hier komen vertical/captions/branding etc.
    """
    output_path = PROCESSED_DIR / f"{input_path.stem}_processed.mp4"
    shutil.copy2(input_path, output_path)
    print(f"DEBUG: processed clip copied to {output_path}")
    return output_path


# -----------------------------------------------------------
# SIMPLE FRONTEND
# -----------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>MotionForge – Clip Generator</title>
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 40px auto; }
            h1 { margin-bottom: 0.2rem; }
            .field { margin: 1rem 0; }
            label { display: block; margin-bottom: 0.3rem; font-weight: 600; }
            input[type="number"] { width: 80px; }
            button { padding: 0.5rem 1.2rem; font-size: 1rem; cursor: pointer; }
            .clips { margin-top: 2rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
            video { width: 100%; border-radius: 8px; }
            .clip-card { border: 1px solid #ddd; border-radius: 8px; padding: 0.75rem; background: #fafafa; }
            .clip-title { font-weight: 600; margin-bottom: 0.25rem; }
            .clip-section-title { font-size: 0.85rem; font-weight: 600; margin-top: 0.5rem; }
            a { font-size: 0.85rem; }
        </style>
    </head>
    <body>
        <h1>MotionForge – Clip Generator</h1>
        <p>Upload één video, kies clip length, krijg meerdere korte clips terug.</p>

        <div class="field">
            <label for="clip_length">Clip length (seconden)</label>
            <input id="clip_length" type="number" min="3" max="60" value="8" />
        </div>

        <div class="field">
            <label for="file">Video bestand (mp4)</label>
            <input id="file" type="file" accept="video/mp4" />
        </div>

        <button onclick="upload()">Generate clips</button>

        <div id="status" style="margin-top:1rem; font-weight:600;"></div>

        <div id="clips" class="clips"></div>

        <script>
            async function upload() {
                const fileInput = document.getElementById('file');
                const clipLengthInput = document.getElementById('clip_length');
                const statusEl = document.getElementById('status');
                const clipsContainer = document.getElementById('clips');

                if (!fileInput.files.length) {
                    alert('Kies eerst een video.');
                    return;
                }

                const file = fileInput.files[0];
                const clipLength = parseInt(clipLengthInput.value || '8', 10);

                const formData = new FormData();
                formData.append('file', file);

                statusEl.textContent = 'Bezig met verwerken...';
                clipsContainer.innerHTML = '';

                try {
                    const response = await fetch(`/upload?clip_length=${clipLength}`, {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const text = await response.text();
                        statusEl.textContent = 'Fout: ' + text;
                        return;
                    }

                    const data = await response.json();
                    statusEl.textContent = `Klaar! ${data.num_clips} clips gegenereerd.`;

                    const originals = data.clip_urls || [];
                    const processed = data.processed_clip_urls || [];

                    originals.forEach((origUrl, index) => {
                        const procUrl = processed[index] || null;

                        const div = document.createElement('div');
                        div.className = 'clip-card';
                        div.innerHTML = `
                            <div class="clip-title">Clip ${index + 1}</div>

                            <div class="clip-section-title">Origineel</div>
                            <video src="${origUrl}" controls></video>
                            <div><a href="${origUrl}" download>Download origineel</a></div>

                            ${procUrl ? `
                                <div class="clip-section-title">Processed</div>
                                <video src="${procUrl}" controls></video>
                                <div><a href="${procUrl}" download>Download processed</a></div>
                            ` : ''}
                        `;
                        clipsContainer.appendChild(div);
                    });

                } catch (err) {
                    console.error(err);
                    statusEl.textContent = 'Onbekende fout in frontend.';
                }
            }
        </script>
    </body>
    </html>
    """


# -----------------------------------------------------------
# UPLOAD ENDPOINT
# -----------------------------------------------------------
@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    clip_length: int = Query(
        8,
        description="Lengte per clip in seconden (standaard 8)",
        ge=3,
        le=60,
    ),
):
    file_location = UPLOAD_DIR / file.filename

    # Sla geüploade video op
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Split video
    clips = split_video(file_location, CLIPS_DIR, clip_length=clip_length)

    # Process elke clip (stabiele kopie naar /processed)
    processed_clips = [process_clip(path) for path in clips]

    # URLs voor frontend
    clip_urls = [f"/clips/{path.name}" for path in clips]
    processed_clip_urls = [f"/clips/processed/{path.name}" for path in processed_clips]

    return {
        "message": "Upload successful + clips generated",
        "filename": file.filename,
        "saved_to": str(file_location),
        "clip_length": clip_length,
        "num_clips": len(clips),
        "clips": [str(p) for p in clips],
        "processed_clips": [str(p) for p in processed_clips],
        "clip_urls": clip_urls,
        "processed_clip_urls": processed_clip_urls,
    }


# -----------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
