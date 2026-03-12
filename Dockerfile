FROM python:3.12-slim

WORKDIR /app

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/
COPY data/ data/
COPY .env* ./

# Expose ports: Streamlit (8501) + FastAPI (8000)
EXPOSE 8501 8000

# Default: run Streamlit
CMD ["streamlit", "run", "src/app/main.py", "--server.headless", "true", "--server.address", "0.0.0.0"]
