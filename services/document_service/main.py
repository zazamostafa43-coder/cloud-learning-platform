from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import uuid
import tempfile
import httpx
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

app = FastAPI(title="Document Reader Service")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
S3_BUCKET = os.getenv("DOC_S3_BUCKET", "document-reader-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(S3_BUCKET)

# Global document storage (shared across services)
documents = {}

class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    summary: Optional[str] = None
    text: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None

def extract_pdf_text(file_path: str) -> dict:
    """Extract text from PDF"""
    try:
        import PyPDF2
        
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            pages = len(reader.pages)
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text.strip())
            
            full_text = "\n\n".join(text_parts)
            
            return {
                "text": full_text,
                "page_count": pages,
                "word_count": len(full_text.split()),
                "status": "completed"
            }
    except Exception as e:
        return {
            "text": f"Error extracting text: {str(e)}",
            "page_count": 0,
            "word_count": 0,
            "status": "error"
        }

def extract_docx_text(file_path: str) -> dict:
    """Extract text from DOCX"""
    try:
        from docx import Document
        
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        
        return {
            "text": full_text,
            "page_count": 1,
            "word_count": len(full_text.split()),
            "status": "completed"
        }
    except Exception as e:
        return {
            "text": f"Error: {str(e)}",
            "page_count": 0,
            "word_count": 0,
            "status": "error"
        }

def extract_txt_text(content: bytes) -> dict:
    """Extract text from TXT"""
    try:
        text = content.decode('utf-8', errors='ignore')
        return {
            "text": text,
            "page_count": 1,
            "word_count": len(text.split()),
            "status": "completed"
        }
    except Exception as e:
        return {
            "text": str(e),
            "page_count": 0,
            "word_count": 0,
            "status": "error"
        }

@app.post("/api/documents/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload and process document"""
    doc_id = str(uuid.uuid4())
    content = await file.read()
    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'txt'
    
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as temp:
            temp.write(content)
            temp_path = temp.name
        
        # Extract based on type
        if file_ext == 'pdf':
            result = extract_pdf_text(temp_path)
        elif file_ext in ['doc', 'docx']:
            result = extract_docx_text(temp_path)
        elif file_ext == 'txt':
            result = extract_txt_text(content)
        else:
            result = extract_txt_text(content)
        
        # Create summary
        text = result["text"]
        if len(text) > 500:
            summary = text[:500] + "..."
        else:
            summary = text
        
        # Store document GLOBALLY
        doc_data = {
            "id": doc_id,
            "filename": file.filename,
            "file_type": file_ext,
            "file_size": len(content),
            "text": text,
            "summary": summary,
            "page_count": result["page_count"],
            "word_count": result["word_count"],
            "status": result["status"],
            "created_at": datetime.utcnow().isoformat()
        }
        documents[doc_id] = doc_data
        
        # Send to Kafka for Quiz service
        try:
            kafka_handler.send_message("document.processed", {
                "id": doc_id,
                "filename": file.filename,
                "text": text[:2000],  # Send text preview for quiz
                "word_count": result["word_count"]
            })
        except Exception as e:
            print(f"Kafka error: {e}")
        
        return DocumentResponse(
            id=doc_id,
            filename=file.filename,
            status=result["status"],
            summary=f"""📄 **Document analyzed successfully!**

📁 File: {file.filename}
📑 Pages: {result['page_count']}
📝 Words: {result['word_count']}

**Summary:**
{summary}

✅ You can now generate a quiz from this document!""",
            text=text,
            page_count=result["page_count"],
            word_count=result["word_count"]
        )
        
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

@app.get("/api/documents/{id}")
async def get_document(id: str):
    """Get document by ID"""
    if id in documents:
        doc = documents[id]
        return {
            "id": id,
            "filename": doc["filename"],
            "text": doc["text"],
            "summary": doc["summary"],
            "page_count": doc["page_count"],
            "word_count": doc["word_count"],
            "status": doc["status"],
            "created_at": doc["created_at"]
        }
    raise HTTPException(status_code=404, detail="Document not found")

@app.get("/api/documents/{id}/text")
async def get_document_text(id: str):
    """Get document text for quiz generation"""
    if id in documents:
        return {
            "id": id,
            "text": documents[id]["text"],
            "word_count": documents[id]["word_count"]
        }
    raise HTTPException(status_code=404, detail="Document not found")

@app.get("/api/documents")
async def list_documents(limit: int = 20):
    """List all documents"""
    items = []
    for doc_id, doc in list(documents.items())[:limit]:
        items.append({
            "id": doc_id,
            "filename": doc["filename"],
            "word_count": doc["word_count"],
            "status": doc["status"],
            "created_at": doc["created_at"]
        })
    return {"documents": items, "total": len(documents)}

@app.delete("/api/documents/{id}")
async def delete_document(id: str):
    """Delete document"""
    if id in documents:
        del documents[id]
        return {"message": "Deleted", "id": id}
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "documents", "version": "2.0", "doc_count": len(documents)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
