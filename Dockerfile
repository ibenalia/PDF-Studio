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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure build directory exists
RUN mkdir -p cppeditor/build

# Compile the C++ PDF editor
RUN cd cppeditor && make

# Create data directory structure
RUN mkdir -p /app/data/uploads /app/data/temp /app/data/processed \
    && chmod -R 777 /app/data

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data

# Expose port for the web server
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0"] 