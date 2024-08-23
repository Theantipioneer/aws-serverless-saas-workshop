import io
import json
import sys
import traceback
from PIL import Image, ImageDraw
from PyPDF2 import PdfReader
import numpy as np
from pdf2image import convert_from_bytes
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
    "INVOICE_RECEIPT_DATE": (255, 0, 0),  # Blue
    "INVOICE_RECEIPT_ID": (0, 255, 0),    # Green
    "VENDOR_NAME": (0, 0, 255),           # Red
    "RECEIVER_NAME": (255, 255, 0),       # Cyan
    "PO_NUMBER": (255, 0, 255),           # Magenta
    "TOTAL": (205, 60, 234),              # pink
    "SUBTOTAL": (226, 185, 247),          # Lilac
    "TAX": (255, 145, 0),                 # Orange
    "VENDOR_VAT_NUMBER": (0, 0, 128),     # Navy
    "RECEIVER_VAT_NUMBER": (128, 128, 0)  # Olive
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

def draw_bounding_box(image, bbox, color, thickness):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    left = bbox["Left"] * width
    top = bbox["Top"] * height
    right = (bbox["Left"] + bbox["Width"]) * width
    bottom = (bbox["Top"] + bbox["Height"]) * height

    draw.rectangle([(left, top), (right, bottom)], outline=color, width=thickness)


def get_width_height(s3, bucketname, filename):
    file_obj = s3.get_object(Bucket=bucketname, Key=filename)
    file_content = file_obj["Body"].read()

    image = Image.open(io.BytesIO(file_content))
    width, height = image.size
    return image, height, width

def extract_images_from_pdf(s3, bucketname, filename):
    file_obj = s3.get_object(Bucket=bucketname, Key=filename)
    file_content = file_obj['Body'].read()
    images = convert_from_bytes(file_content, poppler_path=poppler_path)
    
    processed_images = []
    for pil_image in images:
        width, height = pil_image.size
        processed_images.append((pil_image, height, width))

    return processed_images

def save_image_as_png(image, s3, bucketname, key):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    s3.put_object(Bucket=bucketname, Key=key, Body=buffer, ContentType='image/png')

    
def process_image(response, s3, bucketname, filename, prefix):
    try:
        is_pdf = filename.lower().endswith('.pdf')
        if is_pdf:
            images = extract_images_from_pdf(s3, bucketname, filename)
            print("Successfully converted pdf to image")
        else:
            image, height, width = get_width_height(s3, bucketname, filename)
            images = [(image, height, width)]
        
        for idx, (image, _, _) in enumerate(images):
            # Draw bounding boxes for summary fields
            for document in response.get("ExpenseDocuments", []):
                for field in document.get("SummaryFields", []):
                    field_type = field["Type"]["Text"]
                    if field_type in required_summary_fields:
                        if "ValueDetection" in field and "Geometry" in field["ValueDetection"]:
                            color = SUMMARY_FIELD_COLORS[field_type]
                            draw_bounding_box(
                                image,
                                field["ValueDetection"]["Geometry"]["BoundingBox"],
                                color,
                                2
                            )
                        else:
                            logging.warning(f"Geometry not found for field type: {field_type}")
    
            # Draw bounding boxes for line items
            for document in response.get("ExpenseDocuments", []):
                for group in document.get("LineItemGroups", []):
                    for item in group.get("LineItems", []):
                        for field in item.get("LineItemExpenseFields", []):
                            if field["Type"]["Text"] in required_line_item_fields:
                                if "ValueDetection" in field and "Geometry" in field["ValueDetection"]:
                                    draw_bounding_box(
                                        image,
                                        field["ValueDetection"]["Geometry"]["BoundingBox"],
                                        LINE_ITEM_COLOR,
                                        2
                                    )
                                else:
                                    logging.warning(f"Geometry not found for line item field type: {field['Type']['Text']}")

            # Save the processed image with bounding boxes to S3
            save_image_as_png(image, s3, bucketname, f'{prefix}/{filename.split("/")[-1].split(".")[0]}/{filename.split("/")[-1].split(".")[0]}_page_{idx + 1}.png')
        return {
                "statusCode": 200,
                "body": json.dumps("Successfully uploaded bounded box image"),
            }
    except Exception as e:
        logging.error(f"Error processing image: {e}")
        return {
                "statusCode": 500,
                "body": json.dumps("Error processing image"),
            }
    except Exception as e:
        print(f"Error processing response: {e}")
        print(process_error())
        return False
