web: gunicorn --pythonpath mergify mergify.wsgi -b 0.0.0.0:$PORT --capture-output
worker: python manage.py qcluster
release: python manage.py makemigrations
release: python manage.py migrate