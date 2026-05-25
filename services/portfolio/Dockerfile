FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8003
CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8003"]
