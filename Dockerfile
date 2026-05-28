FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first so pip never fetches NVIDIA/CUDA packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

# Guard: fail build if any CUDA/GPU packages leak in
RUN pip list 2>/dev/null | grep -qiE "nvidia|cuda|cudnn|cublas|cufft|triton" && { echo "FATAL: CUDA/GPU packages found"; exit 1; } || echo "PASS: No CUDA/GPU packages"

EXPOSE 8000

ENV PORT=8000
ENV HF_HUB_OFFLINE=0
ENV TRANSFORMERS_OFFLINE=0

CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
