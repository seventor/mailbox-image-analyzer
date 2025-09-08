import json
import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)
lambda_client = boto3.client('lambda')

def handler(event, context):
    try:
        function_name = os.environ.get('COMPARISON_FUNCTION_NAME')
        if not function_name:
            environment = os.environ.get('ENVIRONMENT', 'dev')
            function_name = f"MailboxImageAnalyzerStack-{environment}-CompareLatestWithMedianFunction"
        
        logger.info(f"Triggering comparison function: {function_name}")
        
        # Run all four models: ModelA, ModelB, ModelC, ModelD
        models = ['ModelA', 'ModelB', 'ModelC', 'ModelD']
        results = []
        
        for model_name in models:
            logger.info(f"Triggering {model_name} comparison")
            
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',
                Payload=json.dumps({
                    'model_name': model_name
                })
            )
            
            results.append({
                'model': model_name,
                'status': 'triggered'
            })
            
            logger.info(f"Successfully triggered {model_name} comparison")
        
        logger.info(f"Successfully triggered all {len(models)} comparison models")
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'success': True,
                'message': f'All {len(models)} comparison models triggered successfully',
                'functionName': function_name,
                'invocationType': 'Event',
                'models_triggered': models,
                'results': results
            })
        }
    except Exception as e:
        logger.error(f"Error triggering comparison: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'success': False,
                'error': f'Failed to trigger comparison: {str(e)}'
            })
        }
