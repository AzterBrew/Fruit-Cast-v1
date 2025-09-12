web: gunicorn fruitcast.wsgi:application
worker: celery -A fruitcast worker --loglevel=info # re-commit