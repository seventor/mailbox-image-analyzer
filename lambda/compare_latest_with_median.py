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
    try:
        bucket_name = os.environ.get('BUCKET_NAME', 'mailbox-image-analyzer-dev')
        latest_image_key = 'uploads/latest.jpg'
        median_image_key = 'median-image/median.jpg'
        status_folder = 'status'
        
        logger.info(f"Starting comparison of latest.jpg with median image")
        
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
        logger.info("Calculating pixel differences")
        diff_array = np.abs(latest_array - median_array)
        
        # Calculate percentage difference
        total_pixels = latest_array.size
        different_pixels = np.sum(diff_array > 10)  # Threshold of 10 for significant difference
        difference_percentage = (different_pixels / total_pixels) * 100
        
        # Determine if there's mail (threshold: 15%)
        has_mail = difference_percentage > 15
        
        # Create timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create comparison result
        comparison_result = {
            'timestamp': timestamp,
            'latest_image': latest_image_key,
            'median_image': median_image_key,
            'difference_percentage': round(difference_percentage, 2),
            'total_pixels': int(total_pixels),
            'different_pixels': int(different_pixels),
            'has_mail': bool(has_mail),
            'threshold': 15.0,
            'image_size': target_size
        }
        
        # Save latest comparison to status/latest-compare.json
        latest_compare_key = f"{status_folder}/latest-compare.json"
        logger.info(f"Saving latest comparison to {latest_compare_key}")
        s3_client.put_object(
            Bucket=bucket_name,
            Key=latest_compare_key,
            Body=json.dumps(comparison_result, indent=2),
            ContentType='application/json',
            Metadata={
                'created_at': timestamp,
                'difference_percentage': str(difference_percentage)
            }
        )
        
        # Update statistics array in status/statistics-compare.json
        statistics_key = f"{status_folder}/statistics-compare.json"
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
                'total_comparisons': str(len(comparisons))
            }
        )
        
        logger.info(f"Comparison completed: {difference_percentage:.2f}% difference, has_mail: {has_mail}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'comparison': comparison_result,
                'message': f'Comparison completed: {difference_percentage:.2f}% difference'
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
