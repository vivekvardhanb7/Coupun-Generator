FROM python:3.11-slim

# Install minimal system dependencies for Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxshmfence1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Let Playwright use system Chromium
ENV PLAYWRIGHT_BROWSERS_PATH=0
ENV CHROME_BIN=/usr/bin/chromium

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (browser already present)
RUN playwright install chromium

# Copy application code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app1.py", "--server.port=8501", "--server.address=0.0.0.0"]
