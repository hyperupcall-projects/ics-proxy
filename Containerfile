FROM docker.io/library/python:3.13-slim-trixie
ARG UID GID USER=app
ENV PORT=3000

RUN groupadd --gid ${GID} ${USER} \
    && useradd --uid ${UID} --gid ${GID} --create-home ${USER}
WORKDIR /app
USER ${USER}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN python -m pip install --no-cache-dir --upgrade pip && \
   pip install uv

EXPOSE ${PORT}
CMD ["bash", "--login", "-c", "uv run gunicorn --bind 0.0.0.0:$PORT --workers 2 ics_proxy:app"]
