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

def modelA_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name):
    """
    Model A: Simple pixel-based difference comparison with yellow pixel visualization
    """
    logger.info("ModelA: Starting pixel-based comparison")
    
    # Convert to grayscale if not already
    if latest_image.mode != 'L':
        latest_image = latest_image.convert('L')
    if median_image.mode != 'L':
        median_image = median_image.convert('L')
    
    # Only resize latest image if it's different size than median image
    if latest_image.size != median_image.size:
        logger.info(f"ModelA: Resizing latest image from {latest_image.size} to {median_image.size}")
        latest_image = latest_image.resize(median_image.size, Image.Resampling.LANCZOS)
    else:
        logger.info(f"ModelA: Images already same size: {latest_image.size}")
    
    target_size = median_image.size
    
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
    
    # Create visualization image with yellow pixels for differences
    # Convert grayscale back to RGB for yellow marking
    visualization_image = latest_image.convert('RGB')
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
        modela_image_key = 'status/modelA.jpg'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=modela_image_key,
            Body=visualization_bytes,
            ContentType='image/jpeg',
            Metadata={
                'created_at': datetime.now(timezone.utc).isoformat(),
                'model': 'ModelA',
                'different_pixels': str(different_pixels),
                'total_pixels': str(total_pixels)
            }
        )
        logger.info(f"ModelA: Saved visualization image with yellow pixels to {modela_image_key}")
        
    except Exception as e:
        logger.error(f"ModelA: Error saving visualization image: {str(e)}")
    
    # Determine if there's mail (threshold: 60%)
    has_mail = difference_percentage > 60
    
    return {
        'model_name': 'ModelA',
        'difference_percentage': round(float(difference_percentage), 2),
        'total_pixels': int(total_pixels),
        'different_pixels': int(different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 60.0,
        'image_size': target_size,
        'method': 'pixel_difference_grayscale',
        'visualization_saved': True
    }

def save_modelA_result(bucket_name, comparison_result, latest_image_key, median_image_key):
    """
    Save Model A comparison result to model-specific files
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
    latest_compare_key = f"{status_folder}/modela.json"
    logger.info(f"Saving latest ModelA comparison to {latest_compare_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=latest_compare_key,
        Body=json.dumps(comparison_result, indent=2),
        ContentType='application/json',
        Metadata={
            'created_at': timestamp,
            'difference_percentage': str(comparison_result['difference_percentage']),
            'model_name': 'ModelA'
        }
    )
    
    # Update statistics array in model-specific file
    statistics_key = f"{status_folder}/statistics-modela.json"
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
        'model_name': 'ModelA',
        'total_comparisons': len(comparisons),
        'last_updated': timestamp,
        'comparisons': comparisons
    }
    
    logger.info(f"Saving updated ModelA statistics to {statistics_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=statistics_key,
        Body=json.dumps(statistics_data, indent=2),
        ContentType='application/json',
        Metadata={
            'last_updated': timestamp,
            'total_comparisons': str(len(comparisons)),
            'model_name': 'ModelA'
        }
    )
    
    return comparison_result
