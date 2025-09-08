import json
import boto3
import logging
import os
from datetime import datetime, timezone
import numpy as np
from PIL import Image
import io
from botocore.exceptions import ClientError
from model_a import modelA_comparison, save_modelA_result
from model_b import modelB_comparison, save_modelB_result
from model_c import modelC_comparison, save_modelC_result
from model_d import modelD_comparison, save_modelD_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')

def run_comparison_model(model_name, latest_image, median_image, latest_image_key, median_image_key, bucket_name=None):
    """
    Run comparison using the specified model
    """
    if model_name == 'ModelA':
        return modelA_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name)
    elif model_name == 'ModelB':
        return modelB_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name)
    elif model_name == 'ModelC':
        return modelC_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name)
    elif model_name == 'ModelD':
        if bucket_name is None:
            raise ValueError("bucket_name is required for ModelD")
        return modelD_comparison(latest_image, median_image, latest_image_key, median_image_key, bucket_name)
    else:
        raise ValueError(f"Unknown model: {model_name}")

def save_comparison_result(bucket_name, model_name, comparison_result, latest_image_key, median_image_key):
    """
    Save comparison result to model-specific files
    """
    # Use the specialized save function for each model
    if model_name == 'ModelA':
        return save_modelA_result(bucket_name, comparison_result, latest_image_key, median_image_key)
    elif model_name == 'ModelB':
        return save_modelB_result(bucket_name, comparison_result, latest_image_key, median_image_key)
    elif model_name == 'ModelC':
        return save_modelC_result(bucket_name, comparison_result, latest_image_key, median_image_key)
    elif model_name == 'ModelD':
        return save_modelD_result(bucket_name, comparison_result, latest_image_key, median_image_key)
    else:
        raise ValueError(f"Unknown model: {model_name}")

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
        comparison_result = run_comparison_model(model_name, latest_image, median_image, latest_image_key, median_image_key, bucket_name)
        
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