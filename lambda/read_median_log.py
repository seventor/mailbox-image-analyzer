import json
import boto3
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Read the median image creation log file
    """
    try:
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        log_key = 'median-image/log.json'
        
        logger.info(f"Reading median image log from {bucket_name}/{log_key}")
        
        try:
            # Try to get the log file
            response = s3_client.get_object(Bucket=bucket_name, Key=log_key)
            log_content = response['Body'].read().decode('utf-8')
            log_data = json.loads(log_content)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS'
                },
                'body': json.dumps({
                    'success': True,
                    'logExists': True,
                    'logData': log_data
                })
            }
            
        except s3_client.exceptions.NoSuchKey:
            # Log file doesn't exist
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS'
                },
                'body': json.dumps({
                    'success': True,
                    'logExists': False,
                    'message': 'No median image log file found. Create a median image first.'
                })
            }
            
    except Exception as e:
        logger.error(f"Error reading median image log: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, OPTIONS'
            },
            'body': json.dumps({
                'success': False,
                'error': f'Failed to read median image log: {str(e)}'
            })
        }
