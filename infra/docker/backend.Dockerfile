FROM python:3.12-slim

WORKDIR /app
COPY apps/backend/pyproject.toml apps/backend/README.md ./
COPY apps/backend/src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "firesight_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
