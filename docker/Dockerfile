FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN bash scripts/install.sh

CMD ["python", "evals/src/main.py", "--help"]
