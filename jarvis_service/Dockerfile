FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OPENJARVIS_HOME=/var/lib/jarvis/openjarvis
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY jarvis_service/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt && pip check
COPY jarvis_service /app/jarvis_service
RUN useradd --uid 10001 --create-home jarvis && mkdir -p /var/lib/jarvis && chown -R jarvis:jarvis /var/lib/jarvis
EXPOSE 10000
ENTRYPOINT ["python", "/app/jarvis_service/entrypoint.py"]
CMD ["uvicorn", "jarvis_service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "10000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
