import sys
import os
import traceback
import logging
import requests
import json
import uuid
import boto3
from urllib.parse import unquote_plus
from urllib.parse import urlparse, unquote
from promptify import Prompter, OpenAI, Pipeline

logger = logging.getLogger()
logger.setLevel(logging.INFO)

openai_api_key = os.environ["OPENAI_API_KEY"]
model = OpenAI(openai_api_key)
prompter = Prompter("ner.jinja")
pipe = Pipeline(prompter, model)


def process_error() -> dict:
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


def extract_text(response: dict, extract_by="LINE") -> list:
    text = []
    for block in response["Blocks"]:
        if block["BlockType"] == extract_by:
            text.append(block["Text"])
    return text


def lambda_handler(event, context):
    print(f"EVENT: {json.dumps(event)}")

    textract = boto3.client("textract")
    
    jwt_token = event['requestContext']['authorizer']['jwt_bearer_token']

    def get_title_as_name(file_key):
        last_index = file_key.rfind("-")
        title = file_key[last_index + 1 :]  # omg
        return title

    try:
        bucketname = 'create-entities-uploads-acumen-154654dasfk'
        payload = json.loads(event['body'])
        key = payload.get('key', '')
        file_path = payload.get('file_path', '')
        title = get_title_as_name(key)

        logging.info(
            f"Bucket: {bucketname} ::: key: {key} ::: title: {title}:::file path: {file_path} ::: jwt: {jwt_token}"
        )

        response = textract.detect_document_text(
            Document={
                "S3Object": {
                    "Bucket": bucketname,
                    "Name": file_path,
                }
            }
        )
        logging.info(json.dumps(response))


        # change LINE by WORD if you want word level extraction
        raw_text = extract_text(response, extract_by="LINE")

        sentence = "\n".join(raw_text)

        result = pipe.fit(
            sentence,
            domain="invoicing",
            labels=["invoice_number", "invoice_date", "vat_amount", "total_amount"],
            description="Provided is text extracted from an invoice - retrieve only the invoice_number, invoice_date, vat_amount and total_amount and nothing else.",
        )

        completion_array = result[0]["parsed"]["data"]["completion"]

        modified_output = {
            item.get("T", item.get("branch", "unknown_key")): item.get(
                "E", item.get("group", "")
            )
            for item in completion_array
        }

        # Validate and manipulate the modified output
        required_keys = [
            "invoice_number",
            "invoice_date",
            "vat_amount",
            "total_amount",
        ]
        validated_output = {
            key: modified_output.get(key, "") for key in required_keys
        }

        documentEntities = {
            "title": title,
            "image_key": key,
            **validated_output,
        }
        print(documentEntities)
    
        create_document_api_endpoint = 'https://4ii59hmute.execute-api.eu-west-1.amazonaws.com/prod/document'
        headers = {'Authorization': f'Bearer {jwt_token}'}

        # Make an HTTP POST request to the Document API's create endpoint
        response = requests.post(create_document_api_endpoint, json=documentEntities, headers=headers)
    
        # Check the response status
        if response.status_code == 200:
            
            return {
                'statusCode': 200,
                'body': 'Entity created successfully.'
            }
        else:
            return {
                'statusCode': response.status_code,
                'body': 'Failed to create entity.'
            }
        
    except:
        error_msg = process_error()
        logger.error(error_msg)

    return {"statusCode": 200, "body": json.dumps("Entity processed successfully")}

















# import json
# import utils
# import logger
# import metrics_manager
# from decimal import Decimal
# from types import SimpleNamespace

# def lambda_handler(event, context):    
#     tenantId = event['requestContext']['authorizer']['tenantId']

#     logger.log_with_tenant_context(event, "Request received to create a entity")
    
#     payload = json.loads(event['body'], object_hook=lambda d: SimpleNamespace(**d), parse_float=Decimal)
    
#     logger.log_with_tenant_context(event, "Request completed to create a entity")
    
#     #TODO: Capture metrics to denote that one document was created by tenant
#     metrics_manager.record_metric(event, "EntityCreated", "Count", 1)