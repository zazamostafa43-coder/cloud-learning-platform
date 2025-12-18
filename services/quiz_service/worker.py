import os
import sys
import json

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
QUIZ_S3_BUCKET = os.getenv("QUIZ_S3_BUCKET", "quiz-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(QUIZ_S3_BUCKET)

def process_quiz_events():
    consumer = kafka_handler.get_consumer("quiz.requested", "quiz_worker_group")
    
    for message in consumer:
        data = message.value
        quiz_id = data.get("id")
        doc_id = data.get("document_id")
        
        # Here we would use LangChain to generate a quiz from document text/notes
        # stored in S3 (accessed via Kafka event data paths)
        
        print(f"Generating quiz {quiz_id} for document {doc_id}...")
        
        # Simulate generation completion
        kafka_handler.send_message("quiz.generated", {
            "id": quiz_id,
            "document_id": doc_id,
            "status": "completed"
        })

if __name__ == "__main__":
    process_quiz_events()
Line 1: # quiz_service/worker.py
