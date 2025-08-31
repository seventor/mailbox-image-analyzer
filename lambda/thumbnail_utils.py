import boto3
import json
import os
from PIL import Image
import io

s3_client = boto3.client('s3')

def create_thumbnail(bucket_name, source_key, thumbnail_key):
    """
    Create a thumbnail from a source image and upload it to S3.
    
    Args:
        bucket_name (str): S3 bucket name
        source_key (str): S3 key of the source image
        thumbnail_key (str): S3 key where the thumbnail should be saved
    
    Returns:
        dict: Result with success status and any error message
    """
    try:
        # Download the source image
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key=source_key
        )
        image_data = response['Body'].read()
        
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
        
        # Upload thumbnail
        s3_client.put_object(
            Bucket=bucket_name,
            Key=thumbnail_key,
            Body=thumbnail_bytes,
            ContentType='image/jpeg'
        )
        
        return {
            'success': True,
            'message': f'Thumbnail created successfully: {thumbnail_key}',
            'thumbnail_key': thumbnail_key,
            'dimensions': f'{new_width}x{new_height}'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'source_key': source_key,
            'thumbnail_key': thumbnail_key
        }
