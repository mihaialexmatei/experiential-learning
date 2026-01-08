FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Setup Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3
RUN python -m pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set Hugging Face token
ARG HF_TOKEN
ENV HF_TOKEN=${HF_TOKEN}

# Download models in Azure (fast!)
RUN python3 -c "from huggingface_hub import snapshot_download; \
    print('Downloading FLUX.1-dev...'); \
    snapshot_download( \
        repo_id='black-forest-labs/FLUX.1-dev', \
        local_dir='/app/models/flux', \
        local_dir_use_symlinks=False, \
        token='${HF_TOKEN}' \
    ); \
    print('FLUX.1-dev downloaded successfully')"

RUN python3 -c "from huggingface_hub import snapshot_download; \
    print('Downloading DiT360 adapter...'); \
    snapshot_download( \
        repo_id='Insta360-Research/DiT360-Panorama-Image-Generation', \
        local_dir='/app/models/dit360', \
        local_dir_use_symlinks=False, \
        token='${HF_TOKEN}' \
    ); \
    print('DiT360 adapter downloaded successfully')"

# Copy application
COPY app.py .

# Configure environment
EXPOSE 8080
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models
ENV HF_HUB_OFFLINE=1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
