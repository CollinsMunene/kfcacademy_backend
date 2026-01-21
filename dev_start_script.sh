#!/bin/bash
export DEBUG=True
fuser -k 8005/tcp
cd /root/kfc/
rm -r output.out
rm -r django_debug.log
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
ps aux | grep '[c]elery' | awk '{print $2}' | xargs -r kill -9
celery -A KFCAcademy worker --loglevel=info --detach
nohup env DEBUG=True gunicorn --workers 3 --timeout 1800 --bind 0:8005 KFCAcademy.wsgi:application >> output.out &
