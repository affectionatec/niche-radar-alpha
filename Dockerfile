# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout 120 \
    --retries 5 \
    -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/reports

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "niche_radar"]
CMD ["serve"]
