import os
import json
import boto3
import asyncio
import logger
from PyPDF2 import PdfReader
from PIL import Image
from io import BytesIO
import requests
import sync_img_processor
from botocore.exceptions import ClientError


OUTPUT_BUCKET_NAME = os.environ["OUTPUT_BUCKET_NAME"]
PREFIX = os.environ["PREFIX"]
OUTPUT_S3_PREFIX = os.environ["OUTPUT_S3_PREFIX"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
SNS_ROLE_ARN = os.environ["SNS_ROLE_ARN"]


def lambda_handler(event, context):
    textract_client = boto3.client('textract')
    print("Event:", event)
    bucket = event['bucket']
    documents = event['documents']
    tenant_id = event['tenantId']
    sub = event['sub'], 
    job_ids = []



    for document in documents:
        try:
            if document.lower().endswith((".pdf", ".png", ".jpg")):
                print("Processing type: Async Expense Analysis")
                response = textract_client.start_expense_analysis(
                    DocumentLocation={
                        "S3Object": {"Bucket": bucket, "Name": document}
                    },
                    OutputConfig={
                        "S3Bucket": OUTPUT_BUCKET_NAME,
                        "S3Prefix": f'{OUTPUT_S3_PREFIX}/{tenant_id}/{sub}',
                    },
                    NotificationChannel={
                        "SNSTopicArn": SNS_TOPIC_ARN,
                        "RoleArn": SNS_ROLE_ARN,
                    },
                )
                
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    logger.info("Job created successfully!")
                    job_id = response["JobId"]
                    job_ids.append(job_id)
                else:
                    logger.error("Job creation failed!")
                    continue  # Skip to the next document
            else:
                print("Processing type: Sync Expense Analysis")
                
        except ClientError as e:
            logger.error(e.response["Error"]["Message"])
            continue  # Skip to the next document

    return {
        'statusCode': 200,
        'body': json.dumps({
            "jobIds": job_ids,
        })
    }
    