from pprint import pprint
import os
import boto3
from botocore.exceptions import ClientError
import uuid
import json
import logger
import random
import threading
import metrics_manager
from document_models import Document
from types import SimpleNamespace
from boto3.dynamodb.conditions import Key

table_name = os.environ["DOCUMENT_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)

        
def get_document(event, key):
    try:
        shard_id, document_id = key.split(":")

        # Retrieve the document from the database
        response = table.get_item(
            Key={"shardId": shard_id, "documentId": document_id},
            ReturnConsumedCapacity="TOTAL",
        )
        item = response.get("Item")

        if not item:
            return None

        # Extract pages data
        pages = item.get("documentData", {}).get("pages", [])

        # Create a Document instance with the retrieved data
        document = Document(
            shard_id=shard_id,
            document_id=document_id,
            pages=pages,
            image_key=item.get("documentData", {}).get("image_key")
        )

        # Record metrics for read capacity
        metrics_manager.record_metric(
            event,
            "ReadCapacityUnits",
            "Count",
            response["ConsumedCapacity"]["CapacityUnits"],
        )
    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error getting a document", e)
    else:
        logger.info("GetItem succeeded: " + str(document))
        return document



def delete_document(event, key):
    try:
        print("key:", key)
        shard_id = key.split(":")[0]
        document_id = key.split(":")[1]

        response = table.delete_item(
            Key={"shardId": shard_id, "documentId": document_id},
            ReturnConsumedCapacity="TOTAL",
        )

        metrics_manager.record_metric(
            event,
            "WriteCapacityUnits",
            "Count",
            response["ConsumedCapacity"]["CapacityUnits"],
        )
    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error deleting a document", e)
    else:
        logger.info("DeleteItem succeeded:")
        return response

# TODO: Implement this method
def create_document(event, payload):
    tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_id = event["requestContext"]["authorizer"]["userId"]

    shard_id = f"{tenant_id}-{user_id}"
    created_documents = []

    try:
        for item in payload:
            document_id = str(uuid.uuid4())

            pages = []

            for page in item.get("pages", []):
                page_data = {
                    "image": page["image"],
                    "boxed_images": page.get("boxed_images", []),
                    "summary_fields": page.get("summary_fields", {}),
                    "line_items": page.get("line_items", [])
                }
                pages.append(page_data)

            response = table.put_item(
                Item={
                    "shardId": shard_id,
                    "documentId": document_id,
                    "documentData": {
                        "image_key": item["image_key"],
                        "pages": pages
                    }
                },
                ReturnConsumedCapacity="TOTAL",
            )

            metrics_manager.record_metric(
                event,
                "WriteCapacityUnits",
                "Count",
                response["ConsumedCapacity"]["CapacityUnits"],
            )

            created_documents.append({
                "shardId": shard_id,
                "documentId": document_id,
                "image_key": item["image_key"],
                "pages": pages
            })

    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error adding documents", e)
    else:
        logger.info("PutItem succeeded:")
        return created_documents




def update_document(event, payload, key):
    try:
        shard_id, document_id = key.split(":")

        # Prepare the pages data
        pages = []
        for item in payload:
            page_data = {
                "image": item["image_key"],
                "boxed_images": item.get("boxed_images", []),
                "summary_fields": item.get("pages", [{}])[0].get("summary_fields", {}),
                "line_items": item.get("pages", [{}])[0].get("line_items", [])
            }
            pages.append(page_data)

        # Create a Document instance
        document = Document(
            shard_id=shard_id,
            document_id=document_id,
            pages=pages,
            image_key=payload[0]["image_key"]  # Assuming the first page's image_key is representative
        )

        # Update the document in the database
        response = table.update_item(
            Key={"shardId": document.shard_id, "documentId": document.document_id},
            UpdateExpression="""
                set documentData.image_key=:image_key,
                    documentData.pages=:pages
            """,
            ExpressionAttributeValues={
                ":image_key": document.image_key,
                ":pages": document.pages
            },
            ReturnValues="UPDATED_NEW",
            ReturnConsumedCapacity="TOTAL",
        )

        metrics_manager.record_metric(
            event,
            "WriteCapacityUnits",
            "Count",
            response["ConsumedCapacity"]["CapacityUnits"],
        )
    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error updating a document", e)
    else:
        logger.info("UpdateItem succeeded:")
        return document



def get_documents(event, tenantId, userId):
    get_all_documents_response = []
    try:
        shardId = tenantId + "-" + userId
        __get_tenant_data(shardId, get_all_documents_response, table, event)
    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error getting all documents", e)
    else:
        logger.info("Get documents succeeded")
        return get_all_documents_response


def __get_tenant_data(shardId, get_all_documents_response, table, event):
    logger.info(shardId)
    
    # Query the table for all documents belonging to the shardId
    response = table.query(
        KeyConditionExpression=Key("shardId").eq(shardId),
        ReturnConsumedCapacity="TOTAL",
    )

    for item in response.get("Items", []):
        # Extract pages data from each document item
        pages = item.get("documentData", {}).get("pages", [])

        # Create a Document instance for each retrieved item
        document = Document(
            shard_id=item.get("shardId"),
            document_id=item.get("documentId"),
            pages=pages,
            image_key=item.get("documentData", {}).get("image_key")
        )

        # Append the document to the response list
        get_all_documents_response.append(document)

    # Record metrics for read capacity
    metrics_manager.record_metric(
        event,
        "ReadCapacityUnits",
        "Count",
        response.get("ConsumedCapacity", {}).get("CapacityUnits", 0),
    )





def __get_dynamodb_table(event, dynamodb):
    accesskey = event["requestContext"]["authorizer"]["accesskey"]
    secretkey = event["requestContext"]["authorizer"]["secretkey"]
    sessiontoken = event["requestContext"]["authorizer"]["sessiontoken"]
    dynamodb = boto3.resource(
        "dynamodb",
        aws_access_key_id=accesskey,
        aws_secret_access_key=secretkey,
        aws_session_token=sessiontoken,
    )

    return dynamodb.Table(table_name)
