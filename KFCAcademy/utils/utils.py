from datetime import timedelta

# Async ActionLogs creation for audit logging
import logging
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

from django.template.loader import render_to_string
from celery import shared_task
from django.core.mail import get_connection,EmailMultiAlternatives
from jinja2 import Environment, FileSystemLoader
import requests
from django.db.models import F, Func, Value, CharField
from django.contrib.postgres.fields import ArrayField

from minio import Minio
from minio.error import S3Error
from django.conf import settings
logger = logging.getLogger('django')


import os
import json

# Cloudflare Stream API configuration
CLOUDFLARE_STREAM_VIDEO_UPLOAD_URL = os.getenv('CLOUDFLARE_STREAM_VIDEO_UPLOAD_URL', 'https://api.cloudflare.com/client/v4/accounts/befb832641959f6fce604ecb85380a33/stream')
CLOUDFLARE_STREAM_IMAGE_UPLOAD_URL = os.getenv('CLOUDFLARE_STREAM_IMAGE_UPLOAD_URL', 'https://api.cloudflare.com/client/v4/accounts/befb832641959f6fce604ecb85380a33/images/v1')
CLOUDFLARE_STREAM_VIDEO_DELETE_URL = os.getenv('CLOUDFLARE_STREAM_VIDEO_DELETE_URL', 'https://api.cloudflare.com/client/v4/accounts/befb832641959f6fce604ecb85380a33/stream/')
CLOUDFLARE_STREAM_IMAGE_DELETE_URL = os.getenv('CLOUDFLARE_STREAM_IMAGE_DELETE_URL', 'https://api.cloudflare.com/client/v4/accounts/befb832641959f6fce604ecb85380a33/images/v1')
CLOUDFLARE_STREAM_API_TOKEN = os.getenv('CLOUDFLARE_STREAM_API_TOKEN', 'RIXX-DWThGADZGwmmOhfmoGe_zuXely7nXWXKdl6')

file_prefix = ''
if settings.DEBUG:
    file_prefix = 'dev_'

    
bucket_name = settings.MINIO_STORAGE_BUCKET_NAME
minio_client = Minio(
    '127.0.0.1:9000',
    access_key=settings.MINIO_STORAGE_ACCESS_KEY,
    secret_key=settings.MINIO_STORAGE_SECRET_KEY,
    secure=False,  # nginx handles SSL
    region='us-east-1',  # Prevent region lookup
)

def get_from_minio(file_path):
    try:
        print(f"Generating presigned URL for file: {file_path}, bucket: {bucket_name}")
        
        # Generate presigned URL (will use localhost)
        url = minio_client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=file_path,
            expires=timedelta(hours=1),
            response_headers={
                "response-content-disposition": f'inline;'
            }
        )
        
        # Replace localhost with public nginx proxy URL
        url = url.replace('127.0.0.1:9000', settings.MINIO_PUBLIC_ENDPOINT)
        url = url.replace('http://', 'https://')
        
        print(f"Generated presigned URL: {url}")
        return url
    except Exception as err:
        print(f"MinIO Error: {err}")
        raise




def upload_image_to_cloudflare_task(file_data, file_name):
    try:
        # Validate file type from extension
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type or not mime_type.startswith("image"):
            logger.error(f"Invalid file type for image upload: {mime_type}")
            return None

        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_STREAM_API_TOKEN}"
        }
        
        # Write bytes to temporary file for upload
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name
        
        try:
            with open(tmp_path, "rb") as f:
                response = requests.post(
                    CLOUDFLARE_STREAM_IMAGE_UPLOAD_URL,
                    headers=headers,
                    files={"file": (file_prefix + file_name, f)},
                    timeout=30
                )

            response.raise_for_status()
            response_data = response.json()
            print(response_data)

            if response.status_code == 200 and response_data.get("success"):

                file_url = response_data.get("result", {}).get("variants", [None])[0]
                if not file_url:
                    logger.error(f"'variants' key missing in response: {response_data}")
                    return None

                return file_url
            else:
                logger.error(f"Failed to upload image: {response_data.get('errors')}")
                return None
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.exception(f"Error uploading image to Cloudflare: {str(e)}")
        return None


def upload_video_to_cloudflare_task(file_data, file_name):
    """Upload video to Cloudflare Stream and update ModuleTopics."""
    try:
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type or not mime_type.startswith("video"):
            logger.error(f"Invalid file type for video upload: {mime_type}")
            return None

        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_STREAM_API_TOKEN}"
        }

        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                response = requests.post(
                    CLOUDFLARE_STREAM_VIDEO_UPLOAD_URL,
                    headers=headers,
                    files={"file": (file_prefix + file_name, f)},
                    timeout=60
                )
                
            response.raise_for_status()
            response_data = response.json()

            if response.status_code == 200 and response_data.get("success"):
                file_url = response_data.get("result", {}).get("playback", {}).get("hls")
                if not file_url:
                    logger.error(f"'playback' key missing in response: {response_data}")
                    return None
                return file_url
            else:
                logger.error(f"Failed to upload video: {response_data.get('errors')}")
                return None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.exception(f"Error uploading video to Cloudflare: {str(e)}")
        return None


def delete_cloudflare_file_task(file_url, resource_type):
    try:
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_STREAM_API_TOKEN}"
        }
        if resource_type == 'image':
            # Extract image ID from URL (second-to-last segment)
            image_id = file_url.split("/")[-2]
            delete_url = f"{CLOUDFLARE_STREAM_IMAGE_DELETE_URL}/{image_id}"
        elif resource_type == 'video':
            # Extract video ID from URL (second-to-last segment)
            video_id = file_url.split("/")[-3]
            delete_url = f"{CLOUDFLARE_STREAM_VIDEO_DELETE_URL}{video_id}"
        else:
            logger.error(f"Invalid resource type for deletion: {resource_type}")
            return False
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Failed to delete file from Cloudflare: {response.text}")
            return False
    except S3Error as e:
        logger.error(f"Failed to delete file from Cloudflare: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Error deleting file from Cloudflare: {str(e)}")
        return False









def upload_file_to_minio_task(file_data, file_name):
    try:
        bucket_name = settings.MINIO_STORAGE_BUCKET_NAME
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            minio_client.fput_object(bucket_name, file_name, tmp_path)
            file_url = f"{bucket_name}/{file_name}"

            return file_url
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except S3Error as e:
        logger.error(f"Failed to upload file to MinIO: {str(e)}")
        return None
    except Exception as e:
        logger.exception(f"Error uploading file to MinIO: {str(e)}")
        return None


def delete_file_from_minio_task(file_name):
    """Delete file from MinIO and update ModuleTopics."""
    try:
        bucket_name = settings.MINIO_STORAGE_BUCKET_NAME
        # let's strip the file_name from the /bucket_name/filename format
        if file_name.startswith(f"{bucket_name}/"):
            delete_file_name = file_name[len(f"{bucket_name}/"):]

        minio_client.remove_object(bucket_name, delete_file_name)

        return True
                
    except S3Error as e:
        logger.error(f"Failed to delete file from MinIO: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Error deleting file from MinIO: {str(e)}")
        return False