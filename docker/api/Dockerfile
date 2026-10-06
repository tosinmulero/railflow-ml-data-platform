FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 railflow \
    && useradd \
       --uid 10001 \
       --gid railflow \
       --create-home \
       railflow

COPY requirements-serving.txt /app/requirements-serving.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install \
       -r /app/requirements-serving.txt

COPY api /app/api
COPY config /app/config

COPY reports/ml/deployment_manifest.json /app/reports/ml/deployment_manifest.json

COPY models/deployment /app/models/deployment

COPY mlflow/mlflow.db /app/mlflow/mlflow.db

RUN chown -R railflow:railflow /app

USER railflow

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]