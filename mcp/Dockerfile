# Glean Commons public front door (hosted MCP endpoint).
# Public mode only: it holds no one's data and has nothing to write to.
#
#   docker build -f mcp/Dockerfile -t glean-commons .
#   docker run -p 8000:8000 glean-commons
#   -> http://localhost:8000/mcp   (health: /health)
#
# Most hosts (Fly.io, Render, Railway, Cloud Run) set $PORT; this respects it.
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN useradd --create-home glean && chown -R glean /app
USER glean
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "python3 mcp/server.py --public --front-door --http ${PORT} --host 0.0.0.0 ${GLEAN_ALLOW_ORIGINS}"]
