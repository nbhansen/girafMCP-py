# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GIRAF_DATA_DIR=/app/data
ENV CHROMA_PERSIST_DIR=/app/chroma_data
ENV GIRAF_MCP_HOST=0.0.0.0
ENV GIRAF_MCP_PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies (if needed, e.g. for building some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .[http]

# Copy project files
COPY . .

# Create directories for data persistence
RUN mkdir -p data chroma_data

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application in HTTP mode
# Note: Users can override this to use stdio mode by changing the CMD
ENTRYPOINT ["giraf-mcp"]
CMD ["--http"]
