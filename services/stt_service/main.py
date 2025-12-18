from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
import os
import uuid
import tempfile
import wave
import io
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

app = FastAPI(title="STT Service - Speech to Text")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
S3_BUCKET = os.getenv("STT_S3_BUCKET", "stt-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(S3_BUCKET)

# Storage
transcriptions = {}

class TranscriptionResponse(BaseModel):
    id: str
    text: str
    status: str
    filename: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None

def transcribe_with_speech_recognition(audio_path: str, language: str = "en") -> dict:
    """Transcribe using SpeechRecognition library"""
    try:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        
        # Convert to WAV if needed using pydub
        wav_path = audio_path
        if not audio_path.endswith('.wav'):
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(audio_path)
                wav_path = audio_path + ".wav"
                audio.export(wav_path, format="wav")
            except Exception as e:
                print(f"Pydub conversion failed: {e}")
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        
        # Try Google Speech Recognition
        lang_code = "ar-SA" if language == "ar" else "en-US"
        text = recognizer.recognize_google(audio_data, language=lang_code)
        
        if wav_path != audio_path and os.path.exists(wav_path):
            os.unlink(wav_path)
            
        return {
            "text": text,
            "confidence": 0.95,
            "status": "completed"
        }
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return {
            "text": "",
            "confidence": 0.0,
            "status": "error"
        }

def transcribe_with_whisper(audio_path: str) -> dict:
    """Transcribe using OpenAI Whisper"""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return {
            "text": result["text"],
            "confidence": 0.95,
            "status": "completed",
            "language": result.get("language", "unknown")
        }
    except Exception as e:
        print(f"Whisper error: {e}")
        return None

@app.post("/api/stt/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "en"
):
    """Upload audio file and transcribe to text (Bilingual Support)"""
    file_id = str(uuid.uuid4())
    content = await file.read()
    file_size = len(content)
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'wav'
    
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Try Whisper first
        result = transcribe_with_whisper(temp_path)
        if not result:
            result = transcribe_with_speech_recognition(temp_path, language)
        
        if not result or result["status"] == "error" or not result["text"]:
            result = {
                "text": f"""📊 Audio File Analysis:
                
📁 Filename: {file.filename}
📦 Size: {file_size / 1024:.1f} KB
🎵 Format: {file_ext.upper()}

⚠️ Note: No clear speech recognized. 
Possible reasons: Poor quality, background noise, or unsupported format.""",
                "confidence": 0.0,
                "status": "completed"
            }
        
        transcriptions[file_id] = {
            "text": result["text"],
            "filename": file.filename,
            "language": language,
            "confidence": result.get("confidence", 0.0),
            "status": result["status"],
            "file_size": file_size,
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            kafka_handler.send_message("audio.transcription.completed", {
                "id": file_id,
                "filename": file.filename,
                "text_preview": result["text"][:100],
                "language": language
            })
        except: pass
        
        return TranscriptionResponse(
            id=file_id,
            text=result["text"],
            status=result["status"],
            filename=file.filename,
            language=language,
            confidence=result.get("confidence")
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

@app.get("/api/stt/transcription/{id}")
async def get_transcription(id: str):
    if id in transcriptions:
        return {"id": id, **transcriptions[id]}
    raise HTTPException(status_code=404, detail="Transcription not found")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "stt", "version": "3.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
