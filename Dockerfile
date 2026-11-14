FROM python:3.12-slim

# System dependencies for Pillow and ONNX Runtime (rembg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure model directory is deterministic
ENV U2NET_HOME=/app/.u2net
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download rembg birefnet-general-lite model at build time (~224MB)
# This prevents downloading on every container cold start in Railway
RUN python -c "from rembg import new_session; new_session('birefnet-general-lite')"

# Copy application source
COPY . .

# Create volume/storage mount points
RUN mkdir -p /data/images/raw /data/images/processed

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
