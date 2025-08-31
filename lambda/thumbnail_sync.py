import boto3
import json
import os
from datetime import datetime
from PIL import Image
import io

s3_client = boto3.client('s3')

def handler(event, context):
    try:
        print("=== THUMBNAIL SYNC FUNCTION STARTED ===")
        # Get bucket name from environment variable
        bucket_name = os.environ['BUCKET_NAME']
        
        # Source folders to check for images
        source_folders = ['usortert', 'ai-training-data/with-mail', 'ai-training-data/without-mail']
        
        # Get all images from source folders
        source_images = {}
        for folder in source_folders:
            try:
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=folder + '/',
                    MaxKeys=1000
                )
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        if key.endswith('.jpg'):
                            # Extract filename without folder path
                            filename = key.split('/')[-1]
                            source_images[filename] = key
                            print(f"Found source image: {filename}")
            except Exception as e:
                print(f"Error listing objects in {folder}: {str(e)}")
        
        # Get all thumbnails
        thumbnails = {}
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix='thumbnails/',
                MaxKeys=1000
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('-thumbnail.jpg'):
                        # Extract original filename from thumbnail name
                        # e.g., "thumbnails/2025-08-31-17-35-thumbnail.jpg" -> "2025-08-31-17-35.jpg"
                        # Remove the thumbnails/ prefix first, then replace -thumbnail.jpg with .jpg
                        filename_without_prefix = key.replace('thumbnails/', '')
                        original_filename = filename_without_prefix.replace('-thumbnail.jpg', '.jpg')
                        thumbnails[original_filename] = key
                        print(f"Found thumbnail: {key} -> {original_filename}")
        except Exception as e:
            print(f"Error listing thumbnails: {str(e)}")
        
        print(f"Source images: {list(source_images.keys())}")
        print(f"Thumbnails: {list(thumbnails.keys())}")
        
        # Create missing thumbnails
        created_count = 0
        for filename, source_key in source_images.items():
            if filename not in thumbnails:
                try:
                    print(f"Creating thumbnail for missing: {filename}")
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
                    
                    # Create thumbnail filename
                    thumbnail_filename = filename.replace('.jpg', '-thumbnail.jpg')
                    thumbnail_key = f'thumbnails/{thumbnail_filename}'
                    
                    # Upload thumbnail
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=thumbnail_key,
                        Body=thumbnail_bytes,
                        ContentType='image/jpeg'
                    )
                    
                    # Add the newly created thumbnail to the thumbnails dictionary
                    # Use the original filename as the key, not the thumbnail filename
                    thumbnails[filename] = thumbnail_key
                    
                    created_count += 1
                    print(f"Created thumbnail: {thumbnail_key} for {filename}")
                    
                except Exception as e:
                    print(f"Error creating thumbnail for {source_key}: {str(e)}")
        
        print(f"After creation - Source images: {list(source_images.keys())}")
        print(f"After creation - Thumbnails: {list(thumbnails.keys())}")
        
        # Delete orphaned thumbnails
        deleted_count = 0
        for thumbnail_filename, thumbnail_key in thumbnails.items():
            if thumbnail_filename not in source_images:
                try:
                    print(f"Deleting orphaned thumbnail: {thumbnail_key} (source: {thumbnail_filename} not found)")
                    s3_client.delete_object(
                        Bucket=bucket_name,
                        Key=thumbnail_key
                    )
                    deleted_count += 1
                    print(f"Deleted orphaned thumbnail: {thumbnail_key}")
                except Exception as e:
                    print(f"Error deleting thumbnail {thumbnail_key}: {str(e)}")
            else:
                print(f"Keeping thumbnail: {thumbnail_key} (source: {thumbnail_filename} exists)")
        
        print("=== THUMBNAIL SYNC FUNCTION COMPLETED ===")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Thumbnail sync completed',
                'thumbnails_created': created_count,
                'thumbnails_deleted': deleted_count,
                'source_images_checked': len(source_images),
                'thumbnails_checked': len(thumbnails)
            })
        }
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
