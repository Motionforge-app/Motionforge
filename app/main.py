import logging
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    allow_origins=["*"],  # eventueel later strenger maken
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def safe_filename(original_name: str) -> str:
    """
    Maak een veilige bestandsnaam (zonder spaties en rare tekens).
    """
    name = original_name.replace(" ", "_")
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))


def split_video(input_path: Path, clip_length: int) -> List[str]:
    """
    Split een video op in stukjes van `clip_length` seconden.
    - audio staat UIT (workaround voor MoviePy / multi-clip issues)
    - GEEN gebruik meer van 'targetname' keyword
    """
    logger.info(f"Start splitting video: {input_path} in chunks of {clip_length}s")

    if not input_path.exists():
        raise RuntimeError(f"Input file does not exist: {input_path}")

    try:
        # audio=False om audio-problemen te vermijden (stabieler op Railway)
        video = VideoFileClip(str(input_path), audio=False)
    except Exception as e:
        raise RuntimeError(f"Failed to open video: {e}")

    duration = float(video.duration or 0)
    if duration <= 0:
        video.close()
        raise RuntimeError(f"Video has invalid duration: {duration}")

    logger.info(f"Video duration: {duration:.2f}s")

    clips_created: List[str] = []
    start = 0.0
    index = 1

    try:
        while start < duration:
            end = min(start + clip_length, duration)
            logger.info(f"Creating subclip {index}: {start:.2f}s -> {end:.2f}s")

            subclip = video.subclip(start, end)

            output_name = f"{input_path.stem}_part{index}.mp4"
            output_path = SPLIT_DIR / output_name

            # BELANGRIJK: geen 'targetname=' meer, gewoon filename als 1e arg
            subclip.write_videofile(
                str(output_path),
                codec="libx264",
                audio=False,      # audio uit voor stabiliteit
                remove_temp=True,
                logger=None,
            )

            clips_created.append(output_name)
            index += 1
            start = end

        logger.info(f"Finished splitting. Created {len(clips_created)} clips.")
        return clips_created

    except Exception as e:
        logger.exception("Error during splitting")
        raise RuntimeError(f"Error while splitting video: {e}")

    finally:
        video.close()


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------


@app.get("/")
async def root():
    return {"status": "ok", "message": "MotionForge backend running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    clip_length: int = Query(4, description="Length of each clip in seconds"),
):
    """
    Upload 1 video en split deze in clips van `clip_length` seconden.
    Frontend roept dit aan als:
      POST /upload?clip_length=4
    met 1 bestand in 'file'.
    """
    logger.info(f"Received upload: filename={file.filename}, clip_length={clip_length}")

    if clip_length <= 0:
        raise HTTPException(status_code=400, detail="clip_length must be > 0")

    try:
        filename = safe_filename(file.filename or "input.mp4")
        input_path = CLIPS_DIR / filename

        # bestand wegschrijven
        with input_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Saved file to {input_path} ({len(content)} bytes)")

        # video splitten
        try:
            clips = split_video(input_path, clip_length)
        except Exception as e:
            logger.exception("Split error")
            # Dit is de fout die jij in de frontend ziet
            raise HTTPException(status_code=500, detail=f"Split error: {e}")

        return JSONResponse(
            {
                "status": "ok",
                "message": "Video split successfully",
                "original": filename,
                "clips": clips,
            }
        )

    except HTTPException:
        # al geformatteerde fout
        raise
    except Exception as e:
        logger.exception("Unexpected error in /upload")
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")


@app.get("/clips")
async def list_clips():
    """
    Optionele endpoint voor je frontend:
    lijst alle gegenereerde clips in de split-map.
    """
    files = [f.name for f in SPLIT_DIR.glob("*.mp4")]
    return {"count": len(files), "clips": files}
