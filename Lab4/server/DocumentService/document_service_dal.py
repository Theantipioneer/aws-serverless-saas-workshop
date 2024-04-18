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
from document_models import Entity
from types import SimpleNamespace
from boto3.dynamodb.conditions import Key

table_name = os.environ["DOCUMENT_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)




def get_document(event, key):
    try:
        shard_id = key.split(":")[0]
        document_id = key.split(":")[1]

        response = table.get_item(
            Key={"shardId": shard_id, "documentId": document_id},
            ReturnConsumedCapacity="TOTAL",
        )
        item = response.get("Item")

        if not item:
            return None

        entity_data = item.get("documentData", {}).get("entity", {})
        entity = Entity(
            invoice_number=entity_data.get("invoice_number"),
            invoice_date=entity_data.get("invoice_date"),
            total_amount=entity_data.get("total_amount"),
            vat_amount=entity_data.get("vat_amount"),
        )

        document = Document(
            shard_id,
            document_id,
            item.get("documentData", {}).get("title"),
            item.get("documentData", {}).get("image_key"),
            entity,
        )

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
        logger.info("GetItem succeeded:" + str(document))
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

    document_id = str(uuid.uuid4())

    try:
        response = table.put_item(
            Item={
                "shardId": shard_id,
                "documentId": document_id,
                "documentData": {
                    "title": payload.title,
                    "image_key": payload.image_key,
                    "entity": {
                        "invoice_number": payload.entity.invoice_number,
                        "invoice_date": payload.entity.invoice_date,
                        "total_amount": payload.entity.total_amount,
                        "vat_amount": payload.entity.vat_amount,
                    }
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
    except ClientError as e:
        logger.error(e.response["Error"]["Message"])
        raise Exception("Error adding a document", e)
    else:
        logger.info("PutItem succeeded:")
        # Return the created document
        return {
            "shardId": shard_id,
            "documentId": document_id,
            "title": payload.title,
            "image_key": payload.image_key,
            "entity": {
                "invoice_number": payload.entity.invoice_number,
                "invoice_date": payload.entity.invoice_date,
                "total_amount": payload.entity.total_amount,
                "vat_amount": payload.entity.vat_amount,
            }
        }


def update_document(event, payload, key):
    try:
        shard_id = key.split(":")[0]
        document_id = key.split(":")[1]

        entity_data = {
            "invoice_number": payload.entity.invoice_number,
            "invoice_date": payload.entity.invoice_date,
            "total_amount": payload.entity.total_amount,
            "vat_amount": payload.entity.vat_amount,
        }
        entity = Entity(**entity_data)

        document = Document(
            shard_id,
            document_id,
            payload.title,
            payload.image_key,
            entity
        )

        response = table.update_item(
            Key={"shardId": document.shard_id, "documentId": document.document_id},
            UpdateExpression="set documentData.title=:title, documentData.image_key=:image_key, documentData.entity=:entity",
            ExpressionAttributeValues={
                ":title": document.title,
                ":image_key": document.image_key,
                ":entity": {
                    "invoice_number": document.entity.invoice_number,
                    "invoice_date": document.entity.invoice_date,
                    "total_amount": document.entity.total_amount,
                    "vat_amount": document.entity.vat_amount,
                }
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
    response = table.query(
        KeyConditionExpression=Key("shardId").eq(shardId),
        ReturnConsumedCapacity="TOTAL",
    )
    for item in response.get("Items", []):
        entity_data = item.get("documentData", {}).get("entity", {})
        entity = Entity(
            invoice_number=entity_data.get("invoice_number"),
            invoice_date=entity_data.get("invoice_date"),
            total_amount=entity_data.get("total_amount"),
            vat_amount=entity_data.get("vat_amount"),
        )

        document = Document(
            item.get("shardId"),
            item.get("documentId"),
            item.get("documentData", {}).get("title"),
            item.get("documentData", {}).get("image_key"),
            entity,
        )
        get_all_documents_response.append(document)

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
