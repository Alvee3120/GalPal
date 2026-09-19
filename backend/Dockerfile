FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect static files (admin, Swagger UI) with throwaway values; real ones come at runtime.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=build-only ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

RUN useradd --create-home app && mkdir -p /app/media && chown -R app:app /app/media
USER app

EXPOSE 8000

# Production entrypoint. Run `python manage.py migrate` as a separate release step.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
