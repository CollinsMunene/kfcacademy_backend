#!/bin/bash
export DEBUG=True
fuser -k 8000/tcp
cd /home/eliud/apps/fpc/
# rm -r output.out
# rm -r django_debug.log
# rm -r venv
# python3 -m venv venv
. venv/bin/activate
# pip3 install -r requirements.txt
# python3 -m pip install -U pip setuptools
# systemctl stop celery
# pkill -f 'celery'
# systemctl start celery
# python3 manage.py collectstatic
# sudo cp  -r /root/FPCAcademy_backend/staticfiles/* /var/www/FPCAcademy_backend/staticfiles/
# sudo chown -R www-data:www-data /var/www/FPCAcademy_backend/staticfiles
# sudo chmod -R 755 /var/www/FPCAcademy_backend/staticfiles
python3 manage.py makemigrations  && python3 manage.py migrate
# python manage.py auto_create_dpias --ids 65 66 67 70 71 72 23 73 --user 8b76cb6b-963b-42ed-9d99-a3af94fb65d4
# python manage.py generate_permissions
# python manage.py update_application_owner
# celery -A FPCAcademy_backend worker --loglevel=info --logfile=celery.log --detach
ps aux | grep '[c]elery' | awk '{print $2}' | xargs -r kill -9
celery -A KFCAcademy worker --loglevel=info --detach
nohup env DEBUG=True gunicorn --workers 3 --timeout 1800 --bind 0:8000 KFCAcademy.wsgi:application >> output.out &
# python manage.py runserver 0.0.0.0:8800
