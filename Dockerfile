FROM python:3.12.10-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system --no-cache -r pyproject.toml
COPY . .
EXPOSE 8000
CMD [ "python", "main.py" ]