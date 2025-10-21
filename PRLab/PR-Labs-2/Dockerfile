FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy server files
COPY server.py .
COPY server_single.py .
COPY client.py .
COPY concurrency_test.py .

# Create content directory
RUN mkdir -p /app/content
RUN mkdir -p /app/downloads

# Copy content files
COPY content/ /app/content/

# Expose port
EXPOSE 8080

# Default command
CMD ["python", "server.py", "/app/content", "--counter-mode", "safe", "--rate-limit", "5", "--rate-window", "1.0"]