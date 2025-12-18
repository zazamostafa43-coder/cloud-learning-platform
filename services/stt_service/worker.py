import os
import sys
import json
import whisper

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
STT_S3_BUCKET = os.getenv("STT_S3_BUCKET", "stt-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(STT_S3_BUCKET)

# Load Whisper model
model = whisper.load_model("base")

def process_transcription_request():
    consumer = kafka_handler.get_consumer("audio.transcription.requested", "stt_worker_group")
    
    for message in consumer:
        data = message.value
        file_id = data.get("id")
        s3_key = data.get("s3_path")
        
        # Download from S3
        local_path = f"temp_{file_id}"
        if s3_handler.download_file(s3_key, local_path):
            # Transcribe
            result = model.transcribe(local_path)
            transcription_text = result["text"]
            
            # Send completion message
            kafka_handler.send_message("audio.transcription.completed", {
                "id": file_id,
                "text": transcription_text,
                "status": "completed"
            })
            
            # Cleanup
            os.remove(local_path)

if __name__ == "__main__":
    process_transcription_request()
Line 1: # stt_service/worker.py
