FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cache bust: 2026-07-10-v3
LABEL build_version="2026-07-10-v3"

CMD ["python", "main.py"]
