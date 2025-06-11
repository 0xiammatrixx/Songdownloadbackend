import subprocess
import os
from fastapi import HTTPException

def fallback_with_ytdlp(video_url: str, output_dir: str = "downloads") -> str:
    os.makedirs(output_dir, exist_ok=True)

    command = [
        "yt-dlp",
        "--cookies", "www.youtube.com_cookies.txt",  # Ensure this file is in your project root
        "-f", "best",
        "-o", f"{output_dir}/%(title)s.%(ext)s",
        video_url,
    ]

    try:
        subprocess.run(command, check=True)
        return "Downloaded successfully with yt-dlp"
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp failed: {str(e)}")
