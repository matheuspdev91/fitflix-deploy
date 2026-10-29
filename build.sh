#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# CRIAR SUPERUSER AUTOMATICO
export DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-123456}"

python manage.py createsuperuser \
  --noinput \
  --username admin \
  --email admin@email.com || true

# SEED.PY
python manage.py seed_exercicios 
