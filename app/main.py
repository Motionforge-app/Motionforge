import logging
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from moviepy.editor import VideoFileClip

# ---------------------------------------------------------
# Basisconfig
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CLIPS_DIR = BASE_DIR / "clips"
SPLIT_DIR = CLIPS_DIR / "split"

CLIPS_DIR.mkdir(parents=True, exist_ok=True)
SPLIT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("motionforge")

app = FastAPI(title="MotionForge Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def safe_filename(original_name: str) -> str:
    """Maak een veilige bestandsnaam"""
    name = original_name.replace(" ", "_")
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))


def split_video(input_path: Path, clip_length: int) -> List[str]:
    """Split video in clips van N seconden, zonder audio (stabieler op Railway)."""
    logger.info(f"Start splitting: {input_path} in chunks of {clip_length}s")

    if not input_path.exists():
        raise RuntimeError(f"Input file not found: {input_path}")

    try:
        video = VideoFileClip(str(input_path), audio=False)
    except Exception as e:
        raise RuntimeError(f"Failed to open video: {e}")

    duration = float(video.duration or 0)
    if duration <= 0:
        video.close()
        raise RuntimeError("Invalid video duration")

    clips_created = []
    start = 0.0
    index = 1

    try:
        while start < duration:
            end = min(start + clip_length, duration)
            logger.info(f"Clip {index}: {start:.2f}s → {end:.2f}s")

            subclip = video.subclip(start, end)
            output_name = f"{input_path.stem}_part{index}.mp4"
            output_path = SPLIT_DIR / output_name

            subclip.write_videofile(
                str(output_path),
                codec="libx264",
                audio=False,
                remove_temp=True,
                logger=None,
            )

            clips_created.append(output_name)
            start = end
            index += 1

        video.close()
        return clips_created

    except Exception as e:
        video.close()
        logger.exception("Error during splitting")
        raise RuntimeError(f"Error while splitting video: {e}")


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "message": "MotionForge backend running"}


@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    clip_length: int = Query(4, description="Length of each clip in seconds"),
):
    logger.info(f"Received upload: {file.filename} (clip_length={clip_length})")

    if clip_length <= 0:
        raise HTTPException(status_code=400, detail="clip_length must be > 0")

    try:
        filename = safe_filename(file.filename or "input.mp4")
        input_path = CLIPS_DIR / filename

        # bestand wegschrijven
        with input_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Saved to {input_path} ({len(content)} bytes)")

        # splitten
        try:
            clips = split_video(input_path, clip_length)
        except Exception as e:
            logger.exception("Split error")
            raise HTTPException(status_code=500, detail=f"Split error: {e}")

        return JSONResponse({
            "status": "ok",
            "message": "Video split successfully",
            "original": filename,
            "clips": clips,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload error")
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")


@app.get("/clips")
async def list_clips():
    """Toon alle clips in de split-map."""
    files = [f.name for f in SPLIT_DIR.glob("*.mp4")]
    return {"count": len(files), "clips": files}


# ---------------------------------------------------------
# NEW: Download endpoint
# ---------------------------------------------------------
@app.get("/download/{filename}")
async def download_clip(filename: str):
    """Download één clip direct vanaf Railway."""
    file_path = SPLIT_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
    )
