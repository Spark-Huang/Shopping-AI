# Use an official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY safety/requirements.txt .
RUN apt-get update && apt-get install -y gcc g++ python3-dev
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY safety/app ./app
COPY ./platform/configs/safety ./platform/configs/safety

ENV PYTHONPATH=/app:/app/platform/configs/safety

# Expose port
EXPOSE 8012

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8012"]
