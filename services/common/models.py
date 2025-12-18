from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User accounts for the learning platform"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # For future auth
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="owner")
    quizzes = relationship("Quiz", back_populates="user")

class Document(Base):
    """Uploaded documents for processing"""
    __tablename__ = 'documents'
    
    id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    s3_path = Column(String(500))
    status = Column(String(50), default='pending')
    page_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="documents")
    notes = relationship("Note", back_populates="document")
    quizzes = relationship("Quiz", back_populates="source_document")

class Note(Base):
    """Generated notes from documents"""
    __tablename__ = 'notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(100), ForeignKey('documents.id'))
    title = Column(String(255), nullable=True)
    content = Column(Text)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="notes")

class Quiz(Base):
    """Generated quizzes"""
    __tablename__ = 'quizzes'
    
    id = Column(String(100), primary_key=True)
    document_id = Column(String(100), ForeignKey('documents.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    topic = Column(String(100))
    difficulty = Column(String(20), default='medium')
    num_questions = Column(Integer)
    quiz_data = Column(Text)  # JSON representation of quiz questions
    status = Column(String(50), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source_document = relationship("Document", back_populates="quizzes")
    user = relationship("User", back_populates="quizzes")
    attempts = relationship("QuizAttempt", back_populates="quiz")

class QuizAttempt(Base):
    """Quiz attempt records"""
    __tablename__ = 'quiz_attempts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String(100), ForeignKey('quizzes.id'))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    score = Column(Integer)
    total_questions = Column(Integer)
    percentage = Column(Float)
    answers_data = Column(Text)  # JSON of user answers
    completed_at = Column(DateTime, default=datetime.utcnow)
    time_taken_seconds = Column(Integer, nullable=True)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")

class ChatHistory(Base):
    """Chat conversation history"""
    __tablename__ = 'chat_histories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(100), index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    role = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text)
    document_id = Column(String(100), nullable=True)  # If chat is about a document
    timestamp = Column(DateTime, default=datetime.utcnow)

class Transcription(Base):
    """Speech-to-text transcription records"""
    __tablename__ = 'transcriptions'
    
    id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    filename = Column(String(255))
    s3_path = Column(String(500))
    transcribed_text = Column(Text)
    language = Column(String(10), default='ar')
    confidence = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(50), default='completed')
    created_at = Column(DateTime, default=datetime.utcnow)

class AudioGeneration(Base):
    """Text-to-speech generation records"""
    __tablename__ = 'audio_generations'
    
    id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    input_text = Column(Text)
    language = Column(String(10), default='ar')
    voice = Column(String(50), default='default')
    s3_path = Column(String(500), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(50), default='completed')
    created_at = Column(DateTime, default=datetime.utcnow)
