ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS runtime

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app
WORKDIR /app

ENTRYPOINT ["python", "-m", "netskope_collector"]

FROM python:${PYTHON_VERSION}-bookworm AS dev

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      iputils-ping less docker.io unzip curl groff jq && \
    curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install && \
    rm -rf /var/lib/apt/lists/* awscliv2.zip aws/

COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements-dev.txt

WORKDIR /workspace
CMD ["sleep", "infinity"]
