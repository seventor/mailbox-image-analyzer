import json
import boto3
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)
lambda_client = boto3.client('lambda')

def handler(event, context):
    """
    Trigger the median image creation function
    """
    try:
        # Get the function name from environment or construct it
        function_name = os.environ.get('MEDIAN_FUNCTION_NAME')
        if not function_name:
            # Construct function name based on environment
            environment = os.environ.get('ENVIRONMENT', 'dev')
            function_name = f"MailboxImageAnalyzerStack-{environment}-CreateMedianImageFunction"
        
        logger.info(f"Triggering median image creation function: {function_name}")
        
        # Invoke the median image creation function
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({})
        )
        
        logger.info(f"Successfully triggered median image creation. Response: {response}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Median image creation triggered successfully',
                'functionName': function_name,
                'invocationType': 'Event'
            })
        }
        
    except Exception as e:
        logger.error(f"Error triggering median image creation: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'success': False,
                'error': f'Failed to trigger median image creation: {str(e)}'
            })
        }
