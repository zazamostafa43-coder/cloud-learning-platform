from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
import os
import uuid
import tempfile
import io
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

app = FastAPI(title="TTS Service - Text to Speech")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
S3_BUCKET = os.getenv("TTS_S3_BUCKET", "tts-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(S3_BUCKET)

# In-memory storage for audio files
audio_storage = {}

class TTSRequest(BaseModel):
    text: str
    language: str = "ar"
    speed: float = 1.0

class TTSResponse(BaseModel):
    id: str
    status: str
    message: str
    audio_url: Optional[str] = None
    text_preview: Optional[str] = None

def generate_audio_gtts(text: str, language: str) -> bytes:
    """Generate audio using gTTS"""
    try:
        from gtts import gTTS
        
        # Map common language codes
        lang_map = {
            "ar": "ar",
            "en": "en",
            "fr": "fr",
            "de": "de",
            "es": "es",
            "zh": "zh-CN",
        }
        lang = lang_map.get(language, "ar")
        
        # Create TTS
        tts = gTTS(text=text, lang=lang, slow=False)
        
        # Save to bytes
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        return audio_buffer.read()
    except Exception as e:
        print(f"gTTS error: {e}")
        raise

@app.post("/api/tts/synthesize", response_model=TTSResponse)
async def synthesize_speech(request: TTSRequest):
    """Convert text to speech and return audio"""
    request_id = str(uuid.uuid4())
    
    try:
        # Generate audio
        audio_bytes = generate_audio_gtts(request.text, request.language)
        
        # Store in memory
        audio_storage[request_id] = {
            "audio": audio_bytes,
            "text": request.text,
            "language": request.language,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Log to Kafka
        try:
            kafka_handler.send_message("audio.generation.completed", {
                "id": request_id,
                "text_preview": request.text[:50],
                "language": request.language,
                "status": "completed"
            })
        except Exception as e:
            print(f"Kafka error: {e}")
        
        return TTSResponse(
            id=request_id,
            status="completed",
            message="✅ تم إنشاء الملف الصوتي بنجاح!",
            audio_url=f"/api/tts/audio/{request_id}/download",
            text_preview=request.text[:100] if len(request.text) > 100 else request.text
        )
        
    except Exception as e:
        return TTSResponse(
            id=request_id,
            status="error",
            message=f"❌ خطأ في إنشاء الصوت: {str(e)}",
            text_preview=request.text[:50]
        )

@app.get("/api/tts/audio/{id}/download")
async def download_audio(id: str):
    """Download the generated audio file"""
    if id not in audio_storage:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    audio_data = audio_storage[id]
    audio_bytes = audio_data["audio"]
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="speech_{id}.mp3"'
        }
    )

@app.get("/api/tts/audio/{id}/stream")
async def stream_audio(id: str):
    """Stream the audio for playback"""
    if id not in audio_storage:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    audio_data = audio_storage[id]
    audio_bytes = audio_data["audio"]
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg"
    )

@app.get("/api/tts/audio/{id}")
async def get_audio_info(id: str):
    """Get audio info"""
    if id not in audio_storage:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    data = audio_storage[id]
    return {
        "id": id,
        "text_preview": data["text"][:100],
        "language": data["language"],
        "audio_url": f"/api/tts/audio/{id}/stream",
        "download_url": f"/api/tts/audio/{id}/download",
        "created_at": data["created_at"]
    }

@app.delete("/api/tts/audio/{id}")
async def delete_audio(id: str):
    """Delete audio"""
    if id in audio_storage:
        del audio_storage[id]
        return {"message": "Audio deleted", "id": id}
    raise HTTPException(status_code=404, detail="Audio not found")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "tts", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
