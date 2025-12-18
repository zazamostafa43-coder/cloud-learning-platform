# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set work directory
WORKDIR /app
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities
COPY services/common ./services/common

# Copy service code
COPY services/chat_service ./services/chat_service

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Run the service
CMD ["python", "services/chat_service/main.py"]
