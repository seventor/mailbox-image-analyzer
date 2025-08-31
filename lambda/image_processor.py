import boto3
import json
import os
from datetime import datetime
from PIL import Image
import io

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
        
        # Create thumbnail using PIL
        image = Image.open(io.BytesIO(image_data))
        
        # Calculate new height maintaining aspect ratio (128px wide)
        width, height = image.size
        new_width = 128
        new_height = int((height * new_width) / width)
        
        # Resize image
        thumbnail = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert thumbnail to bytes
        thumbnail_buffer = io.BytesIO()
        thumbnail.save(thumbnail_buffer, format='JPEG', quality=85)
        thumbnail_bytes = thumbnail_buffer.getvalue()
        
        # Upload thumbnail to thumbnails folder
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f'thumbnails/{timestamp}-thumbnail.jpg',
            Body=thumbnail_bytes,
            ContentType='image/jpeg'
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image processed successfully',
                'timestamp': timestamp,
                'current_minute': current_minute,
                'original_file': 'uploads/latest.jpg',
                'copied_file': f'usortert/{timestamp}.jpg',
                'thumbnail_file': f'thumbnails/{timestamp}-thumbnail.jpg'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
