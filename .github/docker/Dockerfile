# Build environment for xbbg with Bloomberg C++ SDK
#
# This image includes:
# - Rust stable toolchain with clippy and rustfmt
# - Python 3 with uv
# - Bloomberg C++ SDK (latest version, auto-detected)
# - Build tools (gcc, make, clang for bindgen)

FROM rust:bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    clang \
    libclang-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust components
RUN rustup component add clippy rustfmt

# Install uv and add to PATH
ENV PATH="/root/.local/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Download and install Bloomberg C++ SDK (latest version detected from PyPI index)
RUN BLPAPI_VERSION=$(curl -s https://blpapi.bloomberg.com/repository/releases/python/simple/blpapi/ \
        | grep -oP 'blpapi-\K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1) \
    && echo "Installing Bloomberg SDK version: $BLPAPI_VERSION" \
    && mkdir -p /opt/blpapi \
    && curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
    | tar -xz -C /opt/blpapi --strip-components=1

# Set Bloomberg SDK environment variables
ENV BLPAPI_ROOT=/opt/blpapi
ENV LD_LIBRARY_PATH=/opt/blpapi/lib:$LD_LIBRARY_PATH

# Install Python tools via uv
RUN uv tool install ruff \
    && uv tool install maturin \
    && uv pip install --system \
        pytest \
        pytest-cov \
        pyarrow \
        pandas \
        numpy

# Create workspace directory
WORKDIR /workspace

# Labels
LABEL org.opencontainers.image.source="https://github.com/alpha-xone/xbbg"
LABEL org.opencontainers.image.description="Build environment for xbbg with Bloomberg SDK"
