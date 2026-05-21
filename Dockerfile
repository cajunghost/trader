FROM python:3.12-slim

WORKDIR /app
COPY . .

ENV HOST=0.0.0.0
ENV PORT=10000
ENV TRADER_DB_PATH=/data/trader.sqlite3

RUN mkdir -p /data

EXPOSE 10000
CMD ["sh", "-c", "python -m option_ai_tool.server --host 0.0.0.0 --port ${PORT:-10000}"]
