import io
import json
import sys
import traceback
from PIL import Image, ImageDraw
from PyPDF2 import PdfReader
import numpy as np
from pdf2image import convert_from_bytes
import logger
import logging
import os

poppler_path = "/opt/bin"

def process_error():
    ex_type, ex_value, ex_traceback = sys.exc_info()
    traceback_string = traceback.format_exception(ex_type, ex_value, ex_traceback)
    error_msg = json.dumps(
        {
            "errorType": ex_type.__name__,
            "errorMessage": str(ex_value),
            "stackTrace": traceback_string,
        }
    )
    return error_msg

SUMMARY_FIELD_COLORS = {
    "INVOICE_RECEIPT_DATE": (0, 123, 255),  # Azure
    "INVOICE_RECEIPT_ID": (167, 252, 0),   # Spring bud
    "VENDOR_NAME": (80, 200, 120),             # Emerald Green
    "RECEIVER_NAME": (255, 0, 79),           # Red
    "PO_NUMBER": (255, 0, 255),             # Magenta
    "TOTAL": (233, 116, 81),                # Burnt Sienna
    "SUBTOTAL": (226, 185, 247),            # Lilac
    "TAX": (191, 0, 255),                   # Electic purple
    "VENDOR_VAT_NUMBER": (242, 92, 84),     # Peach
    "RECEIVER_VAT_NUMBER": (87, 204, 153)   # Green
}

# Color for line item values
LINE_ITEM_COLOR = (255, 165, 0)  # Orange

required_summary_fields = SUMMARY_FIELD_COLORS.keys()
required_line_item_fields = {
    "ITEM",
    "QUANTITY",
    "PRICE",
    "UNIT_PRICE"
}

def draw_bounding_box(draw, image_size, bounding_box, color):
    try:
        width, height = image_size

        # Extract the bounding box coordinates
        left = bounding_box['Left'] * width
        top = bounding_box['Top'] * height
        box_width = bounding_box['Width'] * width
        box_height = bounding_box['Height'] * height

        # Draw the bounding box on the image
        top_left = (left, top)
        bottom_right = (left + box_width, top + box_height)
        draw.rectangle([top_left, bottom_right], outline=color, width=2)
    except Exception as e:
        logging.error(f"Error drawing bounding box: {e}")

def get_image(s3_client, bucket_name, filename):
    file_obj = s3_client.get_object(Bucket=bucket_name, Key=filename)
    file_content = file_obj['Body'].read()

    image = Image.open(io.BytesIO(file_content))
    return image, image.size

def extract_images_from_pdf(document_content):
    pages = convert_from_bytes(document_content, poppler_path=poppler_path)
    processed_images = []
    for pil_image in pages:
        width, height = pil_image.size
        processed_images.append((pil_image, (width, height)))  # Adjust to return a tuple
    return processed_images

def save_image_as_png(image, s3_client, bucket_name, key):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=buffer, ContentType='image/png')

async def process_image(textract_response, s3_client, bucket_name, filename, prefix):
    try:
        # Extract tenantId, sub, and invoicename from the filename path
        path_parts = filename.split('/')
        tenant_id = path_parts[-3]
        sub = path_parts[-2]
        invoicename = path_parts[-1].split('.')[0]
        
        is_pdf = filename.lower().endswith('.pdf')
        if is_pdf:
            document_obj = s3_client.get_object(Bucket=bucket_name, Key=filename)
            document_content = document_obj['Body'].read()
            images = extract_images_from_pdf(document_content)
            print("Successfully converted PDF to images")
        else:
            image, image_size = get_image(s3_client, bucket_name, filename)
            images = [(image, image_size)]

        for idx, (image, image_size) in enumerate(images):
            draw = ImageDraw.Draw(image)

            # Process the textract response to draw bounding boxes
            for document in textract_response.get("ExpenseDocuments", []):
                for field in document.get("SummaryFields", []):
                    field_type = field["Type"]["Text"]
                    if field_type in required_summary_fields:
                        bounding_box = field.get('ValueDetection', {}).get('Geometry', {}).get('BoundingBox', {})
                        if bounding_box:
                            draw_bounding_box(draw, image_size, bounding_box, SUMMARY_FIELD_COLORS.get(field_type, (255, 255, 255)))
                        else:
                            logging.warning(f"Bounding box not found for field type: {field_type}")

                # Draw bounding boxes for line items
                for group in document.get("LineItemGroups", []):
                    for item in group.get("LineItems", []):
                        for field in item.get("LineItemExpenseFields", []):
                            if field["Type"]["Text"] in required_line_item_fields:
                                bounding_box = field.get('ValueDetection', {}).get('Geometry', {}).get('BoundingBox', {})
                                if bounding_box:
                                    draw_bounding_box(draw, image_size, bounding_box, LINE_ITEM_COLOR)
                                else:
                                    logging.warning(f"Bounding box not found for line item field type: {field['Type']['Text']}")

            # Save the processed image back to S3
            page_suffix = f'_page_{idx + 1}' if is_pdf else ''
            # output_key = f"{prefix}/{filename.split('/')[-1].split('.')[0]}/{filename.split('/')[-1].split('.')[0]}{page_suffix}.png"
            output_key = f"{prefix}/{tenant_id}/{sub}/{invoicename}/{invoicename}{page_suffix}.png"
            save_image_as_png(image, s3_client, bucket_name, output_key)

        return {
            "statusCode": 200,
            "body": "Successfully uploaded bounded box image",
        }
    except Exception as e:
        logging.error(f"Error processing image: {e}")
        return {
            "statusCode": 500,
            "body": "Error processing image",
        }