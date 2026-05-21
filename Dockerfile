FROM python:3.12-slim

WORKDIR /app
COPY . .

ENV HOST=0.0.0.0
ENV PORT=8080
ENV TRADER_DB_PATH=/data/trader.sqlite3

RUN mkdir -p /data

EXPOSE 8080
CMD ["python", "-m", "option_ai_tool.server"]

