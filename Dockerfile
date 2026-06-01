# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into the user's local directory
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production runner stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime PostgreSQL dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder stage
COPY --from=builder /root/.local /root/.local
COPY . /app

# Ensure user binaries are in PATH and Python buffers correctly
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start the uvicorn API gateway server
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
