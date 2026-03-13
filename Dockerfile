FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Node 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build
COPY src/frontend/package*.json src/frontend/
WORKDIR /app/src/frontend
RUN npm ci
COPY src/frontend/ .
RUN npm run build

# Back to root
WORKDIR /app
COPY . .

# Data directories
RUN mkdir -p data/models data/predictions data/journal

# Expose port
EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
