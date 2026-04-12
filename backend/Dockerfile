FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY database/migrations/ ./migrations/

EXPOSE 8000
CMD ["bash", "start.sh"]
