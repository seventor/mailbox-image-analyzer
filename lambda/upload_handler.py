import boto3
import json
import base64
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def handler(event, context):
    try:
        logger.info(f"Upload request received: {event.get('httpMethod', 'Unknown')}")
        
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        logger.info(f"Using bucket: {bucket_name}")
        
        # Get the body and check if it's base64 encoded
        body = event['body']
        is_base64_encoded = event.get('isBase64Encoded', False)
        logger.info(f"Body length: {len(body)}, is_base64_encoded: {is_base64_encoded}")
        
        if is_base64_encoded:
            # API Gateway base64 encoded the binary data
            image_bytes = base64.b64decode(body)
            logger.info(f"Decoded base64 image, size: {len(image_bytes)} bytes")
        else:
            # Raw binary data - convert to bytes if it's a string
            if isinstance(body, str):
                image_bytes = body.encode('latin-1')
                logger.info(f"Converted string to bytes, size: {len(image_bytes)} bytes")
            else:
                image_bytes = body
                logger.info(f"Using raw body, size: {len(image_bytes)} bytes")
        
        # Upload to S3 in the uploads folder
        logger.info(f"Uploading to S3: {bucket_name}/uploads/latest.jpg")
        s3_client.put_object(
            Bucket=bucket_name,
            Key='uploads/latest.jpg',
            Body=image_bytes,
            ContentType='image/jpeg',
            CacheControl='no-store',  # Simple and robust
            Metadata={
                'uploaded-at': datetime.now().isoformat()
            }
        )
        logger.info("Upload completed successfully")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST,OPTIONS'
            },
            'body': json.dumps({'message': 'Image uploaded successfully'})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST,OPTIONS'
            },
            'body': json.dumps({'error': str(e)})
        }
