#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEBIAN_MIRROR="${DEBIAN_MIRROR:-https://ftp.us.debian.org/debian}"
DEBIAN_SECURITY_MIRROR="${DEBIAN_SECURITY_MIRROR:-https://security.debian.org/debian-security}"

sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list || true
sed -i "s|https://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list || true
sed -i "s|http://security.debian.org|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list || true
sed -i "s|https://security.debian.org|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list || true
if ls /etc/apt/sources.list.d/*.list >/dev/null 2>&1; then
  sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/*.list
  sed -i "s|https://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/*.list
  sed -i "s|http://security.debian.org|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/*.list
  sed -i "s|https://security.debian.org|${DEBIAN_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/*.list
fi

APT_ARGS=(
  -o Acquire::Retries=5
  -o Acquire::http::Timeout=30
  -o Acquire::https::Timeout=30
)

apt-get update "${APT_ARGS[@]}"
apt-get install -y --no-install-recommends "${APT_ARGS[@]}" \
  ca-certificates \
  build-essential \
  cmake \
  gcc \
  git \
  imagemagick \
  libgtk-3-dev \
  pkg-config
rm -rf /var/lib/apt/lists/*

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "${ROOT_DIR}"
python -m pip install "pygame>=2.1.0"

pushd "${ROOT_DIR}/submodules/rlp" >/dev/null
python setup.py build_ext --inplace
popd >/dev/null

mkdir -p "${ROOT_DIR}/submodules/rlp/rlp/lib"
pushd "${ROOT_DIR}/submodules/rlp/rlp/lib" >/dev/null
cmake ../../puzzles
make -j"$(nproc)" libbridges libgalaxies libloopy libpattern libundead
popd >/dev/null

pushd "${ROOT_DIR}/submodules/flowfree" >/dev/null
gcc -std=c11 -O2 -Wall -Wextra -o flowfree_all_solutions flowfree_all_solutions.c
popd >/dev/null

echo "TopoBench install complete."
