import boto3
import json
import os
from datetime import datetime, timezone

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Get HTTP method
        http_method = event.get('httpMethod', 'GET')
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        model_name = query_params.get('model', '').lower()
        
        # Validate model parameter
        allowed_models = ['modela', 'modelb', 'modelc', 'modeld']
        if model_name not in allowed_models:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Invalid model parameter. Must be "modela", "modelb", "modelc", or "modeld"'})
            }
        
        # Construct the statistics file key
        statistics_key = f'status/statistics-{model_name}.json'
        
        if http_method == 'GET':
            # Fetch the statistics JSON file
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=statistics_key)
                content = response['Body'].read().decode('utf-8')
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                    },
                    'body': content
                }
            except s3_client.exceptions.NoSuchKey:
                # File doesn't exist, return empty array
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                    },
                    'body': json.dumps([])
                }
        
        elif http_method == 'POST':
            # Save the statistics JSON file
            try:
                # Parse the request body
                body = event.get('body', '')
                if not body:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type',
                            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                        },
                        'body': json.dumps({'error': 'No body provided'})
                    }
                
                                # Validate JSON
                try:
                    data = json.loads(body)
                    
                    # Handle both array format and object format with comparisons array
                    if isinstance(data, list):
                        # Direct array format - use as is
                        comparisons_array = data
                    elif isinstance(data, dict) and 'comparisons' in data:
                        # Object format with comparisons array - extract the array
                        comparisons_array = data['comparisons']
                        if not isinstance(comparisons_array, list):
                            return {
                                'statusCode': 400,
                                'headers': {
                                    'Content-Type': 'application/json',
                                    'Access-Control-Allow-Origin': '*',
                                    'Access-Control-Allow-Headers': 'Content-Type',
                                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                                },
                                'body': json.dumps({'error': 'Data must be a JSON array or object with comparisons array'})
                            }
                    else:
                        return {
                            'statusCode': 400,
                            'headers': {
                                'Content-Type': 'application/json',
                                'Access-Control-Allow-Origin': '*',
                                'Access-Control-Allow-Headers': 'Content-Type',
                                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                            },
                            'body': json.dumps({'error': 'Data must be a JSON array or object with comparisons array'})
                        }
                except json.JSONDecodeError:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Headers': 'Content-Type',
                            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                        },
                        'body': json.dumps({'error': 'Invalid JSON format'})
                    }
                
                # Save to S3
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=statistics_key,
                    Body=json.dumps(data, indent=2),  # Save the original format
                    ContentType='application/json',
                    Metadata={
                        'last_modified': datetime.now(timezone.utc).isoformat(),
                        'model': model_name
                    }
                )
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                    },
                    'body': json.dumps({
                        'message': f'Statistics for {model_name} saved successfully',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                }
                
            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                    },
                    'body': json.dumps({'error': f'Failed to save statistics: {str(e)}'})
                }
        
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({'error': str(e)})
        }
