FROM quay.io/pypa/manylinux_2_28_x86_64

ARG BLPAPI_VERSION=3.25.12.1

RUN dnf install -y clang-devel git \
    && dnf clean all

RUN mkdir -p /opt/blpapi \
    && curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
        | tar -xz -C /opt/blpapi --strip-components=1 \
    && ln -sf /opt/blpapi/Linux /opt/blpapi/lib \
    && ln -sf /opt/blpapi/lib/libblpapi3_64.so /opt/blpapi/lib/libblpapi3.so

ENV BLPAPI_ROOT=/opt/blpapi
ENV LIBRARY_PATH=/opt/blpapi/lib:${LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/opt/blpapi/lib:${LD_LIBRARY_PATH}
