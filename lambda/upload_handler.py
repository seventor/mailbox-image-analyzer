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
        
        # API Gateway automatically base64 encodes binary data
        # We need to decode it back to binary
        image_bytes = base64.b64decode(event['body'])
        
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
