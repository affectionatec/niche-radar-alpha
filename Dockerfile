# syntax=docker/dockerfile:1
FROM docker.1panel.live/library/python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --timeout 120 \
    --retries 5 \
    -i https://mirrors.huaweicloud.com/repository/pypi/simple/ \
    --trusted-host mirrors.huaweicloud.com \
    --extra-index-url https://pypi.mirrors.ustc.edu.cn/simple/ \
    --trusted-host pypi.mirrors.ustc.edu.cn \
    -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/reports

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "niche_radar"]
CMD ["serve"]
