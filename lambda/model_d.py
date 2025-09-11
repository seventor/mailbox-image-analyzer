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

def calculate_brightness(image):
    """
    Calculate the overall brightness of an image
    Returns the mean brightness value (0-255)
    """
    # Convert to grayscale if not already
    if image.mode != 'L':
        gray_image = image.convert('L')
    else:
        gray_image = image
    
    # Convert to numpy array and calculate mean
    gray_array = np.array(gray_image, dtype=np.float32)
    brightness = np.mean(gray_array)
    
    return brightness

def adjust_brightness(image, target_brightness):
    """
    Adjust the brightness of an image to match the target brightness
    Returns a new PIL Image with adjusted brightness
    """
    # Convert to RGB if not already (needed for brightness adjustment)
    if image.mode != 'RGB':
        rgb_image = image.convert('RGB')
    else:
        rgb_image = image
    
    # Calculate current brightness
    current_brightness = calculate_brightness(rgb_image)
    
    # Calculate brightness adjustment factor
    if current_brightness > 0:
        brightness_factor = target_brightness / current_brightness
    else:
        brightness_factor = 1.0
    
    logger.info(f"Brightness adjustment: current={current_brightness:.2f}, target={target_brightness:.2f}, factor={brightness_factor:.2f}")
    
    # Convert to numpy array for adjustment
    rgb_array = np.array(rgb_image, dtype=np.float32)
    
    # Apply brightness adjustment
    adjusted_array = rgb_array * brightness_factor
    
    # Clip values to valid range (0-255)
    adjusted_array = np.clip(adjusted_array, 0, 255)
    
    # Convert back to PIL Image
    adjusted_image = Image.fromarray(adjusted_array.astype(np.uint8))
    
    return adjusted_image

def modelD_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name):
    """
    Model D: Brightness-adjusted comparison
    1. Calculate overall brightness of latest.jpg and median image
    2. Adjust latest.jpg brightness to match median image brightness
    3. Compare using same logic as Model A
    4. Save the brightness-adjusted image to /status/modelD.jpg
    """
    logger.info("ModelD: Starting brightness-adjusted comparison")
    
    # Calculate brightness of both images
    latest_brightness = calculate_brightness(latest_image)
    median_brightness = calculate_brightness(median_image)
    
    logger.info(f"ModelD: Latest brightness={latest_brightness:.2f}, Median brightness={median_brightness:.2f}")
    
    # Adjust latest image brightness to match median brightness
    adjusted_latest_image = adjust_brightness(latest_image, median_brightness)
    
    # Now perform comparison using Model A logic on the adjusted image
    # Convert to grayscale if not already
    if adjusted_latest_image.mode != 'L':
        adjusted_latest_image = adjusted_latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')
    
    # Only resize adjusted latest image if it's different size than median image
    if adjusted_latest_image.size != median_image.size:
        logger.info(f"ModelD: Resizing adjusted latest image from {adjusted_latest_image.size} to {median_image.size}")
        adjusted_latest_image = adjusted_latest_image.resize(median_image.size, Image.Resampling.LANCZOS)
    else:
        logger.info(f"ModelD: Images already same size: {adjusted_latest_image.size}")
    
    target_size = median_image.size
    
    # Convert to numpy arrays
    latest_array = np.array(adjusted_latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)
    
    # Calculate difference
    logger.info("ModelD: Calculating pixel differences on brightness-adjusted image")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference
    total_pixels = latest_array.size
    different_pixels = np.sum(diff_array > 10)  # Threshold of 10 for significant difference
    difference_percentage = (different_pixels / total_pixels) * 100
    
    # Create visualization image with yellow pixels for differences
    # Convert grayscale back to RGB for yellow marking
    visualization_image = adjusted_latest_image.convert('RGB')
    vis_array = np.array(visualization_image)
    
    # Mark different pixels as pure yellow (255, 255, 0)
    diff_mask = diff_array > 10
    vis_array[diff_mask] = [255, 255, 0]  # Pure yellow
    
    # Convert back to PIL Image
    visualization_image = Image.fromarray(vis_array, 'RGB')
    
    # Save the visualization image with yellow pixels to S3
    try:
        output_buffer = io.BytesIO()
        visualization_image.save(output_buffer, format='JPEG', quality=95)
        visualization_bytes = output_buffer.getvalue()
        
        # Save visualization to S3
        modeld_image_key = 'status/modelD.jpg'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=modeld_image_key,
            Body=visualization_bytes,
            ContentType='image/jpeg',
            Metadata={
                'created_at': datetime.now(timezone.utc).isoformat(),
                'model': 'ModelD',
                'original_brightness': str(latest_brightness),
                'target_brightness': str(median_brightness),
                'different_pixels': str(different_pixels),
                'total_pixels': str(total_pixels)
            }
        )
        logger.info(f"ModelD: Saved visualization image with yellow pixels to {modeld_image_key}")
        
    except Exception as e:
        logger.error(f"ModelD: Error saving visualization image: {str(e)}")
    
    # Determine if there's mail (threshold: 60% - same as Model A)
    has_mail = difference_percentage > 60
    
    return {
        'model_name': 'ModelD',
        'difference_percentage': round(float(difference_percentage), 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 60.0,
        'image_size': target_size,
        'method': 'brightness_adjusted_pixel_difference_grayscale',
        'original_brightness': round(float(latest_brightness), 2),
        'median_brightness': round(float(median_brightness), 2),
        'brightness_adjustment_factor': round(float(median_brightness / latest_brightness), 2) if latest_brightness > 0 else 1.0,
        'adjusted_image_saved': True
    }

def save_modelD_result(bucket_name, comparison_result, latest_image_key, median_image_key):
    """
    Save Model D comparison result to model-specific files
    """
    status_folder = 'status'
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Add common fields to comparison result
    comparison_result.update({
        'timestamp': timestamp,
        'latest_image': latest_image_key,
        'median_image': median_image_key,
    })
    
    # Save latest comparison to model-specific file
    latest_compare_key = f"{status_folder}/modeld.json"
    logger.info(f"Saving latest ModelD comparison to {latest_compare_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=latest_compare_key,
        Body=json.dumps(comparison_result, indent=2),
        ContentType='application/json',
        Metadata={
            'created_at': timestamp,
            'difference_percentage': str(comparison_result['difference_percentage']),
            'model_name': 'ModelD'
        }
    )
    
    # Update statistics array in model-specific file
    statistics_key = f"{status_folder}/statistics-modeld.json"
    try:
        # Try to read existing statistics
        statistics_response = s3_client.get_object(Bucket=bucket_name, Key=statistics_key)
        statistics_data = json.loads(statistics_response['Body'].read())
        comparisons = statistics_data.get('comparisons', [])
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            # File doesn't exist, create new
            comparisons = []
        else:
            logger.error(f"Error reading statistics file: {str(e)}")
            comparisons = []
    except Exception as e:
        logger.error(f"Unexpected error reading statistics: {str(e)}")
        comparisons = []
    
    # Add new comparison to the beginning of the array
    comparisons.insert(0, comparison_result)
    
    # Keep only comparisons from the last 60 days to prevent file from growing too large
    sixty_days_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sixty_days_ago = sixty_days_ago.replace(day=sixty_days_ago.day - 60)
    comparisons = [c for c in comparisons if datetime.fromisoformat(c['timestamp'].replace('Z', '+00:00')) >= sixty_days_ago]
    
    # Save updated statistics
    statistics_data = {
        'model_name': 'ModelD',
        'total_comparisons': len(comparisons),
        'last_updated': timestamp,
        'comparisons': comparisons
    }
    
    logger.info(f"Saving updated ModelD statistics to {statistics_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=statistics_key,
        Body=json.dumps(statistics_data, indent=2),
        ContentType='application/json',
        Metadata={
            'last_updated': timestamp,
            'total_comparisons': str(len(comparisons)),
            'model_name': 'ModelD'
        }
    )
    
    return comparison_result