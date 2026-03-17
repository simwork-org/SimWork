FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency file and install
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -e .

# Copy backend source
COPY . .

# Copy scenarios (mounted or built from root context)
# For Railway: scenarios are included via root build context or volume

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
