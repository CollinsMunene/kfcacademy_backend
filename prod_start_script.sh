# #!/bin/bash
# export DEBUG=False
# fuser -k 8000/tcp
# cd /home/eliud/apps/kfc/
# rm -r output.out
# rm -r django_debug.log
# rm -r venv
# python3 -m venv venv
# . venv/bin/activate
# pip3 install -r requirements.txt
# python3 -m pip install -U pip setuptools
# pip3 install gunicorn

# # systemctl stop celery
# # pkill -f 'celery'
# # systemctl start celery
# # python3 manage.py collectstatic
# # sudo cp  -r /root/FPCAcademy_backend/staticfiles/* /var/www/kfc/staticfiles/
# # sudo chown -R www-data:www-data /var/www/kfc/staticfiles
# # sudo chmod -R 755 /var/www/kfc/staticfiles
# # python3 manage.py makemigrations  && python3 manage.py migrate
# # celery -A FPCAcademy_backend worker --loglevel=info --logfile=celery.log --detach
# ps aux | grep '[c]elery' | awk '{print $2}' | xargs -r kill -9
# celery -A KFCAcademy worker --loglevel=info --detach
# nohup env DEBUG=False gunicorn --workers 3 --timeout 1800 --bind 0:8000 KFCAcademy.wsgi:application >> output.out &
# # python manage.py runserver 0.0.0.0:8000
