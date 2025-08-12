
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN git clone --depth=1 https://github.com/ashtadhyayi-com/data /app/data
COPY app.py /app/app.py
ENV PORT=8080
CMD ["bash","-lc","uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
