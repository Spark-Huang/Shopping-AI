FROM python:3.11-slim

WORKDIR /app

COPY search/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY search ./search
COPY crawler ./crawler
COPY ./platform/configs/search ./platform/configs/search
COPY ./platform/data ./platform/data

EXPOSE 8010

CMD ["uvicorn", "search.app.main:app", "--host", "0.0.0.0", "--port", "8010"]
