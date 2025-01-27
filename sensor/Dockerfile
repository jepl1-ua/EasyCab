FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CENTRAL_HOST=central
ENV CENTRAL_PORT=8443
CMD ["python", "sensor.py"]
