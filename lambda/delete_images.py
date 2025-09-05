import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def _response(status_code: int, body: dict):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps(body)
    }


def handler(event, context):
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            try:
                body = json.loads(event['body'])
            except Exception:
                return _response(400, {'success': False, 'error': 'Invalid JSON in request body'})
        else:
            body = event.get('body') or {}

        image_keys = body.get('imageKeys', [])

        if not image_keys or not isinstance(image_keys, list):
            return _response(400, {'success': False, 'error': 'imageKeys must be a non-empty array'})

        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        logger.info(f"Deleting {len(image_keys)} originals from bucket {bucket_name}")

        deleted = 0
        errors = []

        for key in image_keys:
            # Only delete original JPGs; do not touch thumbnails
            if not key.lower().endswith('.jpg'):
                logger.info(f"Skipping non-jpg key: {key}")
                continue
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=key)
                deleted += 1
            except ClientError as e:
                msg = f"Failed to delete {key}: {str(e)}"
                logger.error(msg)
                errors.append(msg)

        return _response(200, {
            'success': True,
            'deletedCount': deleted,
            'errorCount': len(errors),
            'errors': errors
        })

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return _response(500, {'success': False, 'error': f'Internal server error: {str(e)}'})


