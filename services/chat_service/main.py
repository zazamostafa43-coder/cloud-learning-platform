from fastapi import FastAPI, HTTPException
import os
import uuid
import random
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

from services.common.kafka_handler import KafkaHandler
from services.common.s3_handler import S3Handler

app = FastAPI(title="Chat Completion Service")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
S3_BUCKET = os.getenv("CHAT_S3_BUCKET", "chat-service-storage-dev")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)
s3_handler = S3Handler(S3_BUCKET)

# In-memory storage
conversations: Dict[str, List[dict]] = {}
document_context: Dict[str, str] = {}  # Store document text for context

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    document_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    message_count: int = 0
    created_at: Optional[str] = None

# Knowledge base for intelligent responses (Bilingual)
KNOWLEDGE_BASE = {
    "python": {
        "ar": "Python هي لغة برمجة عالية المستوى سهلة التعلم. تستخدم في تطوير الويب، علوم البيانات، والذكاء الاصطناعي.",
        "en": "Python is a high-level, easy-to-learn programming language used in web development, data science, and AI."
    },
    "docker": {
        "ar": "Docker هو منصة لتشغيل التطبيقات في حاويات معزولة لضمان ثبات البيئة.",
        "en": "Docker is a platform for running applications in isolated containers, ensuring consistent environments."
    },
    "kafka": {
        "ar": "Apache Kafka هو نظام message queue موزع عالي الأداء للتواصل بين الخدمات.",
        "en": "Apache Kafka is a high-performance distributed message queue used for service communication."
    },
    "aws": {
        "ar": "Amazon Web Services هي منصة حوسبة سحابية رائدة تقدم خدمات التخزين والذكاء الاصطناعي.",
        "en": "Amazon Web Services (AWS) is a leading cloud platform offering storage, compute, and AI services."
    },
    "fastapi": {
        "ar": "FastAPI هو إطار عمل Python حديث وسريع لبناء APIs مع توثيق تلقائي.",
        "en": "FastAPI is a modern, fast Python framework for building APIs with automatic documentation."
    }
}

# Keyword patterns
GREETING_KEYWORDS = ["hello", "hi", "hey", "مرحبا", "اهلا", "hey", "السلام"]
HELP_KEYWORDS = ["help", "مساعدة", "how", "كيف", "explain", "شرح"]

def detect_language(text: str) -> str:
    """Simple language detection based on characters"""
    arabic_chars = [chr(i) for i in range(0x0600, 0x06FF)]
    if any(char in arabic_chars for char in text):
        return "ar"
    return "en"

def find_knowledge(query: str, lang: str) -> Optional[str]:
    """Find relevant knowledge based on language"""
    query_lower = query.lower()
    for key, values in KNOWLEDGE_BASE.items():
        if key in query_lower:
            return values.get(lang, values.get("en"))
    return None

def generate_ai_response(message: str, conversation_history: List[dict], document_text: str = None) -> str:
    """Generate bilingual intelligent response"""
    lang = detect_language(message)
    message_lower = message.lower()
    
    if any(kw in message_lower for kw in GREETING_KEYWORDS):
        if lang == "ar":
            return "مرحباً بك! أنا مساعدك الذكي في منصة التعلم السحابية. كيف يمكنني مساعدتك؟ 🎓"
        return "Hello! I'm your AI learning assistant. How can I help you today? 🤖"
    
    if any(kw in message_lower for kw in HELP_KEYWORDS):
        if lang == "ar":
            return """🌟 **إليك ما يمكنني القيام به:**
- تحويل الصوت (STT) ونص للخدمة.
- إنشاء اختبارات ذكية من ملفاتك.
- الإجابة على استفساراتك التعليمية."""
        return """🌟 **I can help you with:**
- **STT**: Convert your voice notes to text.
- **TTS**: Generate natural speech from text.
- **Documents**: Analyze and summarize your PDFs.
- **Quizzes**: Generate tests from your study materials.
- Ask me anything about Cloud, Python, or your documents!"""

    if document_text:
        if lang == "ar":
            return f"📚 **بناءً على المستند المرفوع:**\n\n{document_text[:300]}...\n\nهل تريد إنشاء اختبار حول هذا المحتوى؟"
        return f"📚 **Based on the uploaded document:**\n\n{document_text[:300]}...\n\nWould you like me to generate a quiz based on this content?"

    knowledge = find_knowledge(message, lang)
    if knowledge:
        return f"📖 **{message.capitalize()}:**\n\n{knowledge}\n\n" + ("Do you want to know more?" if lang == "en" else "هل تريد معرفة المزيد؟")

    # Default responses
    if lang == "ar":
        return f"سؤال رائع عن '{message}'! جرب رفع مستند حول هذا الموضوع لأتمكن من مساعدتك بشكل أفضل. 📄"
    return f"Great question about '{message}'! Try uploading a document about this topic so I can assist you better. 📄"

@app.post("/api/chat/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message and get AI response"""
    conv_id = request.conversation_id or str(uuid.uuid4())
    
    # Initialize or get conversation
    if conv_id not in conversations:
        conversations[conv_id] = []
    
    # Add user message
    user_msg = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    }
    conversations[conv_id].append(user_msg)
    
    # Get document context if provided
    doc_text = None
    if request.document_id and request.document_id in document_context:
        doc_text = document_context[request.document_id]
    
    # Generate response
    ai_response = generate_ai_response(
        request.message, 
        conversations[conv_id],
        doc_text
    )
    
    # Add assistant message
    assistant_msg = {
        "role": "assistant",
        "content": ai_response,
        "timestamp": datetime.utcnow().isoformat()
    }
    conversations[conv_id].append(assistant_msg)
    
    # Log to Kafka
    try:
        kafka_handler.send_message("chat.message", {
            "conversation_id": conv_id,
            "user_message": request.message[:100],
            "assistant_response": ai_response[:100],
            "document_id": request.document_id,
            "timestamp": assistant_msg["timestamp"]
        })
    except Exception as e:
        print(f"Kafka logging failed: {e}")
    
    # Archive conversation to S3 if it gets long
    if len(conversations[conv_id]) > 10 and len(conversations[conv_id]) % 10 == 0:
        try:
            import json
            s3_key = f"conversations/{conv_id}/history.json"
            s3_handler.s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(conversations[conv_id], ensure_ascii=False).encode('utf-8'),
                ContentType="application/json"
            )
        except Exception as e:
            print(f"S3 archive failed: {e}")
    
    return ChatResponse(
        conversation_id=conv_id,
        response=ai_response,
        message_count=len(conversations[conv_id]),
        created_at=assistant_msg["timestamp"]
    )

@app.get("/api/chat/conversations")
async def list_conversations(limit: int = 10):
    """List all conversations"""
    items = []
    for conv_id, messages in list(conversations.items())[:limit]:
        last_msg = messages[-1] if messages else None
        items.append({
            "id": conv_id,
            "message_count": len(messages),
            "last_message": last_msg["content"][:50] + "..." if last_msg else None,
            "last_timestamp": last_msg["timestamp"] if last_msg else None
        })
    return {"conversations": items, "total": len(conversations)}

@app.get("/api/chat/conversations/{id}")
async def get_conversation(id: str):
    """Get conversation history"""
    if id in conversations:
        return {
            "id": id,
            "messages": conversations[id],
            "message_count": len(conversations[id])
        }
    raise HTTPException(status_code=404, detail="Conversation not found")

@app.delete("/api/chat/conversations/{id}")
async def delete_conversation(id: str):
    """Delete a conversation"""
    if id in conversations:
        conversations.pop(id)
        return {"message": "Conversation deleted", "id": id}
    raise HTTPException(status_code=404, detail="Conversation not found")

@app.post("/api/chat/context/document")
async def add_document_context(document_id: str, text: str):
    """Add document context for chat (internal API)"""
    document_context[document_id] = text
    return {"message": "Document context added", "document_id": document_id}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chat", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
