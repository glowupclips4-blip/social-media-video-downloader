
import os
import re
import uuid
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

app = FastAPI()

allowed_origin = os.getenv("ALLOWED_ORIGIN")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin] if allowed_origin else ["*"],
    allow_credentials=bool(allowed_origin),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/download")
async def download_video(url: str = Query(...), format: str = Query("best")):
    uid = uuid.uuid4().hex[:12]
    output_template = f"/tmp/{uid}.%(ext)s"

    try:
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title") or "video"

        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", title)
        safe_title = safe_title.strip("._-") or "video"
        safe_title = safe_title[:120]

        ydl_opts = {
            "format": format,
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        matches = list(Path("/tmp").glob(f"{uid}.*"))
        if not matches:
            raise HTTPException(
                status_code=500,
                detail="Download finished, but the video file was not found.",
            )

        downloaded_file = matches[0]
        filename = f"{safe_title}{downloaded_file.suffix}"

        def iterfile():
            try:
                with open(downloaded_file, "rb") as video:
                    while True:
                        chunk = video.read(1024 * 1024)
                        if not chunk:
                            break
                        yield chunk
            finally:
                try:
                    downloaded_file.unlink(missing_ok=True)
                except OSError:
                    pass

        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        message = str(e).encode("ascii", errors="replace").decode("ascii")
        raise HTTPException(
            status_code=500,
            detail=f"Error during download: {message}",
        )


@app.get("/")
async def root():
    return {
        "message": (
            "Welcome to the Social Media Video Downloader API. "
            "Use /download?url=<video_url>&format=<video_format> "
            "to download videos."
        )
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
            
