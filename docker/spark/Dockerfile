FROM spark:4.2.0-scala2.13-java17-python3-ubuntu

USER root

# RailFlow configuration files are YAML-based.
# Install PyYAML through Ubuntu's package manager to avoid
# modifying the system Python environment with pip.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-yaml \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV PYSPARK_PYTHON=/usr/bin/python3
ENV PYSPARK_DRIVER_PYTHON=/usr/bin/python3

USER spark