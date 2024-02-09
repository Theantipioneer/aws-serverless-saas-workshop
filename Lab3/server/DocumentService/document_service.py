# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import utils
import logger
import metrics_manager
import document_service_dal
from decimal import Decimal
from aws_lambda_powertools import Tracer
from types import SimpleNamespace

tracer = Tracer()


@tracer.capture_lambda_handler
def get_document(event, context):
    tenantId = event["requestContext"]["authorizer"]["tenantId"]
    tracer.put_annotation(key="TenantId", value=tenantId)

    logger.log_with_tenant_context(event, "Request received to get a document")
    params = event["pathParameters"]
    logger.log_with_tenant_context(event, params)
    key = params["id"]
    logger.log_with_tenant_context(event, key)
    document = document_service_dal.get_document(event, key)

    logger.log_with_tenant_context(event, "Request completed to get a document")
    metrics_manager.record_metric(event, "SingleDocumentRequested", "Count", 1)
    return utils.generate_response(document)


@tracer.capture_lambda_handler
def create_document(event, context):
    tenantId = event["requestContext"]["authorizer"]["tenantId"]
    tracer.put_annotation(key="TenantId", value=tenantId)

    logger.log_with_tenant_context(event, "Request received to create a document")
    payload = json.loads(
        event["body"], object_hook=lambda d: SimpleNamespace(**d), parse_float=Decimal
    )
    document = document_service_dal.create_document(event, payload)
    logger.log_with_tenant_context(event, "Request completed to create a document")

    # TODO: Capture metrics to denote that one document was created by tenant
    metrics_manager.record_metric(event, "DocumentCreated", "Count", 1)
    return utils.generate_response(document)


@tracer.capture_lambda_handler
def update_document(event, context):
    tenantId = event["requestContext"]["authorizer"]["tenantId"]
    tracer.put_annotation(key="TenantId", value=tenantId)

    logger.log_with_tenant_context(event, "Request received to update a document")
    payload = json.loads(
        event["body"], object_hook=lambda d: SimpleNamespace(**d), parse_float=Decimal
    )
    params = event["pathParameters"]
    key = params["id"]
    document = document_service_dal.update_document(event, payload, key)
    logger.log_with_tenant_context(event, "Request completed to update a document")
    metrics_manager.record_metric(event, "DocumentUpdated", "Count", 1)
    return utils.generate_response(document)


@tracer.capture_lambda_handler
def delete_document(event, context):
    tenantId = event["requestContext"]["authorizer"]["tenantId"]
    tracer.put_annotation(key="TenantId", value=tenantId)

    logger.log_with_tenant_context(event, "Request received to delete a document")
    params = event["pathParameters"]
    key = params["id"]
    response = document_service_dal.delete_document(event, key)
    logger.log_with_tenant_context(event, "Request completed to delete a document")
    metrics_manager.record_metric(event, "DocumentDeleted", "Count", 1)
    return utils.create_success_response("Successfully deleted the document")


@tracer.capture_lambda_handler
def get_documents(event, context):
    tenantId = event["requestContext"]["authorizer"]["tenantId"]
    userId = event["requestContext"]["authorizer"]["userId"]
    tracer.put_annotation(key="TenantId", value=tenantId)
    # **get using userId rather than tenantId

    logger.log_with_tenant_context(event, "Request received to get all documents")
    response = document_service_dal.get_documents(event, tenantId, userId)
    metrics_manager.record_metric(event, "DocumentsRetrieved", "Count", len(response))
    logger.log_with_tenant_context(event, "Request completed to get all documents")
    return utils.generate_response(response)
