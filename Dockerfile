FROM mcr.microsoft.com/playwright/python:v1.57.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=4173 CHROMIUM_PATH=/ms-playwright/chromium-1200/chrome-linux64/chrome
EXPOSE 4173
CMD ["sh", "-c", "uvicorn autoqa.app:app --host 0.0.0.0 --port ${PORT}"]
