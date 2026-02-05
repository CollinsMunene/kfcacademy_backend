#!/bin/bash
export DEBUG=False
fuser -k 8000/tcp
cd /apps/kfc/
rm  output.out
rm  django_debug.log
rm -r venv
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt
python3 -m pip install -U pip setuptools
systemctl stop celery
pkill -f 'celery'
systemctl start celery
# python3 manage.py collectstatic --noinput
# sudo cp  -r /root/kfc/staticfiles/* /var/www/kfc/staticfiles/
# sudo chown -R www-data:www-data /var/www/kfc/staticfiles
# sudo chmod -R 755 /var/www/kfc/staticfiles
# python manage.py makemigrations --merge
# python3 manage.py makemigrations  && python3 manage.py migrate
python3 manage.py makemigrations --noinput && python3 manage.py migrate --noinput
# celery -A cropcare worker --loglevel=info --logfile=celery.log --detach
sudo ps aux | grep '[c]elery' | awk '{print $2}' | sudo xargs -r kill -9
# DEBUG=False celery -A CropCare worker --loglevel=info --detach
DEBUG=False celery -A KFCAcademy worker \
    --loglevel=INFO \
    --logfile=/home/lina/apps/kfc/celery.log \
    --pidfile=/home/lina/apps/kfc/celery.pid \
    --detach
pkill -f "python manage.py heartbeat"
nohup env DEBUG=False gunicorn --workers 3 --timeout 1800 --bind 0:8000 KFCAcademy.wsgi:application >> output.out &
# python manage.py classify_fsc_tiers
nohup python manage.py heartbeat &
echo "KFCAcademy Production Server Started"