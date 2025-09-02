import json
import boto3
import logging
import os
from datetime import datetime, timezone
import numpy as np
from PIL import Image
import io
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def handler(event, context):
    """
    Create a median image from the latest 7 images in the without-mail folder.
    The median image represents an average of how the mailbox looks without mail.
    """
    
    try:
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        source_folder = 'ai-training-data/without-mail'
        target_folder = 'median-image'
        target_filename = 'median.jpg'
        num_images = 7
        
        logger.info(f"Starting median image creation from {source_folder}")
        logger.info(f"Will use latest {num_images} images to create median")
        
        # List objects in the without-mail folder
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=source_folder + '/',
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                logger.warning(f"No images found in {source_folder}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': True,
                        'message': f'No images found in {source_folder}',
                        'medianCreated': False
                    })
                }
            
            # Filter for .jpg files and sort by LastModified (newest first)
            jpg_files = []
            for obj in response['Contents']:
                if obj['Key'].endswith('.jpg') and not obj['Key'].endswith('-thumbnail.jpg'):
                    jpg_files.append(obj)
            
            # Sort by LastModified (newest first)
            jpg_files.sort(key=lambda x: x['LastModified'], reverse=True)
            
            if len(jpg_files) == 0:
                logger.warning(f"No JPG images found in {source_folder}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': True,
                        'message': f'No JPG images found in {source_folder}',
                        'medianCreated': False
                    })
                }
            
            # Take the latest num_images
            latest_images = jpg_files[:num_images]
            logger.info(f"Found {len(latest_images)} images to process")
            
            if len(latest_images) < 3:
                logger.warning(f"Not enough images ({len(latest_images)}) to create meaningful median. Need at least 3.")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': True,
                        'message': f'Not enough images ({len(latest_images)}) to create meaningful median',
                        'medianCreated': False
                    })
                }
            
            # Download and process images
            image_arrays = []
            image_sizes = []
            
            for i, obj in enumerate(latest_images):
                try:
                    logger.info(f"Processing image {i+1}/{len(latest_images)}: {obj['Key']}")
                    
                    # Download image from S3
                    response = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                    image_data = response['Body'].read()
                    
                    # Open with PIL
                    image = Image.open(io.BytesIO(image_data))
                    
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    
                    # Resize to a standard size for consistent processing
                    # Use the same size as the source images (1024x576)
                    target_size = (1024, 576)  # Match source image dimensions
                    image = image.resize(target_size, Image.Resampling.LANCZOS)
                    
                    # Convert to numpy array
                    img_array = np.array(image)
                    image_arrays.append(img_array)
                    image_sizes.append(img_array.shape)
                    
                    logger.info(f"Successfully processed image {i+1}: {img_array.shape}")
                    
                except Exception as e:
                    logger.error(f"Error processing image {obj['Key']}: {str(e)}")
                    continue
            
            if len(image_arrays) < 3:
                logger.error("Not enough successfully processed images to create median")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'success': False,
                        'error': 'Not enough successfully processed images to create median'
                    })
                }
            
            # Create median image
            logger.info(f"Creating median from {len(image_arrays)} images")
            median_array = np.median(image_arrays, axis=0).astype(np.uint8)
            
            # Convert back to PIL Image
            median_image = Image.fromarray(median_array)
            
            # Save to bytes
            img_buffer = io.BytesIO()
            median_image.save(img_buffer, format='JPEG', quality=85)
            img_buffer.seek(0)
            
            # Upload to S3
            target_key = f"{target_folder}/{target_filename}"
            logger.info(f"Uploading median image to {target_key}")
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=target_key,
                Body=img_buffer.getvalue(),
                ContentType='image/jpeg',
                Metadata={
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'source_images': str(len(image_arrays)),
                    'source_folder': source_folder
                }
            )
            
            logger.info(f"Successfully created and uploaded median image: {target_key}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'message': f'Successfully created median image from {len(image_arrays)} images',
                    'medianCreated': True,
                    'targetKey': target_key,
                    'sourceImages': len(image_arrays)
                })
            }
            
        except ClientError as e:
            logger.error(f"S3 error: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'success': False,
                    'error': f'S3 error: {str(e)}'
                })
            }
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            })
        }
