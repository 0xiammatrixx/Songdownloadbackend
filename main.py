import tempfile
from fastapi import FastAPI, File, Query, UploadFile, BackgroundTasks
from youtube_explode_fallback import fallback_with_ytdlp
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse
import subprocess
import os
import uuid
import threading

app = FastAPI()
MAX_FILE_SIZE_MB = 100

@app.get("/")
def root():
    return {"message": "YouTube downloader is alive."}

@app.get("/download/")
def download(video_url: str = Query(...)):
    try:
        result = fallback_with_ytdlp(video_url)
        return {"detail": result}
    except Exception as e:
        return {"error": str(e)}
    
# New Endpoint for Query-based download
class QueryModel(BaseModel):
    query: str

@app.post("/download-by-query")
def download_by_query(data: QueryModel):
    try:
        uid = str(uuid.uuid4())[:8]
        os.makedirs("downloads", exist_ok=True)
        output_path = f"downloads/{uid}.mp3"

        command = [
            "yt-dlp",
            f"ytsearch1:{data.query}",
            "-x", "--audio-format", "mp3",
            "--output", output_path,
            "--cookies", "cookies.txt"
        ]

        subprocess.run(command, check=True)

        BackgroundTasks.add_task(os.remove, output_path)

        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{data.query}.mp3")
    except Exception as e:
        return {"error": str(e)}

class URLModel(BaseModel):
    url: str

@app.post("/download-youtube-video")
async def download_youtube_video(data: URLModel):
    try:
        url = data.url
        if not url or "youtube.com" not in url:
            return {"error": "Invalid YouTube URL"}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            filename = tmp.name

        command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "--cookies", "cookies.txt",
            "--max-filesize", "100M",
            "-o", filename,
            url
        ]
        subprocess.run(command, check=True)

        def iterfile():
            with open(filename, mode="rb") as f:
                yield from f

        def cleanup():
            if os.path.exists(filename):
                os.remove(filename)

        threading.Thread(target=cleanup).start()
        return StreamingResponse(iterfile(), media_type="video/mp4")
    except Exception as e:
        return {"error": str(e)}

@app.post("/convert-uploaded-video")
async def convert_uploaded_video(video_file: UploadFile = File(...)):
    try:
        # Step 1: Save uploaded file to disk
        temp_id = str(uuid.uuid4())
        input_path = f"/tmp/{temp_id}_{video_file.filename}"
        output_path = f"/tmp/{temp_id}.mp3"

        with open(input_path, "wb") as f:
            content = await video_file.read()
            f.write(content)

        # Step 2: Convert to mp3 using ffmpeg
        ffmpeg_command = [
            "ffmpeg",
            "-y",  # overwrite if exists
            "-i", input_path,
            "-vn",  # no video
            "-acodec", "libmp3lame",
            "-ab", "192k",
            output_path
        ]
        subprocess.run(ffmpeg_command, check=True)

        # Step 3: Stream MP3 file back
        def iterfile():
            with open(output_path, mode="rb") as file_like:
                yield from file_like

        # Optional: Clean up async
        def cleanup():
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)

        threading.Thread(target=cleanup).start()
        # Use a generator to send file back
        response = StreamingResponse(iterfile(), media_type="audio/mpeg")
        response.headers["Content-Disposition"] = f"attachment; filename=converted.mp3"

        # Schedule cleanup (could be better with background tasks)
        import threading
        threading.Thread(target=cleanup).start()

        return response

    except Exception as e:
        print("❌ Conversion error:", e)
        return {"error": str(e)}