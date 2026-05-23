FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY parser.py bot.py ./
RUN mkdir -p /app/data /app/tmp && chmod 700 /app/data

CMD ["python", "bot.py"]
