FROM python:3.12-slim

RUN addgroup --system apm && adduser --system --ingroup apm apm
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER apm
ENTRYPOINT ["apm-mcp-server"]

