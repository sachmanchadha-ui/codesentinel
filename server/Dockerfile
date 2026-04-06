FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    pydantic \
    websockets \
    openai \
    python-dotenv \
    httpx \
    openenv-core

COPY models.py .
COPY client.py .
COPY inference.py .
COPY openenv.yaml .
COPY server/ ./server/

EXPOSE 7860

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]