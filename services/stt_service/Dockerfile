# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set work directory
WORKDIR /app
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common utilities
COPY services/common ./services/common

# Copy service code (passed as build arg or context)
COPY services/stt_service ./services/stt_service

# Expose port
EXPOSE 8001

# Run the service
CMD ["python", "services/stt_service/main.py"]
