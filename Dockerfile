FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including PoDoFo
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    make \
    cmake \
    libpodofo-dev \
    libcurl4-openssl-dev \
    python3-magic \
    gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN groupadd -r pdfeditor && useradd -r -g pdfeditor pdfeditor

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure build directory exists
RUN mkdir -p cppeditor/build

# Compile the C++ PDF editor
RUN cd cppeditor && make

# Create data directory structure with secure permissions
RUN mkdir -p /app/data/uploads /app/data/temp /app/data/processed \
    && chown -R pdfeditor:pdfeditor /app/data \
    && chmod -R 750 /app/data

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data

# Configure runtime user and permissions
RUN chown -R pdfeditor:pdfeditor /app/bin \
    && chmod -R 750 /app/bin

# Expose port for the web server
EXPOSE 5000

# Use a startup script to handle permissions and user switching
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]

# Run the application with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "run:app"] 