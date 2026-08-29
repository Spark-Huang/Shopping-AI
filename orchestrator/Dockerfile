
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and config
COPY orchestrator/app ./app
COPY ./platform/configs/orchestrator ./platform/configs/orchestrator
COPY ./platform/data ./platform/data

# Set environment variables
ENV PYTHONPATH=/app
ENV SHARED_CONFIG_ROOT=/app/platform/configs
ENV LLM_API_KEY=${LLM_API_KEY}
ENV SAFETY_BASE_URL=http://safety:8012

# Expose the port the app runs on
EXPOSE 8009

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009", "--reload"]
