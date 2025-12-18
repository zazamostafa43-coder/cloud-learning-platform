from fastapi import FastAPI, HTTPException
import os
import uuid
import random
import json
import httpx
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

from services.common.kafka_handler import KafkaHandler

app = FastAPI(title="Quiz Generator Service")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
DOC_SERVICE_URL = os.getenv("DOC_SERVICE_URL", "http://document-service:8003")

kafka_handler = KafkaHandler(KAFKA_BOOTSTRAP_SERVERS)

# Storage
quizzes = {}
quiz_results = {}

class Question(BaseModel):
    id: int
    question: str
    options: List[str]
    answer: str
    explanation: Optional[str] = None

class QuizRequest(BaseModel):
    document_id: Optional[str] = None
    topic: Optional[str] = None
    num_questions: int = 5

class QuizResponse(BaseModel):
    id: str
    status: str
    topic: Optional[str] = None
    num_questions: int = 0
    questions: Optional[List[Question]] = None
    source_document: Optional[str] = None

class SubmitRequest(BaseModel):
    answers: Dict[int, str]

# Basic question templates for generating from text
def generate_questions_from_text(text: str, num_questions: int = 5) -> List[dict]:
    """Generate quiz questions from document text using AI-like analysis"""
    if not text or len(text) < 50:
        return []
    
    questions = []
    sentences = text.replace('\n', ' ').split('.')
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if not sentences:
        return []
    
    # Extract key phrases and generate questions
    used_sentences = set()
    
    for i in range(min(num_questions, len(sentences))):
        # Pick a random sentence
        available = [s for j, s in enumerate(sentences) if j not in used_sentences]
        if not available:
            break
            
        sentence = random.choice(available)
        used_sentences.add(sentences.index(sentence))
        
        # Find important words
        words = sentence.split()
        important_words = [w for w in words if len(w) > 4]
        
        if important_words:
            keyword = random.choice(important_words)
            
            # Create fill-in-the-blank style question
            questions.append({
                "q": f"Based on the document, what is the concept related to: '{keyword}'?",
                "options": [
                    f"It relates to: {sentence[:50]}...",
                    "No mention of this in the document",
                    "The concept is unclear in the text",
                    "All of the above"
                ],
                "answer": f"It relates to: {sentence[:50]}...",
                "explanation": f"This concept is mentioned in the document: {sentence[:100]}..."
            })
    
    return questions

# Fallback question banks
FALLBACK_QUESTIONS = {
    "general": [
        {"q": "What is the importance of lifelong learning?", "options": ["Skill development", "Staying in the past", "Avoiding challenges", "None"], "answer": "Skill development", "explanation": "Lifelong learning is essential for skill development and adapting to changes."},
        {"q": "What is the goal of education?", "options": ["Building knowledge and skills", "Memorization only", "Exams only", "None"], "answer": "Building knowledge and skills", "explanation": "Education aims to build educated individuals capable of thinking."},
        {"q": "How can comprehension be improved?", "options": ["Repetition and practice", "Speed reading", "Avoiding questions", "Sleeping"], "answer": "Repetition and practice", "explanation": "Practice and repetition help consolidate information."},
    ],
    "cloud": [
        {"q": "What is Cloud Computing?", "options": ["Online services", "Local computer", "Hard drive", "None"], "answer": "Online services", "explanation": "Cloud computing provides computing resources over the internet."},
        {"q": "What is the benefit of Docker?", "options": ["Running apps in containers", "Website design", "Writing code", "None"], "answer": "Running apps in containers", "explanation": "Docker isolates applications in containers for consistent operation."},
    ]
}

async def fetch_document_text(document_id: str) -> Optional[str]:
    """Fetch document text from Document Service"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{DOC_SERVICE_URL}/api/documents/{document_id}/text")
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
    except Exception as e:
        print(f"Error fetching document: {e}")
    return None

@app.post("/api/quiz/generate", response_model=QuizResponse)
async def generate_quiz(request: QuizRequest):
    """Generate quiz - from document or topic"""
    quiz_id = str(uuid.uuid4())
    questions = []
    source_doc = None
    topic = request.topic or "general"
    
    # If document_id provided, generate from document
    if request.document_id:
        doc_text = await fetch_document_text(request.document_id)
        
        if doc_text:
            source_doc = request.document_id
            topic = f"document-{request.document_id[:8]}"
            
            # Generate questions from document text
            generated = generate_questions_from_text(doc_text, request.num_questions)
            
            for i, q in enumerate(generated):
                questions.append(Question(
                    id=i + 1,
                    question=q["q"],
                    options=q["options"],
                    answer=q["answer"],
                    explanation=q.get("explanation")
                ))
    
    # If no questions yet, use fallback
    if not questions:
        pool = FALLBACK_QUESTIONS.get(topic, FALLBACK_QUESTIONS["general"])
        selected = random.sample(pool, min(request.num_questions, len(pool)))
        
        for i, q in enumerate(selected):
            questions.append(Question(
                id=i + 1,
                question=q["q"],
                options=q["options"],
                answer=q["answer"],
                explanation=q.get("explanation")
            ))
    
    # Store quiz
    quizzes[quiz_id] = {
        "topic": topic,
        "questions": questions,
        "source_document": source_doc,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Kafka event
    try:
        kafka_handler.send_message("quiz.generated", {
            "id": quiz_id,
            "topic": topic,
            "num_questions": len(questions),
            "document_id": source_doc
        })
    except:
        pass
    
    return QuizResponse(
        id=quiz_id,
        status="completed",
        topic=topic,
        num_questions=len(questions),
        questions=questions,
        source_document=source_doc
    )

@app.get("/api/quiz/{id}")
async def get_quiz(id: str):
    """Get quiz by ID"""
    if id in quizzes:
        quiz = quizzes[id]
        return {
            "id": id,
            "topic": quiz["topic"],
            "questions": [q.dict() for q in quiz["questions"]],
            "source_document": quiz.get("source_document"),
            "created_at": quiz["created_at"]
        }
    raise HTTPException(status_code=404, detail="Quiz not found")

@app.post("/api/quiz/{id}/submit")
async def submit_quiz(id: str, submission: SubmitRequest):
    """Submit quiz answers"""
    if id not in quizzes:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz = quizzes[id]
    questions = quiz["questions"]
    
    correct = []
    wrong = []
    details = []
    
    for q in questions:
        user_answer = submission.answers.get(q.id, "")
        is_correct = user_answer == q.answer
        
        if is_correct:
            correct.append(q.id)
        else:
            wrong.append(q.id)
        
        details.append({
            "question_id": q.id,
            "question": q.question,
            "your_answer": user_answer,
            "correct_answer": q.answer,
            "is_correct": is_correct,
            "explanation": q.explanation
        })
    
    score = len(correct)
    total = len(questions)
    percentage = (score / total * 100) if total > 0 else 0
    
    if percentage >= 80:
        feedback = "🌟 Excellent! Great performance!"
    elif percentage >= 60:
        feedback = "👍 Very Good!"
    elif percentage >= 40:
        feedback = "📚 Good, needs review"
    else:
        feedback = "💪 Try again!"
    
    result = {
        "quiz_id": id,
        "score": score,
        "total": total,
        "percentage": percentage,
        "feedback": feedback,
        "correct_answers": correct,
        "wrong_answers": wrong,
        "details": details
    }
    
    # Store result
    if id not in quiz_results:
        quiz_results[id] = []
    quiz_results[id].append(result)
    
    return result

@app.get("/api/quiz/{id}/results")
async def get_results(id: str):
    """Get quiz results"""
    if id not in quizzes:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return {
        "quiz_id": id,
        "attempts": quiz_results.get(id, []),
        "questions": [{"id": q.id, "question": q.question, "answer": q.answer} for q in quizzes[id]["questions"]]
    }

@app.get("/api/quiz/history")
async def quiz_history(limit: int = 10):
    """Get quiz history"""
    items = []
    for qid, quiz in list(quizzes.items())[:limit]:
        items.append({
            "id": qid,
            "topic": quiz["topic"],
            "num_questions": len(quiz["questions"]),
            "source_document": quiz.get("source_document"),
            "created_at": quiz["created_at"]
        })
    return {"quizzes": items}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "quiz", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
