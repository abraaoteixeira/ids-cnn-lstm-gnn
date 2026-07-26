FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    gcc \
    python3-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt (from root)
COPY requirements.txt .

# Install python dependencies
# Clean out heavy CUDA/ML/DeepLearning packages to keep the image lightweight and buildable
RUN grep -E -v "cu12|cuda|nvidia|cupy|cuml|cudf|cucim|cuvs|torch|tensorflow|jax|tensorboard" requirements.txt > requirements_clean.txt \
    && pip install --no-cache-dir -r requirements_clean.txt \
    && pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic websockets

# Copy necessary files (dashboard_api_v2.py, backend/, and other relevant assets)
COPY dashboard_api_v2.py .
COPY backend/ ./backend/

# Expose port 8001
EXPOSE 8001

# Run FastAPI via uvicorn
CMD ["uvicorn", "dashboard_api_v2:app", "--host", "0.0.0.0", "--port", "8001"]
