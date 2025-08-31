import boto3
import json
import os
from datetime import datetime
from PIL import Image
import io
from thumbnail_utils import create_thumbnail

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        # Get current time
        now = datetime.now()
        current_minute = now.minute
        
        # Check if current minute is between 55-59 or 00-04
        if not (current_minute >= 55 or current_minute <= 4):
            # Do nothing if not in the specified time window
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Image processing skipped - not in processing window',
                    'current_minute': current_minute,
                    'processing_window': 'minutes 55-59 or 00-04'
                })
            }
        
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Get the current timestamp for filename
        timestamp = now.strftime('%Y-%m-%d-%H-%M')
        
        # Download the latest.jpg file from S3
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key='uploads/latest.jpg'
        )
        image_data = response['Body'].read()
        
        # Copy to usortert folder with timestamped filename
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f'usortert/{timestamp}.jpg',
            Body=image_data,
            ContentType='image/jpeg'
        )
        
        # Create thumbnail using shared utility
        thumbnail_key = f'thumbnails/{timestamp}-thumbnail.jpg'
        thumbnail_result = create_thumbnail(bucket_name, f'usortert/{timestamp}.jpg', thumbnail_key)
        
        if not thumbnail_result['success']:
            print(f"Error creating thumbnail: {thumbnail_result['error']}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to create thumbnail: {thumbnail_result["error"]}'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image processed successfully',
                'timestamp': timestamp,
                'current_minute': current_minute,
                'original_file': 'uploads/latest.jpg',
                'copied_file': f'usortert/{timestamp}.jpg',
                'thumbnail_file': thumbnail_key,
                'thumbnail_dimensions': thumbnail_result['dimensions']
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
