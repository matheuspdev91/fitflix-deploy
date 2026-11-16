
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    ffmpeg \
    gifsicle \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/fitflix

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN ls -la /opt/fitflix && test -f /opt/fitflix/manage.py
RUN test -f /opt/fitflix/projeto/wsgi.py

EXPOSE 80


CMD ["sh", "-c", "python manage.py collectstatic --noinput && exec gunicorn projeto.wsgi:application --bind 0.0.0.0:80 --access-logfile - --error-logfile - --log-level info"]
