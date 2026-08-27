FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "langgraph-checkpoint-redis>=0.5,<1"
COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
