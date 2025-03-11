FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make the data directory if it doesn't exist and set proper permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Host on all interfaces for Docker
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 5000

CMD ["python", "app.py"]