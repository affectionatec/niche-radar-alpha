FROM docker.1panel.live/library/python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/reports

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "niche_radar"]
CMD ["serve"]
