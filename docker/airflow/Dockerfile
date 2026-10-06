FROM apache/airflow:3.3.2-python3.12

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/railflow-venv \
    && /opt/railflow-venv/bin/python -m pip install --upgrade pip \
    && /opt/railflow-venv/bin/pip install \
        "pyspark==4.2.0" \
        "PyYAML==6.0.2" \
        "requests>=2.32,<3.0" \
        "dbt-core==1.12.5" \
        "dbt-duckdb==1.11.0" \
        "duckdb==1.5.6"

RUN chown -R airflow:0 /opt/railflow-venv

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="/opt/railflow-venv/bin:${PATH}"

USER airflow

WORKDIR /opt/airflow
# STAGE 8C ML LIFECYCLE DEPENDENCIES
USER root

COPY requirements-ml.txt /tmp/railflow-requirements-ml.txt
COPY requirements-serving.txt /tmp/railflow-requirements-serving.txt

RUN /opt/railflow-venv/bin/python -m pip install --no-cache-dir \
        -r /tmp/railflow-requirements-ml.txt \
        -r /tmp/railflow-requirements-serving.txt \
    && /opt/railflow-venv/bin/python -m pip check

USER airflow