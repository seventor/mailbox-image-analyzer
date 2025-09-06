import boto3
import json
import os

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Folders to check
        folders = [
            'usortert', 
            'ai-training-data/training/with-mail', 
            'ai-training-data/training/without-mail',
            'ai-training-data/evaluation/with-mail', 
            'ai-training-data/evaluation/without-mail',
            'ai-training-data/test/with-mail', 
            'ai-training-data/test/without-mail'
        ]
        stats = {}
        
        for folder in folders:
            try:
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=folder + '/',
                    MaxKeys=1000
                )
                
                # Count only .jpg files (excluding thumbnails)
                count = 0
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        if key.endswith('.jpg') and not key.endswith('-thumbnail.jpg'):
                            count += 1
                
                stats[folder] = count
                
            except Exception as e:
                print(f"Error getting count for {folder}: {str(e)}")
                stats[folder] = 0
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'stats': stats,
                'total': sum(stats.values())
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({'error': str(e)})
        }
