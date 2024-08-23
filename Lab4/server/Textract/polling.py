import boto3
import json
import os
import utils
import logger

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['ASYNCHRONOUS_EXPENSE_TABLE'])
s3_bucket = os.environ['POOLED_UPLOAD_BUCKET']

def lambda_handler(event, context):
    # job_id = event['jobId']
    job_id = event['pathParameters']['jobId']
    
    sub = event["requestContext"]["authorizer"]["principalId"]
    # sub = event["sub"]
    tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    # tenant_id = event["tenantId"]
    print('sub:', sub)

    # Retrieve the database item
    response = table.get_item(Key={'jobId': job_id})
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'body': json.dumps({"error": "Job ID not found"})
        }
    
    item = response['Item']
    image_key = item.get('image_key')

    # Extract the UUID and invoice name from the image_key
    # base_name = os.path.basename(image_key).replace('.pdf', '')
    base_name = os.path.basename(image_key).replace('.pdf', '').replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
    postprocess_prefix = f"postprocess/{tenant_id}/{sub}/{base_name}/"
    
    # Check for processed images
    processed_images = []
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=s3_bucket, Prefix=postprocess_prefix)
    
    for page in pages:
        for obj in page.get('Contents', []):
            if obj['Key'].endswith('.png'):
                processed_images.append(obj['Key'])
    
    return utils.generate_response({
                "status": item['status'],
                "summary_fields": item['summary_fields'],
                "line_items": item['line_items'],
                "image_key": item['image_key'],
                "processed_images": processed_images,
                "bounding_box_status": item['bounding_box_status']
            })

        
