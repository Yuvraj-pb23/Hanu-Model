import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def check_ffmpeg_installed() -> bool:
    """Check if ffmpeg is accessible."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def convert_to_wav(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
    """Convert any audio/video file to WAV format using ffmpeg."""
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', str(sample_rate),
            '-ac', '1',
            '-f', 'wav',
            '-y', output_path
        ]
        
        process = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error converting audio: {e}")
        return False

def format_time_srt(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds_int = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

def format_transcription_result(result: Dict[str, Any], format_type: str) -> str:
    """Format the raw transcription result into text or SRT."""
    if format_type == "txt":
        return result.get("text", "")
    
    elif format_type == "srt":
        srt_content = []
        for i, segment in enumerate(result.get("segments", []), 1):
            start_time = format_time_srt(segment.get("start", 0))
            end_time = format_time_srt(segment.get("end", 0))
            text = segment.get("text", "").strip()
            
            srt_content.append(f"{i}\\n{start_time} --> {end_time}\\n{text}\\n")
            
        return "\\n".join(srt_content)
    
    return result.get("text", "")
