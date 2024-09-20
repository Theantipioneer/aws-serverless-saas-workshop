import json
import utils
import boto3
import base64
import logger
import os
import requests
from botocore.exceptions import ClientError
import upload_helper 

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

ANALYSE_EXPENSE_FUNCTION = os.environ["ANALYSE_EXPENSE_FUNCTION"]


def lambda_handler(event, context):
    try:
        # Parse the JSON body
        body = json.loads(event['body'])
        documents = body.get('documents', [])
        
        if not documents:
            return utils.generate_response({"error": "'documents' key not found in the request body"})

        if len(documents) > 25:
            return utils.generate_response({"error": "Upload attempt exceeds limit of 25 documents"})
        
        allowed_formats = {'.pdf', '.png', '.jpg', '.jpeg'}
        max_file_size_mb = 4


        # Check document formats
        for document in documents:
            # Access the 'file_name' key
            file_name = document.get('file_name', '').lower()  # Extract and lower case the file name

            if not file_name:
                return utils.generate_response({"error": "Document does not contain a valid 'file_name' key or the value is empty"})

            ext = os.path.splitext(file_name)[1]
            if ext not in allowed_formats:
                return utils.generate_response({
                    "error": f"Unsupported file format for document: {document}. Allowed formats are: {', '.join(allowed_formats)}"
                })
                
            # Access the 'file_size' key (assuming the file size is passed in bytes)
            # file_size = document.get('file_size')
            # if file_size is None or not isinstance(file_size, (int, float)):
            #     return utils.generate_response({"error": f"Document '{file_name}' does not contain a valid 'file_size' key or the value is not numeric"})

            # Check if the file size exceeds the maximum allowed size
            # if file_size > max_file_size_mb * 1024 * 1024:
            #     return utils.generate_response({
            #         "error": f"File size of '{file_name}' exceeds the maximum allowed size of {max_file_size_mb} MB"
            #     })

        bucket = os.environ["BUCKET_NAME"]
        tenant_id = event["requestContext"]["authorizer"]["tenantId"]
        sub = event["requestContext"]["authorizer"]["principalId"]
    
        jwt_token = event["headers"]["Authorization"]
        
        # Log the request
        logger.info(f"Request received to upload documents for tenant {tenant_id}")

        # Check tenant balance before uploading
        headers = {"Authorization": jwt_token}
        url = f"https://uh3wulfyxd.execute-api.eu-west-1.amazonaws.com/prod/tenant/{tenant_id}/balance"

        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return utils.generate_response({'error': 'Failed to check tenant balance'})

        tenant_data = response.json()
        tenant_balance = tenant_data.get('tenantBalance', 0)
        
        total_pages = 0
        for doc in documents:
            file_content = base64.b64decode(doc['file'])
            doc_type = doc['file_name'].split(".")[-1].lower()
            total_pages += upload_helper.count_pages(file_content, doc_type)
        
        print("tenant balance:", tenant_balance)
        print("total pages:", total_pages)
        if tenant_balance < total_pages:
            return utils.generate_response({'error': 'Insufficient credits. Buy more credits on your admin site. '})

        uploaded_documents = []

        for doc in documents:
            file_content = base64.b64decode(doc['file'])
            file_name = doc['file_name']

            # Generate a unique key for the document
            uuid_filename = upload_helper.generate_unique_key(file_content, file_name)
            upload_key = f"analyse-expense/{tenant_id}/{sub}/{uuid_filename}"
            try:
                # Upload the file to S3
                s3_client.put_object(Bucket=bucket, Key=upload_key, Body=file_content)
                uploaded_documents.append(upload_key)
            except ClientError as e:
                logger.error(e.response["Error"]["Message"])
                raise Exception("Error uploading document", e)
        
        # Return a response indicating the upload was successful and analysis is beginning
        logger.info(f"Uploaded documents: {uploaded_documents}")
        
        # Invoke the analyse_expense function
        response = lambda_client.invoke(
            FunctionName=ANALYSE_EXPENSE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'bucket': bucket,
                'documents': uploaded_documents,
                'tenantId': tenant_id,
                'sub': sub, 
            })
        )
        # Read and parse the Payload
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))

        if response["StatusCode"] == 200:
            logger.info("Analyse expense successful")
            
            # Get the response from analyse_expense
            response_body = json.loads(response_payload['body'])
            if response_body:
                jobIds = response_body['jobIds']

                # Update tenant balance based on the total pages analyzed
                balance_response = requests.put(
                    url,
                    headers=headers,
                    json={'tenantBalance': -total_pages}
                )
    
                if balance_response.status_code != 200:
                    logger.error('Failed to update tenant balance')
                else:
                    # logger.info(f"Updated tenant balance: ")
                    logger.info(f"balance response: {balance_response} ")
                # Include processed images in the response
                return utils.generate_response({
                    "message": "Upload successful",
                    "jobIds": jobIds
                })
            else:
                logger.error(f"'total_pages_analyzed' or 'data' not found in response payload: {response_payload}")
                return utils.generate_response({"error": "'total_pages_analyzed' or 'data' not found in response payload"})
        else:
            logger.error(f"Error invoking analyse_expense function: {response}")
            return utils.generate_response({"error": "Error invoking analyse_expense function"})
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return utils.generate_response({"error": "Error processing upload", "details": str(e)})
