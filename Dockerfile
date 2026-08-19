FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Copy remaining files
COPY .env.example .env.example

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "ripplegraph.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
