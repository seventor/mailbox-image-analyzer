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
    Model B: Enhanced sensitivity comparison with multiple analysis techniques
    - Lower threshold for pixel differences (5 instead of 10)
    - Edge detection to focus on structural changes
    - Color channel analysis for RGB images
    - Multiple threshold levels for different sensitivity levels
    """
    # Convert to RGB if not already (for color analysis)
    if latest_image.mode != 'RGB':
        latest_image = latest_image.convert('RGB')
    if median_image.mode != 'RGB':
        median_image = median_image.convert('RGB')
    
    # Resize both images to same size for comparison
    target_size = (800, 600)
    latest_image = latest_image.resize(target_size, Image.Resampling.LANCZOS)
    median_image = median_image.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays
    latest_array = np.array(latest_image, dtype=np.float32)
    median_array = np.array(median_image, dtype=np.float32)
    
    # 1. Enhanced pixel difference analysis (more sensitive threshold)
    logger.info("ModelB: Calculating enhanced pixel differences")
    diff_array = np.abs(latest_array - median_array)
    
    # Use lower threshold for more sensitivity (5 instead of 10)
    sensitive_threshold = 5
    very_sensitive_threshold = 2
    
    # Calculate differences at multiple sensitivity levels
    different_pixels_sensitive = np.sum(diff_array > sensitive_threshold)
    different_pixels_very_sensitive = np.sum(diff_array > very_sensitive_threshold)
    
    # 2. Edge detection analysis (focus on structural changes)
    from PIL import ImageFilter
    
    # Apply edge detection to both images
    latest_edges = latest_image.filter(ImageFilter.FIND_EDGES)
    median_edges = median_image.filter(ImageFilter.FIND_EDGES)
    
    # Convert edge images to arrays
    latest_edges_array = np.array(latest_edges.convert('L'), dtype=np.float32)
    median_edges_array = np.array(median_edges.convert('L'), dtype=np.float32)
    
    # Calculate edge differences
    edge_diff_array = np.abs(latest_edges_array - median_edges_array)
    edge_different_pixels = np.sum(edge_diff_array > 10)  # Edge threshold
    
    # 3. Color channel analysis
    # Calculate differences per color channel
    red_diff = np.sum(diff_array[:, :, 0] > sensitive_threshold)
    green_diff = np.sum(diff_array[:, :, 1] > sensitive_threshold)
    blue_diff = np.sum(diff_array[:, :, 2] > sensitive_threshold)
    
    # 4. Combined analysis with weighted scoring
    total_pixels = latest_array.size // 3  # RGB has 3 channels
    
    # Weighted difference calculation
    pixel_weight = 0.6  # 60% weight for pixel differences
    edge_weight = 0.3   # 30% weight for edge differences
    color_weight = 0.1  # 10% weight for color channel analysis
    
    # Normalize differences
    pixel_diff_percent = (different_pixels_sensitive / total_pixels) * 100
    edge_diff_percent = (edge_different_pixels / total_pixels) * 100
    color_diff_percent = ((red_diff + green_diff + blue_diff) / (total_pixels * 3)) * 100
    
    # Calculate weighted difference percentage
    weighted_difference_percentage = (
        (pixel_diff_percent * pixel_weight) +
        (edge_diff_percent * edge_weight) +
        (color_diff_percent * color_weight)
    )
    
    # More sensitive threshold for mail detection (10% instead of 15%)
    has_mail = weighted_difference_percentage > 10
    
    return {
        'model_name': 'ModelB',
        'difference_percentage': round(weighted_difference_percentage, 2),
        'total_pixels': int(total_pixels),
        'different_pixels_sensitive': int(different_pixels_sensitive),
        'different_pixels_very_sensitive': int(different_pixels_very_sensitive),
        'edge_different_pixels': int(edge_different_pixels),
        'red_different_pixels': int(red_diff),
        'green_different_pixels': int(green_diff),
        'blue_different_pixels': int(blue_diff),
        'has_mail': bool(has_mail),
        'threshold': 10.0,  # More sensitive threshold
        'image_size': target_size,
        'method': 'enhanced_sensitivity_multi_analysis',
        'analysis_breakdown': {
            'pixel_diff_percent': round(pixel_diff_percent, 2),
            'edge_diff_percent': round(edge_diff_percent, 2),
            'color_diff_percent': round(color_diff_percent, 2),
            'weights': {
                'pixel': pixel_weight,
                'edge': edge_weight,
                'color': color_weight
            }
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
