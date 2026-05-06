FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . /app

ARG DEBIAN_MIRROR=https://ftp.us.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=https://security.debian.org/debian-security
ENV DEBIAN_MIRROR=${DEBIAN_MIRROR}
ENV DEBIAN_SECURITY_MIRROR=${DEBIAN_SECURITY_MIRROR}

RUN bash scripts/install.sh

CMD ["python", "/bin/bash", "--help"]
