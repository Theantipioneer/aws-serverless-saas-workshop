# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

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

table_name = os.environ['DOCUMENT_TABLE_NAME']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(table_name)

suffix_start = 1 
suffix_end = 10

def get_document(event, key):    
    try:
        shardId = key.split(":")[0]
        documentId = key.split(":")[1] 
        logger.log_with_tenant_context(event, shardId)
        logger.log_with_tenant_context(event, documentId)
        response = table.get_item(Key={'shardId': shardId, 'documentId': documentId}, ReturnConsumedCapacity='TOTAL')
        item = response['Item']
        document = Document(item['shardId'], item['documentId'], item['invoice_number'], item['invoice_date'], item['total_amount'], item['vat_amount'], item['image_key'], item['title'])

        metrics_manager.record_metric(event, "ReadCapacityUnits", "Count", response['ConsumedCapacity']['CapacityUnits'])
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        raise Exception('Error getting a document', e)
    else:
        logger.info("GetItem succeeded:"+ str(document))
        return document

def delete_document(event, key):    
    try:
        shardId = key.split(":")[0]
        documentId = key.split(":")[1] 
        response = table.delete_item(Key={'shardId':shardId, 'documentId': documentId}, ReturnConsumedCapacity='TOTAL')

        metrics_manager.record_metric(event, "WriteCapacityUnits", "Count", response['ConsumedCapacity']['CapacityUnits'])
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        raise Exception('Error deleting a document', e)
    else:
        logger.info("DeleteItem succeeded:")
        return response

#TODO: Implement this method
def create_document(event, payload):
    tenantId = event['requestContext']['authorizer']['tenantId']    
    
    suffix = random.randrange(suffix_start, suffix_end)
    shardId = tenantId+"-"+str(suffix)

    document = Document(shardId, str(uuid.uuid4()), payload.invoice_number,payload.invoice_date, payload.total_amount, payload.vat_amount, payload.image_key, payload.title)
    
    try:
        response = table.put_item(
            Item=
                {
                    'shardId': shardId,  
                    'documentId': document.documentId,
                    'invoice_number': document.invoice_number,
                    'invoice_date': document.invoice_date,
                    'total_amount': document.total_amount,
                    'vat_amount': document.vat_amount,
                    'image_key': document.image_key,
                    'title': document.title
                }, 
                ReturnConsumedCapacity='TOTAL'
        )

        metrics_manager.record_metric(event, "WriteCapacityUnits", "Count", response['ConsumedCapacity']['CapacityUnits'])
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        raise Exception('Error adding a document', e)
    else:
        logger.info("PutItem succeeded:")
        return document


def update_document(event, payload, key):    
    try:
        shardId = key.split(":")[0]
        documentId = key.split(":")[1] 
        logger.log_with_tenant_context(event, shardId)
        logger.log_with_tenant_context(event, documentId)

        document = Document(shardId,documentId,payload.invoice_number, payload.invoice_date, payload.total_amount, payload.vat_amount, payload.image_key, payload.title)

        response = table.update_item(Key={'shardId':document.shardId, 'documentId': document.documentId},
        UpdateExpression="set invoice_number=:invoice_number, #n=:documentDate, total_amount=:total_amount, vat_amount=:vat_amount, image_key=:image_key, title=:title",
        ExpressionAttributeNames= {'#n':'invoice_date'},
        ExpressionAttributeValues={
            ':invoice_number': document.invoice_number,
            ':documentName': document.invoice_date,
            ':total_amount': document.total_amount,
            ':vat_amount': document.vat_amount,
            ':image_key': document.image_key,
            ':title': document.title
        },
        ReturnValues="UPDATED_NEW", 
        ReturnConsumedCapacity='TOTAL')

        metrics_manager.record_metric(event, "WriteCapacityUnits", "Count", response['ConsumedCapacity']['CapacityUnits'])
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        raise Exception('Error updating a document', e)
    else:
        logger.info("UpdateItem succeeded:")
        return document        

def get_documents(event, tenantId):    
    get_all_documents_response =[]
    try:
        __query_all_partitions(tenantId,get_all_documents_response, table, event)
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        raise Exception('Error getting all documents', e)
    else:
        logger.info("Get documents succeeded")
        return get_all_documents_response

def __query_all_partitions(tenantId,get_all_documents_response, table, event):
    threads = []    
    
    for suffix in range(suffix_start, suffix_end):
        partition_id = tenantId+'-'+str(suffix)
        
        thread = threading.Thread(target=__get_tenant_data, args=[partition_id, get_all_documents_response, table, event])
        threads.append(thread)
        
    # Start threads
    for thread in threads:
        thread.start()
    # Ensure all threads are finished
    for thread in threads:
        thread.join()
           
def __get_tenant_data(partition_id, get_all_documents_response, table, event):    
    logger.info(partition_id)
    response = table.query(KeyConditionExpression=Key('shardId').eq(partition_id), ReturnConsumedCapacity='TOTAL')    
    if (len(response['Items']) > 0):
        for item in response['Items']:
            document = Document(item['shardId'], item['documentId'], item['invoice_number'], item['invoice_date'], item['total_amount'], item['vat_amount'], item['image_key'], item['title'])
            get_all_documents_response.append(document)

    metrics_manager.record_metric(event, "ReadCapacityUnits", "Count", response['ConsumedCapacity']['CapacityUnits'])        
