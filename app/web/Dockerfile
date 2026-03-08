# Debian slim: pre-built wheels for psutil, no gcc needed
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8080

# Run app.py when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-", "app:app"]