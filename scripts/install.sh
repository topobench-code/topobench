#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

apt-get update
apt-get install -y --no-install-recommends \
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
