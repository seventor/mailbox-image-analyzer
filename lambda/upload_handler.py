import boto3
import json
import base64
import os
from datetime import datetime

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Get the body and check if it's base64 encoded
        body = event['body']
        is_base64_encoded = event.get('isBase64Encoded', False)
        
        if is_base64_encoded:
            # API Gateway base64 encoded the binary data
            image_bytes = base64.b64decode(body)
        else:
            # Raw binary data - convert to bytes if it's a string
            if isinstance(body, str):
                image_bytes = body.encode('latin-1')
            else:
                image_bytes = body
        
        # Upload to S3 in the uploads folder
        s3_client.put_object(
            Bucket=bucket_name,
            Key='uploads/latest.jpg',
            Body=image_bytes,
            ContentType='image/jpeg'
        )
        
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
