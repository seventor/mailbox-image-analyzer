import boto3
import json
import os
from datetime import datetime, timezone

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Get the folder from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        folder = query_params.get('folder', 'usortert')
        
        # Validate folder parameter
        allowed_folders = ['usortert', 'ai-training-data/with-mail', 'ai-training-data/without-mail', 'uploads', 'median-image', 'status']
        if folder not in allowed_folders:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({'error': 'Invalid folder parameter'})
            }
        
        # List objects in the specified folder
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=folder + '/',
            MaxKeys=1000
        )
        
        images = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.jpg') and not key.endswith('-thumbnail.jpg'):
                    # Extract filename without folder path
                    filename = key.split('/')[-1]
                    base_name = filename.replace('.jpg', '')
                    
                    # Check if thumbnail actually exists
                    thumbnail_key = None
                    try:
                        s3_client.head_object(Bucket=bucket_name, Key=f'thumbnails/{base_name}-thumbnail.jpg')
                        thumbnail_key = f'thumbnails/{base_name}-thumbnail.jpg'
                    except:
                        # No thumbnail exists, set to None
                        thumbnail_key = None
                    
                    # Extract date from filename (YYYY-MM-DD-HH-MM format)
                    date_obj = extract_date_from_filename(base_name)
                    
                    # If filename parsing fails, use S3 LastModified as fallback
                    fallback_date = obj.get('LastModified')
                    if fallback_date:
                        fallback_date = fallback_date.replace(tzinfo=timezone.utc)
                    
                    images.append({
                        'original': key,
                        'thumbnail': thumbnail_key,
                        'name': base_name,
                        'date': date_obj.isoformat() if date_obj else (fallback_date.isoformat() if fallback_date else None),
                        'size': obj.get('Size', 0),
                        'lastModified': obj.get('LastModified', '').isoformat() if obj.get('LastModified') else None
                    })
        
        # Sort by date (newest first)
        images.sort(key=lambda x: x['date'] or '', reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'images': images,
                'folder': folder,
                'count': len(images)
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

def extract_date_from_filename(filename):
    """Extract date from filename like '2025-08-31-17-35' and return as UTC datetime"""
    try:
        import re
        match = re.match(r'(\d{4}-\d{2}-\d{2}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
            year, month, day, hour, minute = map(int, date_str.split('-'))
            # Create UTC datetime object
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except:
        pass
    return None
