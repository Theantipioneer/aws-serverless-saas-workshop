# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import json
import boto3
from boto3.dynamodb.conditions import Key
import urllib.parse
import utils
from botocore.exceptions import ClientError
import logger
import requests
import metrics_manager
import auth_manager

from aws_lambda_powertools import Tracer

tracer = Tracer()

region = os.environ["AWS_REGION"]

dynamodb = boto3.resource("dynamodb")
table_tenant_details = dynamodb.Table("Acumen-TenantDetails")


# This method has been locked down to be only called from tenant registration service
def create_tenant(event, context):
    tenant_details = json.loads(event["body"])

    try:
        response = table_tenant_details.put_item(
            Item={
                "tenantId": tenant_details["tenantId"],
                "tenantName": tenant_details["tenantName"],
                "tenantAddress": tenant_details["tenantAddress"],
                "tenantEmail": tenant_details["tenantEmail"],
                "tenantPhone": tenant_details["tenantPhone"],
                "tenantTier": tenant_details["tenantTier"],
                "tenantBalance": 0,
                "isActive": True,
            }
        )

    except Exception as e:
        raise Exception("Error creating a new tenant", e)
    else:
        return utils.create_success_response("Tenant Created")


def get_tenants(event, context):

    try:
        response = table_tenant_details.scan()
    except Exception as e:
        raise Exception("Error getting all tenants", e)
    else:
        return utils.generate_response(response["Items"])


@tracer.capture_lambda_handler
def update_tenant(event, context):

    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]

    tenant_details = json.loads(event["body"])
    tenant_id = event["pathParameters"]["tenantid"]

    tracer.put_annotation(key="TenantId", value=tenant_id)

    logger.log_with_tenant_context(event, "Request received to update tenant")

    if (
        auth_manager.isTenantAdmin(user_role) and tenant_id == requesting_tenant_id
    ) or auth_manager.isSystemAdmin(user_role):

        response_update = table_tenant_details.update_item(
            Key={
                "tenantId": tenant_id,
            },
            UpdateExpression="set tenantName = :tenantName, tenantAddress = :tenantAddress, tenantEmail = :tenantEmail, tenantPhone = :tenantPhone, tenantTier=:tenantTier",
            ExpressionAttributeValues={
                ":tenantName": tenant_details["tenantName"],
                ":tenantAddress": tenant_details["tenantAddress"],
                ":tenantEmail": tenant_details["tenantEmail"],
                ":tenantPhone": tenant_details["tenantPhone"],
                ":tenantTier": tenant_details["tenantTier"],
            },
            ReturnValues="UPDATED_NEW",
        )

        logger.log_with_tenant_context(event, response_update)

        logger.log_with_tenant_context(event, "Request completed to update tenant")
        return utils.create_success_response("Tenant Updated")
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only tenant admin or system admin can update tenant!",
        )
        return utils.create_unauthorized_response()
 
        
@tracer.capture_lambda_handler
def update_balance(event, context):

    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]

    tenant_details = json.loads(event["body"])
    tenant_id = event["pathParameters"]["tenantid"]

    tracer.put_annotation(key="TenantId", value=tenant_id)

    logger.log_with_tenant_context(event, "Request received to update tenant balance")

    if (
        (auth_manager.isTenantAdmin(user_role) or auth_manager.isTenantUser(user_role)) and tenant_id == requesting_tenant_id
    ) or auth_manager.isSystemAdmin(user_role):

        # Fetch the current balance from the database
        current_balance_response = table_tenant_details.get_item(
            Key={
                "tenantId": tenant_id,
            },
            ProjectionExpression="tenantBalance",
        )

        if "Item" not in current_balance_response:
            return utils.create_failure_response("Tenant not found")

        current_balance = current_balance_response["Item"]["tenantBalance"]

        # Add or subtract the provided amount from the current balance
        amount_to_add_or_subtract = tenant_details["tenantBalance"]
        if amount_to_add_or_subtract < 0 and abs(amount_to_add_or_subtract) > current_balance:
            updated_balance = 0  # Set balance to zero if subtraction would go below zero
        else:
            updated_balance = current_balance + amount_to_add_or_subtract

        # Update the tenant balance
        response_update = table_tenant_details.update_item(
            Key={
                "tenantId": tenant_id,
            },
            UpdateExpression="set tenantBalance = :tenantBalance",
            ExpressionAttributeValues={
                ":tenantBalance": updated_balance,
            },
            ReturnValues="UPDATED_NEW",
        )

        logger.log_with_tenant_context(event, response_update)

        logger.log_with_tenant_context(event, "Request completed to update tenant balance")
        return utils.create_success_response("Balance Updated")
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only tenant admin or system admin can update tenant!",
        )
        return utils.create_unauthorized_response()


@tracer.capture_lambda_handler
def get_tenant(event, context):
    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]
    tenant_id = event["pathParameters"]["tenantid"]

    tracer.put_annotation(key="TenantId", value=tenant_id)

    logger.log_with_tenant_context(event, "Request received to get tenant details")

    if (
        auth_manager.isTenantAdmin(user_role) and tenant_id == requesting_tenant_id
    ) or auth_manager.isSystemAdmin(user_role):
        tenant_details = table_tenant_details.get_item(
            Key={
                "tenantId": tenant_id,
            },
            # AttributesToGet=[
            #     "tenantName",
            #     "tenantAddress",
            #     "tenantEmail",
            #     "tenantPhone",
            # ],
        )
        item = tenant_details["Item"]
        # tenant_info = TenantInfo(
        #     item["tenantName"],
        #     item["tenantAddress"],
        #     item["tenantEmail"],
        #     item["tenantPhone"],
        # )
        logger.log_with_tenant_context(event, item)

        logger.log_with_tenant_context(event, "Request completed to get tenant details")
        return utils.generate_response(item)
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only tenant admin or system admin can deactivate tenant!",
        )
        return utils.create_unauthorized_response()


@tracer.capture_lambda_handler
def get_balance(event, context):
    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]
    tenant_id = event["pathParameters"]["tenantid"]

    tracer.put_annotation(key="TenantId", value=tenant_id)

    logger.log_with_tenant_context(event, "Request received to get tenant details")

    if (
       (auth_manager.isTenantAdmin(user_role) or auth_manager.isTenantUser(user_role)) and tenant_id == requesting_tenant_id
    ) or auth_manager.isSystemAdmin(user_role):
        tenant_details = table_tenant_details.get_item(
            Key={
                "tenantId": tenant_id,
            },
            AttributesToGet=[
                "tenantBalance"
            ],
        )
        item = tenant_details["Item"]
        # tenant_info = TenantInfo(
        #     item["tenantName"],
        #     item["tenantAddress"],
        #     item["tenantEmail"],
        #     item["tenantPhone"],
        # )
        logger.log_with_tenant_context(event, item)

        logger.log_with_tenant_context(event, "Request completed to get tenant balance")
        return utils.generate_response(item)
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only tenant admin or system admin can access tenant details",
        )
        return utils.create_unauthorized_response()


@tracer.capture_lambda_handler
def deactivate_tenant(event, context):

    url_disable_users = os.environ["DISABLE_USERS_BY_TENANT"]
    stage_name = event["requestContext"]["stage"]
    host = event["headers"]["Host"]
    auth = utils.get_auth(host, region)
    headers = utils.get_headers(event)

    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]
    tenant_id = event["pathParameters"]["tenantid"]

    tracer.put_annotation(key="TenantId", value=tenant_id)
    logger.log_with_tenant_context(event, "Request received to deactivate tenant")

    if (
        auth_manager.isTenantAdmin(user_role) and tenant_id == requesting_tenant_id
    ) or auth_manager.isSystemAdmin(user_role):
        response = table_tenant_details.update_item(
            Key={
                "tenantId": tenant_id,
            },
            UpdateExpression="set isActive = :isActive",
            ExpressionAttributeValues={":isActive": False},
            ReturnValues="ALL_NEW",
        )

        logger.log_with_tenant_context(event, response)

        update_details = {}
        update_details["tenantId"] = tenant_id
        update_details["requestingTenantId"] = requesting_tenant_id
        update_details["userRole"] = user_role
        update_user_response = __invoke_disable_users(
            update_details, headers, auth, host, stage_name, url_disable_users
        )
        logger.log_with_tenant_context(event, update_user_response)

        logger.log_with_tenant_context(event, "Request completed to deactivate tenant")
        return utils.create_success_response("Tenant Deactivated")
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only tenant admin or system admin can deactivate tenant!",
        )
        return utils.create_unauthorized_response()


@tracer.capture_lambda_handler
def activate_tenant(event, context):
    url_enable_users = os.environ["ENABLE_USERS_BY_TENANT"]
    stage_name = event["requestContext"]["stage"]
    host = event["headers"]["Host"]
    auth = utils.get_auth(host, region)
    headers = utils.get_headers(event)

    requesting_tenant_id = event["requestContext"]["authorizer"]["tenantId"]
    user_role = event["requestContext"]["authorizer"]["userRole"]

    tenant_id = event["pathParameters"]["tenantid"]
    tracer.put_annotation(key="TenantId", value=tenant_id)

    logger.log_with_tenant_context(event, "Request received to activate tenant")

    if auth_manager.isSystemAdmin(user_role):
        response = table_tenant_details.update_item(
            Key={
                "tenantId": tenant_id,
            },
            UpdateExpression="set isActive = :isActive",
            ExpressionAttributeValues={":isActive": True},
            ReturnValues="ALL_NEW",
        )

        logger.log_with_tenant_context(event, response)

        update_details = {}
        update_details["tenantId"] = tenant_id
        update_details["requestingTenantId"] = requesting_tenant_id
        update_details["userRole"] = user_role
        update_user_response = __invoke_enable_users(
            update_details, headers, auth, host, stage_name, url_enable_users
        )
        logger.log_with_tenant_context(event, update_user_response)

        logger.log_with_tenant_context(event, "Request completed to activate tenant")
        return utils.create_success_response("Tenant Activated")
    else:
        logger.log_with_tenant_context(
            event,
            "Request completed as unauthorized. Only system admin can activate tenant!",
        )
        return utils.create_unauthorized_response()


def __invoke_disable_users(update_details, headers, auth, host, stage_name, invoke_url):
    try:
        url = "".join(["https://", host, "/", stage_name, invoke_url, "/"])
        response = requests.put(
            url, data=json.dumps(update_details), auth=auth, headers=headers
        )

        logger.info(response.status_code)
        if int(response.status_code) != int(utils.StatusCodes.SUCCESS.value):
            raise Exception("Error occured while disabling users for the tenant")

    except Exception as e:
        logger.error("Error occured while disabling users for the tenant")
        raise Exception("Error occured while disabling users for the tenant", e)
    else:
        return "Success invoking disable users"


def __invoke_enable_users(update_details, headers, auth, host, stage_name, invoke_url):
    try:
        url = "".join(["https://", host, "/", stage_name, invoke_url, "/"])
        response = requests.put(
            url, data=json.dumps(update_details), auth=auth, headers=headers
        )

        logger.info(response.status_code)
        if int(response.status_code) != int(utils.StatusCodes.SUCCESS.value):
            raise Exception("Error occured while enabling users for the tenant")

    except Exception as e:
        logger.error("Error occured while enabling users for the tenant")
        raise Exception("Error occured while enabling users for the tenant", e)
    else:
        return "Success invoking enable users"


class TenantInfo:
    def __init__(self, tenant_name, tenant_address, tenant_email, tenant_phone):
        self.tenant_name = tenant_name
        self.tenant_address = tenant_address
        self.tenant_email = tenant_email
        self.tenant_phone = tenant_phone
