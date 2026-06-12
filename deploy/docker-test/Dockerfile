ARG UBUNTU_IMAGE=ubuntu:latest
FROM ${UBUNTU_IMAGE}

ARG GO_VERSION=1.26.4
ARG TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/go/bin:/root/bin:/root/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    wget \
    git \
    jq \
    bc \
    gawk \
    build-essential \
    make \
    gcc \
    tar \
    gzip \
    xz-utils \
    python3 \
    python3-pip \
    python3-venv \
    sysstat \
    net-tools \
    procps \
    iproute2 \
    lsof \
    tini \
  && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
  arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
  case "$arch" in \
    amd64|x86_64) goarch="amd64" ;; \
    arm64|aarch64) goarch="arm64" ;; \
    *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
  esac; \
  curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${goarch}.tar.gz" -o /tmp/go.tgz; \
  rm -rf /usr/local/go; \
  tar -C /usr/local -xzf /tmp/go.tgz; \
  rm -f /tmp/go.tgz; \
  go version

WORKDIR /tmp/bnb-build
COPY requirements.txt /tmp/bnb-build/requirements.txt
COPY scripts/install_deps.sh /tmp/bnb-build/scripts/install_deps.sh
RUN bash scripts/install_deps.sh --yes --no-sudo \
  && rm -rf /tmp/bnb-build

WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
