FROM python:3.11-slim

WORKDIR /app

# Install system deps that some Python packages need
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first — leverages Docker layer caching so
# rebuilds are fast when only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (gets overridden by volume mount in dev,
# but baked in for production builds)
COPY ./src ./src

# Default command — overridden by docker-compose for hot-reload
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]