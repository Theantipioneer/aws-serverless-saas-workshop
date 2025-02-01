import json
import utils
import boto3
import base64
import logger
import os
import requests
from botocore.exceptions import ClientError
import upload_helper 
from typing import List, Dict, Union
from dataclasses import dataclass
import io

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
ANALYSE_EXPENSE_FUNCTION = os.environ["ANALYSE_EXPENSE_FUNCTION"]

class DocumentValidationError(Exception):
    def __init__(self, message: str, file_name: str = "", error_code: str = "VALIDATION_ERROR"):
        self.message = message
        self.file_name = file_name
        self.error_code = error_code
        super().__init__(self.message)

class DocumentValidator:
    ALLOWED_FORMATS = {'.pdf', '.png', '.jpg', '.jpeg'}
    ALLOWED_MIME_TYPES = {
        'application/pdf': '.pdf',
        'image/png': '.png',
        'image/jpeg': ['.jpg', '.jpeg']
    }
    MAX_FILE_SIZE_MB = 25
    MAX_DOCUMENTS = 10
    MIN_FILE_SIZE_BYTES = 100
    
    def validate_documents(self, documents: List[Dict]) -> List[Dict]:
        """Validates all documents and returns list of validation errors if any"""
        validation_errors = []
        
        logger.info(f"Starting document validation for {len(documents) if documents else 0} documents")

        if not documents:
            logger.error("No documents found in request")
            raise DocumentValidationError("No documents found in the request body", error_code="NO_DOCUMENTS")

        if len(documents) > self.MAX_DOCUMENTS:
            logger.error(f"Document count ({len(documents)}) exceeds maximum limit of {self.MAX_DOCUMENTS}")
            raise DocumentValidationError(
                f"Upload attempt exceeds limit of {self.MAX_DOCUMENTS} documents",
                error_code="TOO_MANY_DOCUMENTS"
            )

        for document in documents:
            try:
                self._validate_single_document(document)
            except DocumentValidationError as e:
                logger.error(f"Validation error for document: {e.file_name}, Error: {e.message}, Code: {e.error_code}")
                validation_errors.append({
                    "file_name": e.file_name,
                    "error": e.message,
                    "error_code": e.error_code
                })

        if validation_errors:
            # Don't convert to string - keep as list
            raise DocumentValidationError(
                validation_errors[0]["error"],  # Use the first error message as the main error
                error_code="VALIDATION_ERRORS",
                file_name=json.dumps(validation_errors)
            )

        logger.info("Document validation completed successfully")
        return documents
    
    def _validate_single_document(self, document: Dict):
        logger.info(f"Validating single document: {document.get('file_name', 'unnamed')}")

        # Validate file name
        file_name = document.get('file_name', '').lower()
        if not file_name:
            raise DocumentValidationError(
                "Document does not contain a valid 'file_name' key or the value is empty",
                error_code="INVALID_FILENAME"
            )

        ext = os.path.splitext(file_name)[1]
        if ext not in self.ALLOWED_FORMATS:
            raise DocumentValidationError(
                f"Unsupported file format. Allowed formats are: {', '.join(self.ALLOWED_FORMATS)}",
                file_name=file_name,
                error_code="INVALID_FORMAT"
            )

        # Validate file content
        try:
            file_content = base64.b64decode(document.get('file', ''))
        except Exception as e:
            logger.error(f"Base64 decode error for file {file_name}: {str(e)}")

            raise DocumentValidationError(
                "Invalid file content encoding",
                file_name=file_name,
                error_code="INVALID_ENCODING"
            )

        # Check file size
        file_size = len(file_content)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"File size for {file_name}: {file_size_mb:.2f} MB")
        if file_size < self.MIN_FILE_SIZE_BYTES:
            logger.error(f"File {file_name} is too small: {file_size} bytes")

            raise DocumentValidationError(
                "File appears to be empty",
                file_name=file_name,
                error_code="EMPTY_FILE"
            )
        
        if file_size > self.MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.error(f"File {file_name} exceeds size limit: {file_size_mb:.2f} MB")

            raise DocumentValidationError(
                f"File size exceeds the maximum allowed size of {self.MAX_FILE_SIZE_MB} MB",
                file_name=file_name,
                error_code="FILE_TOO_LARGE"
            )
            

def lambda_handler(event, context):
    try:
        
        logger.info("Processing API Gateway event")
        try:
            body = json.loads(event['body'])
            documents = body.get("documents", [])

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {str(e)}")
            return utils.generate_response({
                "error": "Invalid JSON in request body",
                "error_code": "INVALID_JSON"
            })
        
        if not documents:
            logger.error("No documents found in request")
            return utils.generate_response({
                "error": "No documents found in request",
                "error_code": "NO_DOCUMENTS"
            })
        
        processed_documents = []
        for doc in documents:
            file_name = doc.get('file_name', '')
            logger.info(f'Processing file: {file_name}')
            processed_documents.append(doc)
        
                
        # Initialize the DocumentValidator
        validator = DocumentValidator()
        
        # Validate all documents
        try:
            validated_documents = validator.validate_documents(processed_documents)
        except DocumentValidationError as e:
            logger.info(f"Document validation error caught: {e.error_code}")
            
            if e.error_code == "VALIDATION_ERRORS":
                validation_errors = json.loads(e.file_name)
                return utils.generate_response({
                    "error": e.message,  # This will now be the specific error message
                    "error_code": validation_errors[0]["error_code"],  # Use the specific error code
                    "validation_errors": validation_errors
                })
            else:
                # Single validation error
                return utils.generate_response({
                    "error": e.message,
                    "error_code": e.error_code,
                    "file_name": e.file_name
                })
                
        logger.info("Document validation successful")
        
        # pre-existing code ..
        
        bucket = os.environ["BUCKET_NAME"]
        tenant_id = event["requestContext"]["authorizer"]["tenantId"]
        sub = event["requestContext"]["authorizer"]["principalId"]
        jwt_token = event["headers"]["Authorization"]
        
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
        logger.error(f"Unexpected error in lambda handler: {str(e)}")
        return utils.generate_response({
            "error": "Error processing upload",
            "error_code": "UNEXPECTED_ERROR",
            "details": str(e)
        })