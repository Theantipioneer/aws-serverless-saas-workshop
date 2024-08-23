import os
import json
import boto3
import asyncio
import requests
import logger
import json
from decimal import Decimal
import async_img_processor

def lambda_handler(event, context):
    BUCKET_NAME = os.environ["BUCKET_NAME"]
    PREFIX = os.environ["PREFIX"]
    
    s3 = boto3.client("s3")
    dynamodb = boto3.resource('dynamodb')
    # table = dynamodb.Table(os.environ['ASYNCHRONOUS_EXPENSE_TABLE'])
    
    sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
    job_id = sns_message["JobId"]
    document_location = sns_message["DocumentLocation"]
    image_key = document_location["S3ObjectName"]
    
    path_parts = image_key.split('/')
    # invoicename = path_parts[-1].split('.')[0]  # Extract 'invoicename' from 'invoicename.png'
    tenant_id = path_parts[-3]
    sub = path_parts[-2]
    
    processed_images = []
    bounding_box_status = 'PENDING'

    summary_fields, line_items, textract_response = process_async_response(job_id)

    save_results_to_s3(image_key, summary_fields, line_items, BUCKET_NAME, PREFIX)
    
    try:
        # Process the image asynchronously
        response = asyncio.run(async_img_processor.process_image(textract_response, s3, BUCKET_NAME, image_key, PREFIX))
        
        if response["statusCode"] == 200:
            logger.info("Successfully uploaded processed image")
            bounding_box_status = 'COMPLETED'
            
            base_name = os.path.basename(image_key).replace('.pdf', '').replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
            postprocess_prefix = f"postprocess/{tenant_id}/{sub}/{base_name}/"
            
            # Check for processed images
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=postprocess_prefix)
            
            for page in pages:
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.png'):
                        processed_images.append(obj['Key'])
        else:
            logger.info("Failed to process image!")
            bounding_box_status = 'FAILED'
    except Exception as e:
        logger.error(f"Image processing encountered an error: {e}")
        bounding_box_status = 'FAILED'
    finally:
        # Notify clients regardless of success or failure
        notify_clients(dynamodb, job_id, summary_fields, line_items, processed_images, bounding_box_status, image_key)

    
    return {"statusCode": 200, "body": json.dumps("Files uploaded successfully!")}

def decimal_default(obj):
    if isinstance(obj, Decimal):
        # Convert Decimal to float or int
        return float(obj) if obj % 1 else int(obj)
    raise TypeError

def notify_clients(dynamodb, job_id, summary_fields_per_page, line_items_per_page, processed_images, bounding_box_status, image_key):
    logger.info(f"Fetching active WebSocket connections from {os.environ['WEBSOCKET_CONNECTION_TABLE']} table.")
    
    # Fetch active connections from DynamoDB
    connections_table = dynamodb.Table(os.environ['WEBSOCKET_CONNECTION_TABLE'])
    try:
        active_connections = connections_table.scan()
        logger.info(f"Active connections retrieved: {len(active_connections['Items'])} connections found.")
    except Exception as e:
        logger.error(f"Error scanning WebSocket connections table: {e}")
        return

    # Prepare the message to be sent
    # message = json.dumps({
    #     "jobId": job_id,
    #     "bounding_box_status": bounding_box_status,
    #     "image_key": image_key,
    #     "boxed_images": processed_images,
    #     "pages": []
    # }, default=decimal_default)
    
    message = {
        "jobId": job_id,
        "bounding_box_status": bounding_box_status,
        "image_key": image_key,
        "boxed_images": processed_images,
        "pages": []
    }
    
    for page in range(len(processed_images)):
        page_data = {
            "image": processed_images[page],
            "summary_fields": summary_fields_per_page[page]["summary_fields"] if page < len(summary_fields_per_page) else {},
            "line_items": line_items_per_page[page]["line_items"] if page < len(line_items_per_page) else []
        }
        message["pages"].append(page_data)
    
    # Convert the message to JSON
    message_json = json.dumps(message, default=decimal_default)
    
    for page in range(len(processed_images)):
        page_data = {
            "image": processed_images[page],
            "summary_fields": summary_fields_per_page[page]["summary_fields"] if page < len(summary_fields_per_page) else {},
            "line_items": line_items_per_page[page]["line_items"] if page < len(line_items_per_page) else []
        }
        message["pages"].append(page_data)

    logger.info(f"Message prepared for WebSocket delivery: {message}")

    apigw_management_client = boto3.client('apigatewaymanagementapi',
                                           endpoint_url=os.environ['WEBSOCKET_API_ENDPOINT'])

    # Send the message to all active connections
    for connection in active_connections['Items']:
        connection_id = connection['connectionId']
        try:
            logger.info(f"Sending message to connection ID: {connection_id}")
            apigw_management_client.post_to_connection(
                ConnectionId=connection_id,
                Data=message_json
            )
            logger.info(f"Message successfully sent to connection ID: {connection_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            # Optionally, delete stale connections from the table
            try:
                connections_table.delete_item(Key={'connectionId': connection_id})
                logger.info(f"Deleted stale connection: {connection_id}")
            except Exception as del_error:
                logger.error(f"Failed to delete stale connection {connection_id}: {del_error}")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # or str(obj) if you prefer strings
        return super(DecimalEncoder, self).default(obj)

def process_async_response(job_id):
    textract = boto3.client("textract")

    response = textract.get_expense_analysis(JobId=job_id)

    pages = [response]
    next_token = response.get("NextToken")

    while next_token:
        response = textract.get_expense_analysis(JobId=job_id, NextToken=next_token)
        pages.append(response)
        next_token = response.get("NextToken")

    summary_fields_per_page, line_items_per_page = extract_expense_data_from_pages(pages)

    return summary_fields_per_page, line_items_per_page, response


def extract_expense_data_from_pages(pages):
    summary_fields_per_page = []
    line_items_per_page = []
    required_summary_fields = {
        "INVOICE_RECEIPT_DATE",
        "INVOICE_RECEIPT_ID",
        "VENDOR_NAME",
        "RECEIVER_NAME",
        "PO_NUMBER",
        "TOTAL",
        "SUBTOTAL",
        "TAX",
        "VENDOR_VAT_NUMBER",
        "RECEIVER_VAT_NUMBER"
    }

    required_line_item_fields = {
        "ITEM",
        "QUANTITY",
        "PRICE",
        "UNIT_PRICE"
    }

    for page_num, page in enumerate(pages, start=1):
        page_summary_fields = {}
        page_line_items = []

        for document in page.get('ExpenseDocuments', []):
            # Process summary fields with confidence scores
            for summary_field in document.get('SummaryFields', []):
                field_type = summary_field.get('Type', {}).get('Text')
                if field_type in required_summary_fields:
                    value = summary_field.get('ValueDetection', {}).get('Text', 'Unknown')
                    confidence = Decimal(str(summary_field.get('ValueDetection', {}).get('Confidence', 0.0)))
                    page_summary_fields[field_type] = {
                        "value": value,
                        "confidence": confidence
                    }

            # Process line items with confidence scores
            for line_item_group in document.get('LineItemGroups', []):
                for line_item in line_item_group.get('LineItems', []):
                    line_item_data = {}
                    for field in line_item.get('LineItemExpenseFields', []):
                        field_type = field.get('Type', {}).get('Text')
                        if field_type in required_line_item_fields:
                            value = field.get('ValueDetection', {}).get('Text', 'Unknown')
                            confidence = Decimal(str(field.get('ValueDetection', {}).get('Confidence', 0.0)))
                            line_item_data[field_type] = {
                                "value": value,
                                "confidence": confidence
                            }
                    if line_item_data:
                        page_line_items.append(line_item_data)

        if page_summary_fields:
            summary_fields_per_page.append({"page": page_num, "summary_fields": page_summary_fields})
        if page_line_items:
            line_items_per_page.append({"page": page_num, "line_items": page_line_items})

    return summary_fields_per_page, line_items_per_page

def save_results_to_s3(filename, summary_fields, line_items, bucket_name, prefix):
    s3 = boto3.client("s3")
    
    # Prepare the results to save
    results = {
        "summary_fields": summary_fields,
        "line_items": line_items
    }
    
    # Extract tenantId, sub, and invoicename from the filename path
    path_parts = filename.split('/')
    invoicename = path_parts[-1].split('.')[0]  # Extract 'invoicename' from 'invoicename.png'
    tenant_id = path_parts[-3]
    sub = path_parts[-2]

    # Generate the JSON file path and key
    results_json_key_name = f"{invoicename}_results.json"
    results_json = f"/tmp/{results_json_key_name}"

    # Save the results to a local JSON file
    with open(results_json, 'w') as f:
        json.dump(results, f, cls=DecimalEncoder)
    
    # Upload the JSON file to S3
    s3.upload_file(Filename=results_json, Bucket=bucket_name, Key=f"{prefix}/{tenant_id}/{sub}/{invoicename}/{results_json_key_name}")

    # Optionally, clean up the temporary file after upload
    os.remove(results_json)
