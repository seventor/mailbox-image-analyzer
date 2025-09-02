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

def modelA_comparison(latest_image, median_image, latest_image_key, median_image_key):
    """
    Model A: Pixel-based difference comparison with grayscale conversion
    """
    # Convert to grayscale if not already
    if latest_image.mode != 'L':
        latest_image = latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')
    
    # Resize both images to same size for comparison (use median size as reference)
    target_size = (800, 600)
    latest_image = latest_image.resize(target_size, Image.Resampling.LANCZOS)
    median_image = median_image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays
    latest_array = np.array(latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)
    
    # Calculate difference
    logger.info("ModelA: Calculating pixel differences")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference
    total_pixels = latest_array.size
    different_pixels = np.sum(diff_array > 10)  # Threshold of 10 for significant difference
    difference_percentage = (different_pixels / total_pixels) * 100
    
    # Determine if there's mail (threshold: 15%)
    has_mail = difference_percentage > 15
    
    return {
        'model_name': 'ModelA',
        'difference_percentage': round(difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 15.0,
        'image_size': target_size,
        'method': 'pixel_difference_grayscale'
    }

def modelB_comparison(latest_image, median_image, latest_image_key, median_image_key):
    """
    Model B: Same comparison as ModelA but with sensitivity curve
    - Uses same grayscale pixel comparison as ModelA
    - Applies sensitivity curve: amplifies 0-40%, dampens 40-100%
    - Never exceeds 100%
    """
    # Convert to grayscale if not already (same as ModelA)
    if latest_image.mode != 'L':
        latest_image = latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')
    
    # Resize both images to same size for comparison (same as ModelA)
    target_size = (800, 600)
    latest_image = latest_image.resize(target_size, Image.Resampling.LANCZOS)
    median_image = median_image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays (same as ModelA)
    latest_array = np.array(latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)
    
    # Calculate difference (same as ModelA)
    logger.info("ModelB: Calculating pixel differences (same as ModelA)")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference (same as ModelA)
    total_pixels = latest_array.size
    different_pixels = np.sum(diff_array > 10)  # Same threshold as ModelA
    raw_difference_percentage = (different_pixels / total_pixels) * 100
    
    # Apply sensitivity curve
    # 0-40%: amplify (make more sensitive)
    # 40-100%: dampen (make less sensitive)
    if raw_difference_percentage <= 40:
        # Amplify: multiply by 1.5 (max 40% becomes 60%)
        adjusted_percentage = raw_difference_percentage * 1.5
    else:
        # Dampen: use a curve that approaches 100% asymptotically
        # Formula: 60 + (raw - 40) * 0.67
        # This ensures 40% -> 60%, 100% -> 100%
        adjusted_percentage = 60 + (raw_difference_percentage - 40) * 0.67
    
    # Ensure we never exceed 100%
    final_difference_percentage = min(adjusted_percentage, 100.0)
    
    # More sensitive threshold for mail detection (10% instead of 15%)
    has_mail = final_difference_percentage > 10
    
    return {
        'model_name': 'ModelB',
        'difference_percentage': round(final_difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'raw_difference_percentage': round(raw_difference_percentage, 2),
        'adjusted_difference_percentage': round(adjusted_percentage, 2),
        'has_mail': bool(has_mail),
        'threshold': 10.0,  # More sensitive threshold
        'image_size': target_size,
        'method': 'pixel_difference_grayscale_with_sensitivity_curve',
        'sensitivity_curve': {
            'amplification_factor': 1.5,
            'amplification_range': '0-40%',
            'dampening_factor': 0.67,
            'dampening_range': '40-100%'
        }
    }

def modelC_comparison(latest_image, median_image, latest_image_key, median_image_key):
    """
    Model C: Same comparison as ModelB but with cropping applied to both images
    - Uses same grayscale pixel comparison as ModelA
    - Applies sensitivity curve: amplifies 0-40%, dampens 40-100%
    - Crops both images before comparison using specified crop area
    - Resizes both images to same size BEFORE cropping for consistent crop coordinates
    - Saves cropped images for inspection
    - Never exceeds 100%
    """
    # First, resize both images to the same size for consistent cropping
    # Use the source image dimensions since median will now match
    target_size_before_crop = (1024, 576)  # Both images will be this size
    
    latest_resized = latest_image.resize(target_size_before_crop, Image.Resampling.LANCZOS)
    median_resized = median_image.resize(target_size_before_crop, Image.Resampling.LANCZOS)
    
    # Crop both images using the specified crop area (now applied to same-sized images)
    # Crop area: X=338, Y=33, Width=388, Height=543
    crop_area = (338, 33, 338 + 388, 33 + 543)  # (left, top, right, bottom)
    
    # Crop the images
    latest_cropped = latest_resized.crop(crop_area)
    median_cropped = median_resized.crop(crop_area)
    
    # Save cropped images for inspection
    try:
        # Convert to RGB for saving as JPEG
        latest_cropped_rgb = latest_cropped.convert('RGB')
        median_cropped_rgb = median_cropped.convert('RGB')
        
        # Save to memory buffers
        latest_buffer = io.BytesIO()
        median_buffer = io.BytesIO()
        
        latest_cropped_rgb.save(latest_buffer, format='JPEG', quality=95)
        median_cropped_rgb.save(median_buffer, format='JPEG', quality=95)
        
        # Upload to S3
        bucket_name = os.environ['BUCKET_NAME']
        s3_client.put_object(
            Bucket=bucket_name,
            Key='modelc-latest-cropped.jpg',
            Body=latest_buffer.getvalue(),
            ContentType='image/jpeg'
        )
        s3_client.put_object(
            Bucket=bucket_name,
            Key='modelc-median-cropped.jpg',
            Body=median_buffer.getvalue(),
            ContentType='image/jpeg'
        )
        
        logger.info("ModelC: Saved cropped images for inspection")
    except Exception as e:
        logger.error(f"ModelC: Failed to save cropped images: {str(e)}")
    
    # Convert to grayscale if not already (same as ModelA)
    if latest_cropped.mode != 'L':
        latest_cropped = latest_cropped.convert('L')
    if median_cropped.mode != 'L':
        median_cropped = median_cropped.convert('L')
    
    # Resize both images to same size for comparison (same as ModelA)
    target_size = (800, 600)
    latest_cropped = latest_cropped.resize(target_size, Image.Resampling.LANCZOS)
    median_cropped = median_cropped.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays (same as ModelA)
    latest_array = np.array(latest_cropped, dtype=np.float32)
    median_array = np.array(median_cropped, dtype=np.float32)
    
    # Calculate difference (same as ModelA)
    logger.info("ModelC: Calculating pixel differences (same as ModelA) with cropping")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference (same as ModelA)
    total_pixels = latest_array.size
    different_pixels = np.sum(diff_array > 10)  # Same threshold as ModelA
    raw_difference_percentage = (different_pixels / total_pixels) * 100
    
    # Apply sensitivity curve (much less sensitive than ModelB)
    # 0-40%: slight amplification
    # 40-100%: significant dampening
    if raw_difference_percentage <= 40:
        # Slight amplification: multiply by 1.05 (max 40% becomes 42%)
        adjusted_percentage = raw_difference_percentage * 1.05
    else:
        # Significant dampening: use a curve that approaches 30% asymptotically
        # Formula: 42 + (raw - 40) * 0.05
        # This ensures 40% -> 42%, 100% -> 30%
        adjusted_percentage = 42 + (raw_difference_percentage - 40) * 0.05
    
    # Ensure we never exceed 100%
    final_difference_percentage = min(adjusted_percentage, 100.0)
    
    # More sensitive threshold for mail detection (10% instead of 15%)
    has_mail = final_difference_percentage > 10
    
    return {
        'model_name': 'ModelC',
        'difference_percentage': round(final_difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'raw_difference_percentage': round(raw_difference_percentage, 2),
        'adjusted_difference_percentage': round(adjusted_percentage, 2),
        'has_mail': bool(has_mail),
        'threshold': 10.0,  # More sensitive threshold
        'image_size': target_size,
        'method': 'pixel_difference_grayscale_with_sensitivity_curve_and_cropping',
        'crop_area': {
            'x': 338,
            'y': 33,
            'width': 388,
            'height': 543
        },
        'sensitivity_curve': {
            'amplification_factor': 1.05,
            'amplification_range': '0-40%',
            'dampening_factor': 0.05,
            'dampening_range': '40-100%'
        }
    }

def run_comparison_model(model_name, latest_image, median_image, latest_image_key, median_image_key):
    """
    Run comparison using the specified model
    """
    if model_name == 'ModelA':
        return modelA_comparison(latest_image, median_image, latest_image_key, median_image_key)
    elif model_name == 'ModelB':
        return modelB_comparison(latest_image, median_image, latest_image_key, median_image_key)
    elif model_name == 'ModelC':
        return modelC_comparison(latest_image, median_image, latest_image_key, median_image_key)
    else:
        raise ValueError(f"Unknown model: {model_name}")

def save_comparison_result(bucket_name, model_name, comparison_result, latest_image_key, median_image_key):
    """
    Save comparison result to model-specific files
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
    latest_compare_key = f"{status_folder}/{model_name.lower()}.json"
    logger.info(f"Saving latest comparison to {latest_compare_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=latest_compare_key,
        Body=json.dumps(comparison_result, indent=2),
        ContentType='application/json',
        Metadata={
            'created_at': timestamp,
            'difference_percentage': str(comparison_result['difference_percentage']),
            'model_name': model_name
        }
    )
    
    # Update statistics array in model-specific file
    statistics_key = f"{status_folder}/statistics-{model_name.lower()}.json"
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
    
    # Keep only the last 100 comparisons to prevent file from growing too large
    if len(comparisons) > 100:
        comparisons = comparisons[:100]
    
    # Save updated statistics
    statistics_data = {
        'model_name': model_name,
        'total_comparisons': len(comparisons),
        'last_updated': timestamp,
        'comparisons': comparisons
    }
    
    logger.info(f"Saving updated statistics to {statistics_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=statistics_key,
        Body=json.dumps(statistics_data, indent=2),
        ContentType='application/json',
        Metadata={
            'last_updated': timestamp,
            'total_comparisons': str(len(comparisons)),
            'model_name': model_name
        }
    )
    
    return comparison_result

def handler(event, context):
    try:
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        latest_image_key = 'uploads/latest.jpg'
        median_image_key = 'median-image/median.jpg'
        
        # Get model name from event or default to ModelA
        model_name = event.get('model_name', 'ModelA')
        
        logger.info(f"Starting {model_name} comparison of latest.jpg with median image")
        
        # Check if latest.jpg exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=latest_image_key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning("latest.jpg not found")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': False,
                        'error': 'latest.jpg not found',
                        'comparison': None
                    })
                }
            else:
                raise e
        
        # Check if median image exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=median_image_key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning("median.jpg not found")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'success': False,
                        'error': 'median.jpg not found',
                        'comparison': None
                    })
                }
            else:
                raise e
        
        # Download latest image
        logger.info("Downloading latest.jpg")
        latest_response = s3_client.get_object(Bucket=bucket_name, Key=latest_image_key)
        latest_data = latest_response['Body'].read()
        latest_image = Image.open(io.BytesIO(latest_data))
        
        # Download median image
        logger.info("Downloading median.jpg")
        median_response = s3_client.get_object(Bucket=bucket_name, Key=median_image_key)
        median_data = median_response['Body'].read()
        median_image = Image.open(io.BytesIO(median_data))
        
        # Run comparison using specified model
        comparison_result = run_comparison_model(model_name, latest_image, median_image, latest_image_key, median_image_key)
        
        # Save results to model-specific files
        final_result = save_comparison_result(bucket_name, model_name, comparison_result, latest_image_key, median_image_key)
        
        difference_percentage = comparison_result['difference_percentage']
        has_mail = comparison_result['has_mail']
        
        logger.info(f"{model_name} comparison completed: {difference_percentage:.2f}% difference, has_mail: {has_mail}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'model_name': model_name,
                'comparison': final_result,
                'message': f'{model_name} comparison completed: {difference_percentage:.2f}% difference'
            })
        }
        
    except ClientError as e:
        logger.error(f"S3 error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'S3 error: {str(e)}',
                'comparison': None
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}',
                'comparison': None
            })
        }
