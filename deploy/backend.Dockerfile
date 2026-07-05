# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS backend
WORKDIR /app

# System deps for PyMuPDF (mupdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libglib2.0-0 libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/

# Storage volume
RUN mkdir -p /app/storage/pdfs /app/storage/labels

ENV PYTHONUNBUFFERED=1 \
    PORT=8001

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
