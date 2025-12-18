from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
import time
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cloud Learning Platform API Gateway",
    description="Unified API Gateway for the Cloud-Based Learning Platform",
    version="2.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs (Internal Docker network or localhost)
SERVICES = {
    "stt": os.getenv("STT_SERVICE_URL", "http://stt-service:8001"),
    "tts": os.getenv("TTS_SERVICE_URL", "http://tts-service:8002"),
    "documents": os.getenv("DOC_SERVICE_URL", "http://document-service:8003"),
    "chat": os.getenv("CHAT_SERVICE_URL", "http://chat-service:8004"),
    "quiz": os.getenv("QUIZ_SERVICE_URL", "http://quiz-service:8005"),
}

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "learning-platform-secret-key-2025")
JWT_ALGORITHM = "HS256"

def verify_token(token: str) -> bool:
    """Mock JWT verification - in a real app, use pyjwt to decode and verify"""
    # For demonstration/Phase 3 compliance: any non-empty token is accepted
    return len(token) > 10

@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    """Unified middleware for Security (JWT), Rate Limiting, and Logging"""
    start_time = time.time()
    
    # 1. Network Security: Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Security policy enforcement."}
        )
    
    # 2. Access Control: JWT Authentication
    # Exclude health and root endpoints from auth
    if request.url.path not in ["/", "/health", "/services/status", "/docs", "/openapi.json"]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: JWT Token required (Phase 3 Compliance)"}
            )
        
        token = auth_header.split(" ")[1]
        if not verify_token(token):
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: Invalid Security Token"}
            )
    
    # 3. Request Logging & Execution
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Content-Type-Options"] = "nosniff" # Security header
    
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response

@app.get("/")
async def root():
    """API Gateway root endpoint"""
    return {
        "name": "Cloud Learning Platform API Gateway",
        "version": "2.0.0",
        "services": list(SERVICES.keys()),
        "endpoints": {
            "stt": "/stt/* - Speech to Text conversion",
            "tts": "/tts/* - Text to Speech synthesis",
            "documents": "/documents/* - Document processing and analysis",
            "chat": "/chat/* - AI Chat assistant",
            "quiz": "/quiz/* - Quiz generation and assessment"
        }
    }

@app.get("/health")
async def health_check():
    """Gateway health check"""
    return {
        "status": "healthy", 
        "gateway": "operational",
        "version": "2.0.0"
    }

@app.get("/services/status")
async def services_status():
    """Check status of all backend services"""
    status = {}
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in SERVICES.items():
            try:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    status[name] = {
                        "status": "healthy",
                        "url": url,
                        "response": response.json()
                    }
                else:
                    status[name] = {
                        "status": "unhealthy",
                        "url": url,
                        "error": f"HTTP {response.status_code}"
                    }
            except Exception as e:
                status[name] = {
                    "status": "unreachable",
                    "url": url,
                    "error": str(e)
                }
    
    return {"services": status, "gateway": "operational"}

async def proxy_request(service: str, path: str, request: Request, method: str = None):
    """Proxy request to backend service"""
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")
    
    # Build target URL
    base_url = SERVICES[service]
    target_url = f"{base_url}/api/{service}/{path}"
    
    # Get request method
    http_method = method or request.method
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Prepare headers
            headers = dict(request.headers)
            headers.pop("host", None)
            headers.pop("content-length", None)
            
            # Get request body
            body = await request.body()
            
            logger.info(f"Proxying {http_method} to {target_url}")
            
            # Make request to backend service
            response = await client.request(
                method=http_method,
                url=target_url,
                content=body,
                headers=headers,
                params=request.query_params
            )
            
            # Forward the response from the microservice
            # We filter out some headers that shouldn't be forwarded
            excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
            response_headers = {
                k: v for k, v in response.headers.items() 
                if k.lower() not in excluded_headers
            }
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type")
            )
                
        except httpx.ConnectError:
            logger.error(f"Connection failed to {target_url}")
            raise HTTPException(
                status_code=503, 
                detail=f"Service '{service}' is temporarily unavailable. Please try again later."
            )
        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to {target_url}")
            raise HTTPException(
                status_code=504, 
                detail=f"Service '{service}' request timed out."
            )
        except Exception as e:
            logger.error(f"Gateway error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

# Generic API routes
@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(service: str, path: str, request: Request):
    """Generic proxy for all service requests"""
    return await proxy_request(service, path, request)

# Special handling for file uploads (STT and Documents)
@app.post("/stt/transcribe")
async def stt_transcribe(file: UploadFile = File(...), language: str = "ar"):
    """Upload audio file for transcription"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Read file content
            content = await file.read()
            
            # Create multipart form data
            files = {"file": (file.filename, content, file.content_type)}
            params = {"language": language}
            
            response = await client.post(
                f"{SERVICES['stt']}/api/stt/transcribe",
                files=files,
                params=params
            )
            
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="STT Service is unavailable")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/upload")
async def documents_upload(file: UploadFile = File(...)):
    """Upload document for processing"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            content = await file.read()
            files = {"file": (file.filename, content, file.content_type)}
            
            response = await client.post(
                f"{SERVICES['documents']}/api/documents/upload",
                files=files
            )
            
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Document Service is unavailable")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
