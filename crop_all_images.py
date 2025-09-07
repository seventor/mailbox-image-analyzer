#!/usr/bin/env python3
"""
Script to crop the upper 35px from all images in the ai-training-data directory structure.
This ensures consistency with the upload functionality that already crops images.
"""

import boto3
import os
import logging
from PIL import Image
import io
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def crop_image(image_bytes, crop_pixels=35):
    """
    Crop the upper crop_pixels from an image.
    Returns the cropped image bytes or None if cropping fails.
    """
    try:
        # Open image with PIL
        image = Image.open(io.BytesIO(image_bytes))
        logger.info(f"Original image size: {image.size}")
        
        width, height = image.size
        if height <= crop_pixels:
            logger.warning(f"Image height ({height}px) is less than or equal to crop amount ({crop_pixels}px), skipping crop")
            return None
        
        # Crop the upper crop_pixels
        cropped_image = image.crop((0, crop_pixels, width, height))
        logger.info(f"Cropped image size: {cropped_image.size}")
        
        # Save to bytes
        output_buffer = io.BytesIO()
        cropped_image.save(output_buffer, format='JPEG', quality=95)
        return output_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error cropping image: {str(e)}")
        return None

def process_images_in_bucket(bucket_name, prefix='ai-training-data/', crop_pixels=35):
    """
    Process all images in the specified bucket prefix and crop them.
    """
    s3_client = boto3.client('s3')
    
    # Get all objects with the prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
    
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for page in page_iterator:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            key = obj['Key']
            
            # Skip thumbnails and non-JPG files
            if not key.endswith('.jpg') or key.endswith('-thumbnail.jpg'):
                continue
                
            logger.info(f"Processing: {key}")
            
            try:
                # Download the image
                response = s3_client.get_object(Bucket=bucket_name, Key=key)
                original_bytes = response['Body'].read()
                logger.info(f"Downloaded {len(original_bytes)} bytes")
                
                # Crop the image
                cropped_bytes = crop_image(original_bytes, crop_pixels)
                
                if cropped_bytes is None:
                    logger.info(f"Skipped cropping {key}")
                    skipped_count += 1
                    continue
                
                # Upload the cropped image back to S3
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=key,
                    Body=cropped_bytes,
                    ContentType='image/jpeg',
                    CacheControl='no-cache, no-store, must-revalidate',
                    Expires='0'
                )
                
                logger.info(f"Successfully cropped and uploaded {key} ({len(original_bytes)} -> {len(cropped_bytes)} bytes)")
                processed_count += 1
                
            except ClientError as e:
                logger.error(f"S3 error processing {key}: {str(e)}")
                error_count += 1
            except Exception as e:
                logger.error(f"Error processing {key}: {str(e)}")
                error_count += 1
    
    logger.info(f"Processing complete:")
    logger.info(f"  - Processed: {processed_count}")
    logger.info(f"  - Skipped: {skipped_count}")
    logger.info(f"  - Errors: {error_count}")
    
    return processed_count, skipped_count, error_count

def main():
    """
    Main function to crop all images in the ai-training-data directory.
    """
    bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
    crop_pixels = 35
    
    logger.info(f"Starting image cropping process")
    logger.info(f"Bucket: {bucket_name}")
    logger.info(f"Crop pixels: {crop_pixels}")
    logger.info(f"Prefix: ai-training-data/")
    
    try:
        processed, skipped, errors = process_images_in_bucket(bucket_name, crop_pixels=crop_pixels)
        
        logger.info("=" * 50)
        logger.info("CROPPING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Successfully processed: {processed} images")
        logger.info(f"Skipped (too small): {skipped} images")
        logger.info(f"Errors: {errors} images")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
