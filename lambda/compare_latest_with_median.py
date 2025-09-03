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
    
    # Resize both images to same size for comparison
    target_size = (1024, 576)
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
    
    # Determine if there's mail (threshold: 60%)
    has_mail = difference_percentage > 60
    
    return {
        'model_name': 'ModelA',
        'difference_percentage': round(difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 60.0,
        'image_size': target_size,
        'method': 'pixel_difference_grayscale'
    }

def modelB_comparison(latest_image, median_image, latest_image_key, median_image_key):
    """
    Model B: Same comparison as ModelA but with cubic sensitivity curve
    """
    # Convert to grayscale if not already
    if latest_image.mode != 'L':
        latest_image = latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')
    
    # Resize both images to same size for comparison
    target_size = (1024, 576)
    latest_image = latest_image.resize(target_size, Image.Resampling.LANCZOS)
    median_image = median_image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays
    latest_array = np.array(latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)
    
    # Calculate difference
    logger.info("ModelB: Calculating pixel differences")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference
    total_pixels = latest_array.size
    different_pixels = np.sum(diff_array > 10)  # Threshold of 10 for significant difference
    raw_difference_percentage = (different_pixels / total_pixels) * 100
    
    # Apply cubic sensitivity curve: result = raw³ / 10000
    # This creates a curve that's very gentle at low values and extremely steep at high values
    adjusted_difference_percentage = (raw_difference_percentage ** 3) / 10000
    
    # Determine if there's mail (threshold: 25%)
    has_mail = adjusted_difference_percentage > 25
    
    return {
        'model_name': 'ModelB',
        'difference_percentage': round(adjusted_difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'raw_difference_percentage': round(raw_difference_percentage, 2),
        'has_mail': bool(has_mail),
        'threshold': 25.0,
        'image_size': target_size,
        'method': 'pixel_difference_grayscale_with_cubic_curve',
        'sensitivity_formula': 'raw³ / 10000'
    }

def modelC_comparison(latest_image, median_image, latest_image_key, median_image_key):
    """
    Model C: No cropping. Same comparison grid as ModelA/B (1024x576),
    applies Gaussian horizontal weighting and Model C sensitivity curve.
    """
    # Convert to grayscale if not already (same as ModelA/B)
    if latest_image.mode != 'L':
        latest_image = latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')

    # Resize both images to same size for comparison (same as ModelA/B)
    target_size = (1024, 576)
    latest_image = latest_image.resize(target_size, Image.Resampling.LANCZOS)
    median_image = median_image.resize(target_size, Image.Resampling.LANCZOS)

    # Convert to numpy arrays (same as ModelA/B)
    latest_array = np.array(latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)

    # Calculate difference (same as ModelA/B)
    logger.info("ModelC: Calculating pixel differences (no cropping)")
    diff_array = np.abs(latest_array - median_array)
    
    # Calculate percentage difference with horizontal weighting (Super-Gaussian)
    # - Center emphasis: 150% (2.5× multiplier at center)
    # - Curve width: 20.5% of width (sigma)
    # - Steepness exponent: 2.80 (p)
    # - Smoothly tapers to ~0 at edges
    total_pixels = latest_array.size
    binary_mask = (diff_array > 10)
    different_pixels = int(np.sum(binary_mask))  # unweighted count for reference/metrics

    height, width = latest_array.shape
    center_x = (width - 1) / 2.0
    # weights_row shape: (width,)
    # Super-Gaussian weights: 2.5 * exp(-0.5 * ((x - center)/sigma)^p)
    x = np.arange(width, dtype=np.float32)
    sigma = max((20.5 / 100.0) * width, 1.0)  # 20.5% of width
    p = 2.80  # steepness exponent
    boost = 2.5  # center multiplier (150% emphasis)
    weights_row = boost * np.exp(-0.5 * ((np.abs(x - center_x) / sigma) ** p))
    # Broadcast to full image and compute weighted sum of differing pixels
    weighted_different_pixels = float((binary_mask.astype(np.float32) * weights_row[None, :]).sum())
    weighted_total = float(weights_row.sum() * height)
    raw_difference_percentage = (weighted_different_pixels / weighted_total) * 100
    
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
    
    # Threshold for mail detection (50%)
    has_mail = final_difference_percentage > 50
    
    return {
        'model_name': 'ModelC',
        'difference_percentage': round(final_difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 50.0,
        'image_size': target_size,
        'method': 'pixel_difference_grayscale_with_gaussian_horizontal_weighting'
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
