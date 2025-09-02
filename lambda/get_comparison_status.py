import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def handler(event, context):
    try:
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        
        # Get model name from query parameters or default to ModelA
        model_name = 'ModelA'  # Default model
        if 'queryStringParameters' in event and event['queryStringParameters']:
            model_name = event['queryStringParameters'].get('model', 'ModelA')
        
        # Use model-specific file names
        latest_compare_key = f'status/{model_name.lower()}.json'
        statistics_key = f'status/statistics-{model_name.lower()}.json'
        
        # Get latest comparison
        try:
            latest_response = s3_client.get_object(Bucket=bucket_name, Key=latest_compare_key)
            latest_data = json.loads(latest_response['Body'].read())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                latest_data = None
            else:
                raise e
        
        # Get statistics
        try:
            statistics_response = s3_client.get_object(Bucket=bucket_name, Key=statistics_key)
            statistics_data = json.loads(statistics_response['Body'].read())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                statistics_data = {
                    'model_name': model_name,
                    'total_comparisons': 0,
                    'last_updated': None,
                    'comparisons': []
                }
            else:
                raise e
        
        result = {
            'success': True,
            'model_name': model_name,
            'latest_comparison': latest_data,
            'statistics': statistics_data
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, OPTIONS'
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting comparison status: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, OPTIONS'
            }
        }
