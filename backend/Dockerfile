FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency file
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

# Copy source code
COPY . .

# Copy scenarios
COPY ../scenarios /app/scenarios

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
