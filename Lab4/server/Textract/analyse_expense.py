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
    
    bucket = event['bucket']
    documents = event['documents']
    tenant_id = event['tenantId']
    sub = event['sub']
    
    # total_pages_analyzed = 0
    # all_structured_data = []
    job_ids = []
    # bounding_box_status = 'PENDING'


    for document in documents:
        try:
            # Get document content
            # s3_response = s3_client.get_object(Bucket=bucket, Key=document)
            # doc_content = s3_response["Body"].read()
            
            # Determine document type and count pages
            # if document.lower().endswith(".pdf"):
            #     page_count = count_pages(doc_content, "pdf")
            # elif document.lower().endswith((".png", ".jpeg", ".jpg")):
            #     page_count = count_pages(doc_content, document.lower().split('.')[-1])
            # else:
            #     logger.error("Unsupported file type for document: {}".format(document))
            #     continue

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
                # summary_fields, line_items, raw_response = analyze_expense_sync(
                #     bucket, document
                # )
                # save_preprocessed_to_s3(
                #     document, raw_response, OUTPUT_BUCKET_NAME, OUTPUT_S3_PREFIX
                # )
                # save_processed_to_s3(
                #     document, summary_fields, line_items, OUTPUT_BUCKET_NAME, PREFIX
                # )
                
                # structuredData = {
                #     "image_key": document,
                #     "summary_fields": summary_fields,
                #     "line_items": line_items,
                #     "bounding_box_status": bounding_box_status
                #         }
                # all_structured_data.append(structuredData)
                
                # response = sync_img_processor.process_image(raw_response, s3_client, bucket, document, PREFIX)
                # if response["statusCode"] == 200:
                #     logger.info("Successfully uploaded processed file!")
                #     bounding_box_status = 'COMPLETED'
                #     structuredData = {
                #     "image_key": document,
                #     "summary_fields": summary_fields,
                #     "line_items": line_items,
                #     "bounding_box_status": bounding_box_status
                #         }
                #     all_structured_data.append(structuredData)
                # else:
                #     logger.info("Failed to process image!")
                #     bounding_box_status = 'FAILED'
                #     structuredData = {
                #     "image_key": document,
                #     "summary_fields": summary_fields,
                #     "line_items": line_items,
                #     "bounding_box_status": bounding_box_status
                #         }
                #     all_structured_data.append(structuredData)

                # total_pages_analyzed += page_count
                
        except ClientError as e:
            logger.error(e.response["Error"]["Message"])
            continue  # Skip to the next document

    return {
        'statusCode': 200,
        'body': json.dumps({
            "jobIds": job_ids,
            # "total_pages_analyzed": total_pages_analyzed,
            # "data": all_structured_data
        })
    }
    
# def count_pages(doc_content, doc_type):
#     if doc_type == "pdf":
#         from PyPDF2 import PdfReader
#         from io import BytesIO
#         reader = PdfReader(BytesIO(doc_content))
#         return len(reader.pages)
#     elif doc_type in ["jpeg", "jpg", "png"]:
#         from PIL import Image
#         from io import BytesIO
#         image = Image.open(BytesIO(doc_content))
#         return 1  # Each image is considered as one page
#     else:
#         raise ValueError("Unsupported document type")

# def analyze_expense_sync(bucket_name, document_key):
#     textract_client = boto3.client("textract")
    
#     response = textract_client.analyze_expense(
#         Document={'S3Object': {'Bucket': bucket_name, 'Name': document_key}}
#     )

#     summary_fields, line_items = extract_expense_data_from_response(response)

#     return summary_fields, line_items, response

# def extract_expense_data_from_response(response):
#     summary_fields = {}
#     line_items = []

#     required_summary_fields = {
#         "INVOICE_RECEIPT_DATE",
#         "INVOICE_RECEIPT_ID",
#         "VENDOR_NAME",
#         "RECEIVER_NAME",
#         "PO_NUMBER",
#         "TOTAL",
#         "SUBTOTAL",
#         "TAX",
#         "VENDOR_VAT_NUMBER",
#         "RECEIVER_VAT_NUMBER"
#     }

#     required_line_item_fields = {
#         "ITEM",
#         "QUANTITY",
#         "PRICE",
#         "UNIT_PRICE"
#     }

#     for document in response.get('ExpenseDocuments', []):
#         # Process summary fields with confidence scores
#         for summary_field in document.get('SummaryFields', []):
#             field_type = summary_field.get('Type', {}).get('Text')
#             if field_type in required_summary_fields:
#                 value = summary_field.get('ValueDetection', {}).get('Text', 'Unknown')
#                 confidence = summary_field.get('ValueDetection', {}).get('Confidence', 0.0)
#                 summary_fields[field_type] = {
#                     "value": value,
#                     "confidence": confidence
#                 }

#         # Process line items with confidence scores
#         for line_item_group in document.get('LineItemGroups', []):
#             for line_item in line_item_group.get('LineItems', []):
#                 line_item_data = {}
#                 for field in line_item.get('LineItemExpenseFields', []):
#                     field_type = field.get('Type', {}).get('Text')
#                     if field_type in required_line_item_fields:
#                         value = field.get('ValueDetection', {}).get('Text', 'Unknown')
#                         confidence = field.get('ValueDetection', {}).get('Confidence', 0.0)
#                         line_item_data[field_type] = {
#                             "value": value,
#                             "confidence": confidence
#                         }
#                 if line_item_data:
#                     line_items.append(line_item_data)


#     return summary_fields, line_items

# def save_processed_to_s3(filename, summary_fields, line_items, bucket_name, prefix):
#     results = {
#         "summary_fields": summary_fields,
#         "line_items": line_items
#     }

#     results_json_key_name = f"{filename.split('/')[-1].split('.')[0]}_results.json"
#     results_json = f"/tmp/{results_json_key_name}"

#     with open(results_json, 'w') as f:
#         json.dump(results, f)

#     upload_to_s3(results_json, bucket_name, f"{prefix}/{filename.split('/')[-1].split('.')[0]}/{results_json_key_name}")

# def save_preprocessed_to_s3(filename, raw_response, bucket_name, output_s3_prefix):
#     preprocessed_key_name = f"{filename.split('/')[-1].split('.')[0]}_preprocessed.json"
#     preprocessed_file = f"/tmp/{preprocessed_key_name}"

#     with open(preprocessed_file, 'w') as f:
#         json.dump(raw_response, f)

#     upload_to_s3(preprocessed_file, bucket_name, f"{output_s3_prefix}/{preprocessed_key_name}")

# def upload_to_s3(filename, bucket, key):
#     s3 = boto3.client("s3")
#     s3.upload_file(Filename=filename, Bucket=bucket, Key=key)
