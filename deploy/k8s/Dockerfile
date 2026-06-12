FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/blockchain-bench

COPY . /opt/blockchain-bench

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt/blockchain-bench/monitoring

RUN chmod +x /opt/blockchain-bench/monitoring/cgroup_collector.py

CMD ["python3", "/opt/blockchain-bench/monitoring/cgroup_collector.py", "--header"]
