# Architecture Documentation

## System Architecture

The Cloud-Based Learning Platform follows a microservices architecture pattern with the following key components:

## Component Overview

```
                                   ┌──────────────┐
                                   │   USERS      │
                                   └──────┬───────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          PUBLIC LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 Application Load Balancer (ALB)                  │   │
│  │                        Port 80/443                               │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼──────────────────────────────────┐   │
│  │                      FRONTEND (React)                            │   │
│  │                         Port 3000                                │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────────┐
│                          GATEWAY LAYER                                  │
│  ┌──────────────────────────────▼──────────────────────────────────┐   │
│  │                     API GATEWAY (FastAPI)                        │   │
│  │                         Port 8000                                │   │
│  │  - Rate Limiting   - CORS   - Service Discovery   - Logging     │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────────┐
│                         SERVICES LAYER                                  │
│     ┌───────┬───────┬──────────┼───────────┬───────────┐               │
│     ▼       ▼       ▼          ▼           ▼           │               │
│  ┌─────┐ ┌─────┐ ┌─────┐  ┌───────┐   ┌───────┐       │               │
│  │ STT │ │ TTS │ │ DOC │  │ CHAT  │   │ QUIZ  │       │               │
│  │8001 │ │8002 │ │8003 │  │ 8004  │   │ 8005  │       │               │
│  └──┬──┘ └──┬──┘ └──┬──┘  └───┬───┘   └───┬───┘       │               │
│     │       │       │         │           │           │               │
│     └───────┴───────┴─────────┼───────────┘           │               │
│                               │                       │               │
└───────────────────────────────┼───────────────────────┘               │
                                │                                        │
┌───────────────────────────────┼────────────────────────────────────────┘
│                         EVENT LAYER                                    │
│  ┌────────────────────────────▼────────────────────────────────────┐   │
│  │                    APACHE KAFKA                                  │   │
│  │                    Port 9092                                     │   │
│  │  Topics: audio.*, document.*, quiz.*, chat.*, notes.*           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│              │                                                         │
│  ┌───────────▼────────────┐                                           │
│  │       ZOOKEEPER        │                                           │
│  │       Port 2181        │                                           │
│  └────────────────────────┘                                           │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                   │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │
│   │   PostgreSQL    │   │      S3         │   │     Redis       │     │
│   │   Port 5432     │   │  (AWS Storage)  │   │   Port 6379     │     │
│   │                 │   │                 │   │   (Cache)       │     │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
```

## Service Details

### 1. STT Service (Speech-to-Text)
- **Port**: 8001
- **Technology**: FastAPI, SpeechRecognition/Whisper
- **Storage**: S3 (audio files), PostgreSQL (metadata)
- **Kafka Topics**: 
  - Produces: `audio.transcription.completed`
  - Consumes: `audio.transcription.requested`

### 2. TTS Service (Text-to-Speech)
- **Port**: 8002
- **Technology**: FastAPI, gTTS
- **Storage**: S3 (generated audio)
- **Kafka Topics**:
  - Produces: `audio.generation.completed`
  - Consumes: `audio.generation.requested`

### 3. Document Service
- **Port**: 8003
- **Technology**: FastAPI, PyPDF2, python-docx
- **Storage**: S3 (documents), PostgreSQL (metadata)
- **Kafka Topics**:
  - Produces: `document.uploaded`, `document.processed`, `notes.generated`

### 4. Chat Service
- **Port**: 8004
- **Technology**: FastAPI, Knowledge Base
- **Storage**: S3 (conversation archives), PostgreSQL
- **Kafka Topics**:
  - Produces: `chat.message`
  - Consumes: `document.processed`

### 5. Quiz Service
- **Port**: 8005
- **Technology**: FastAPI, Question Banks
- **Storage**: S3 (quiz templates), PostgreSQL (results)
- **Kafka Topics**:
  - Produces: `quiz.generated`
  - Consumes: `quiz.requested`, `notes.generated`

## Data Flow

### Document Processing Flow
```
User Uploads PDF → Document Service → S3 Storage
                           ↓
                    Text Extraction
                           ↓
                   Kafka (document.processed)
                           ↓
              ┌────────────┴────────────┐
              ↓                         ↓
         Chat Service              Quiz Service
    (adds to knowledge)        (generates questions)
```

### Quiz Generation Flow
```
Quiz Request → Quiz Service → Check Document Context
                    ↓
              Generate Questions
                    ↓
              Store in S3/DB
                    ↓
              Kafka (quiz.generated)
                    ↓
              Return to User
```

## AWS Infrastructure

### VPC Design
```
VPC: 10.0.0.0/16
├── Public Subnets (ALB)
│   ├── 10.0.1.0/24 (us-east-1a)
│   └── 10.0.2.0/24 (us-east-1b)
├── Private Subnets (Services)
│   ├── 10.0.10.0/24 (us-east-1a)
│   └── 10.0.11.0/24 (us-east-1b)
├── Data Subnets (RDS)
│   ├── 10.0.20.0/24 (us-east-1a)
│   └── 10.0.21.0/24 (us-east-1b)
└── Kafka Subnets
    ├── 10.0.30.0/24 (us-east-1a)
    └── 10.0.31.0/24 (us-east-1b)
```

### S3 Buckets
| Bucket | Purpose |
|--------|---------|
| stt-service-storage-dev | Audio files for transcription |
| tts-service-storage-dev | Generated audio files |
| document-reader-storage-dev | Uploaded documents |
| chat-service-storage-dev | Conversation archives |
| quiz-service-storage-dev | Quiz templates |
| shared-assets-dev | Static assets |

## Security Architecture

### Network Security
- ALB in public subnets only
- Services in private subnets
- RDS in isolated data subnets
- NAT Gateway for outbound access

### Security Groups
1. **ALB SG**: Allows 80/443 from internet
2. **Services SG**: Allows 8000-8005 from ALB
3. **RDS SG**: Allows 5432 from Services
4. **Kafka SG**: Allows 9092 from Services

### Data Security
- S3: Server-side encryption (AES-256)
- RDS: Encryption at rest
- All traffic: TLS in transit
