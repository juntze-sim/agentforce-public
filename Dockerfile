# AgentForce — containerised CLI runner.
# The app runs in this container; the LLM (Ollama) runs on the HOST machine,
# reached via host.docker.internal.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    OLLAMA_MODEL=qwen3:8b

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "run.py"]
