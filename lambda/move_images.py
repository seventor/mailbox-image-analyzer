import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Move images between S3 folders.
    
    Expected event structure:
    {
        "sourceFolder": "usortert",
        "targetFolder": "ai-training-data/with-mail",
        "imageKeys": ["2025-01-15-10-30.jpg", "2025-01-15-11-45.jpg"]
    }
    """
    
    try:
        # Parse request body
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
        
        source_folder = body.get('sourceFolder')
        target_folder = body.get('targetFolder')
        image_keys = body.get('imageKeys', [])
        
        # Validate input
        if not source_folder or not target_folder or not image_keys:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing required parameters: sourceFolder, targetFolder, or imageKeys'
                })
            }
        
        # Validate folder names
        allowed_folders = ['usortert', 'ai-training-data/with-mail', 'ai-training-data/without-mail']
        if source_folder not in allowed_folders or target_folder not in allowed_folders:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Invalid folder names. Allowed: usortert, ai-training-data/with-mail, ai-training-data/without-mail'
                })
            }
        
        # Get bucket name from environment
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        
        logger.info(f"Moving {len(image_keys)} images from {source_folder} to {target_folder} in bucket {bucket_name}")
        
        moved_count = 0
        errors = []
        
        for image_key in image_keys:
            try:
                # The image_key already contains the full path (e.g., "usortert/2025-08-31-17-36.jpg")
                # So we use it directly as the source key
                source_key = image_key
                
                # For the target, we need to replace the source folder with the target folder
                # Extract just the filename from the source key
                filename = image_key.split('/')[-1]
                target_key = f"{target_folder}/{filename}"
                
                logger.info(f"Processing image: {source_key} -> {target_key}")
                
                # Check if source image exists
                try:
                    s3_client.head_object(Bucket=bucket_name, Key=source_key)
                    logger.info(f"Source image found: {source_key}")
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        error_msg = f"Source image not found: {source_key}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        continue
                    else:
                        raise
                
                # Copy image to target folder
                copy_source = {'Bucket': bucket_name, 'Key': source_key}
                logger.info(f"Copying {source_key} to {target_key}")
                s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=bucket_name,
                    Key=target_key
                )
                logger.info(f"Copy successful: {source_key} -> {target_key}")
                
                # Delete from source folder
                logger.info(f"Deleting source: {source_key}")
                s3_client.delete_object(Bucket=bucket_name, Key=source_key)
                logger.info(f"Delete successful: {source_key}")
                
                moved_count += 1
                logger.info(f"Successfully moved {source_key} to {target_key}")
                
            except Exception as e:
                error_msg = f"Failed to move {image_key}: {str(e)}"
                logger.error(error_msg)
                logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
                errors.append(error_msg)
        
        # Prepare response
        if errors:
            return {
                'statusCode': 207,  # Multi-status
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'success': True,
                    'movedCount': moved_count,
                    'errorCount': len(errors),
                    'errors': errors,
                    'message': f"Moved {moved_count} images with {len(errors)} errors"
                })
            }
        else:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'success': True,
                    'movedCount': moved_count,
                    'message': f"Successfully moved {moved_count} images"
                })
            }
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            })
        }
