FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv

# Copy requirements and install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run as non-root user
RUN useradd -m nonroot
USER nonroot

# Run server
CMD ["python", "server.py"]
