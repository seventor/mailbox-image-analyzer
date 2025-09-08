import json
import boto3
import logging
import os
from datetime import datetime, timezone
import numpy as np
from PIL import Image, ImageFilter
import io
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def modelB_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name):
    """
    Model B: Multi-analysis comparison (pixel, edge, color) with yellow pixel visualization
    """
    logger.info("ModelB: Starting multi-analysis comparison")
    
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
    
    # 1. Pixel difference analysis
    logger.info("ModelB: Calculating pixel differences")
    pixel_diff_array = np.abs(latest_array - median_array)
    pixel_different_pixels = np.sum(pixel_diff_array > 10)
    pixel_diff_percent = (pixel_different_pixels / latest_array.size) * 100
    
    # 2. Edge detection analysis
    logger.info("ModelB: Calculating edge differences")
    latest_edges = latest_image.filter(ImageFilter.FIND_EDGES)
    median_edges = median_image.filter(ImageFilter.FIND_EDGES)
    
    latest_edge_array = np.array(latest_edges, dtype=np.float32)
    median_edge_array = np.array(median_edges, dtype=np.float32)
    
    edge_diff_array = np.abs(latest_edge_array - median_edge_array)
    edge_different_pixels = np.sum(edge_diff_array > 10)
    edge_diff_percent = (edge_different_pixels / latest_edge_array.size) * 100
    
    # 3. Color analysis (convert back to RGB for color comparison)
    latest_rgb = latest_image.convert('RGB')
    median_rgb = median_image.convert('RGB')
    
    latest_rgb_array = np.array(latest_rgb, dtype=np.float32)
    median_rgb_array = np.array(median_rgb, dtype=np.float32)
    
    color_diff_array = np.abs(latest_rgb_array - median_rgb_array)
    color_different_pixels = np.sum(np.any(color_diff_array > 10, axis=2))
    color_diff_percent = (color_different_pixels / (latest_rgb_array.shape[0] * latest_rgb_array.shape[1])) * 100
    
    # Calculate weighted overall difference
    overall_difference = (pixel_diff_percent * 0.5) + (edge_diff_percent * 0.3) + (color_diff_percent * 0.2)
    
    # Create visualization image with yellow pixels for differences
    # Use pixel differences for visualization
    visualization_image = latest_image.convert('RGB')
    vis_array = np.array(visualization_image)
    
    # Mark different pixels as pure yellow (255, 255, 0)
    diff_mask = pixel_diff_array > 10
    vis_array[diff_mask] = [255, 255, 0]  # Pure yellow
    
    # Convert back to PIL Image
    visualization_image = Image.fromarray(vis_array, 'RGB')
    
    # Save the visualization image with yellow pixels to S3
    try:
        output_buffer = io.BytesIO()
        visualization_image.save(output_buffer, format='JPEG', quality=95)
        visualization_bytes = output_buffer.getvalue()
        
        # Save visualization to S3
        modelb_image_key = 'status/modelB.jpg'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=modelb_image_key,
            Body=visualization_bytes,
            ContentType='image/jpeg',
            Metadata={
                'created_at': datetime.now(timezone.utc).isoformat(),
                'model': 'ModelB',
                'different_pixels': str(pixel_different_pixels),
                'total_pixels': str(latest_array.size)
            }
        )
        logger.info(f"ModelB: Saved visualization image with yellow pixels to {modelb_image_key}")
        
    except Exception as e:
        logger.error(f"ModelB: Error saving visualization image: {str(e)}")
    
    # Determine if there's mail (threshold: 25%)
    has_mail = overall_difference > 25
    
    return {
        'model_name': 'ModelB',
        'difference_percentage': round(float(overall_difference), 2),
        'total_pixels': int(latest_array.size),
        'different_pixels': int(pixel_different_pixels),
        'has_mail': bool(has_mail),
        'threshold': 25.0,
        'image_size': target_size,
        'method': 'multi_analysis_weighted',
        'analysis_breakdown': {
            'pixel_diff_percent': round(float(pixel_diff_percent), 2),
            'edge_diff_percent': round(float(edge_diff_percent), 2),
            'color_diff_percent': round(float(color_diff_percent), 2)
        },
        'visualization_saved': True
    }

def save_modelB_result(bucket_name, comparison_result, latest_image_key, median_image_key):
    """
    Save Model B comparison result to model-specific files
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
    latest_compare_key = f"{status_folder}/modelb.json"
    logger.info(f"Saving latest ModelB comparison to {latest_compare_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=latest_compare_key,
        Body=json.dumps(comparison_result, indent=2),
        ContentType='application/json',
        Metadata={
            'created_at': timestamp,
            'difference_percentage': str(comparison_result['difference_percentage']),
            'model_name': 'ModelB'
        }
    )
    
    # Update statistics array in model-specific file
    statistics_key = f"{status_folder}/statistics-modelb.json"
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
        'model_name': 'ModelB',
        'total_comparisons': len(comparisons),
        'last_updated': timestamp,
        'comparisons': comparisons
    }
    
    logger.info(f"Saving updated ModelB statistics to {statistics_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=statistics_key,
        Body=json.dumps(statistics_data, indent=2),
        ContentType='application/json',
        Metadata={
            'last_updated': timestamp,
            'total_comparisons': str(len(comparisons)),
            'model_name': 'ModelB'
        }
    )
    
    return comparison_result
