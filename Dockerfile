FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy exporter code
COPY exporter.py .

# Expose Prometheus metrics port
EXPOSE 9090

# Run the exporter
CMD ["python", "exporter.py"]
