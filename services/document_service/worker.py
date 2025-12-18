import os
import sys
import json
import PyPDF2
from docx import Document as DocxDocument

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DOC_S3_BUCKET = os.getenv("DOC_S3_BUCKET", "document-reader-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(DOC_S3_BUCKET)

def extract_text(file_path):
    ext = file_path.split('.')[-1].lower()
    text = ""
    if ext == 'pdf':
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
    elif ext == 'docx':
        doc = DocxDocument(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    return text

def process_document_events():
    consumer = kafka_handler.get_consumer("document.uploaded", "doc_worker_group")
    
    for message in consumer:
        data = message.value
        doc_id = data.get("id")
        s3_key = data.get("s3_path")
        
        # Download from S3
        local_path = f"temp_{doc_id}"
        if s3_handler.download_file(s3_key, local_path):
            # Extract text
            text = extract_text(local_path)
            
            # Publish "document.processed" event
            kafka_handler.send_message("document.processed", {
                "id": doc_id,
                "text": text[:2000], # Sending snippet for Kafka size limits, full text in S3
                "s3_path": s3_key
            })
            
            # Simulate Note Generation
            notes = f"Summary of document {doc_id}:\n" + text[:500] + "..."
            
            # Save notes to S3
            notes_key = f"notes/{doc_id}_notes.txt"
            notes_path = f"temp_notes_{doc_id}.txt"
            with open(notes_path, 'w', encoding='utf-8') as f:
                f.write(notes)
            
            if s3_handler.upload_file(notes_path, notes_key):
                kafka_handler.send_message("notes.generated", {
                    "doc_id": doc_id,
                    "notes_s3_path": notes_key
                })
            
            # Cleanup
            if os.path.exists(local_path): os.remove(local_path)
            if os.path.exists(notes_path): os.remove(notes_path)

if __name__ == "__main__":
    process_document_events()
Line 1: # document_service/worker.py
