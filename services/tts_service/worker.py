import os
import sys
import json
from gtts import gTTS

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TTS_S3_BUCKET = os.getenv("TTS_S3_BUCKET", "tts-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(TTS_S3_BUCKET)

def process_tts_request():
    consumer = kafka_handler.get_consumer("audio.generation.requested", "tts_worker_group")
    
    for message in consumer:
        data = message.value
        request_id = data.get("id")
        text = data.get("text")
        lang = data.get("language", "en")
        
        # Generate speech
        tts = gTTS(text=text, lang=lang)
        local_path = f"{request_id}.mp3"
        tts.save(local_path)
        
        # Upload to S3
        s3_key = f"generated/{request_id}.mp3"
        if s3_handler.upload_file(local_path, s3_key):
            # Send completion message
            kafka_handler.send_message("audio.generation.completed", {
                "id": request_id,
                "s3_path": s3_key,
                "status": "completed"
            })
            
        # Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    process_tts_request()
Line 1: # tts_service/worker.py
