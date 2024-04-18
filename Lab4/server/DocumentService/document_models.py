# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


class Entity:
    def __init__(self, invoice_number="", invoice_date="", total_amount=0, vat_amount=0):
        self.invoice_number = invoice_number
        self.invoice_date = invoice_date
        self.total_amount = total_amount
        self.vat_amount = vat_amount

class Document:
    key = ""

    def __init__(self, shard_id, document_id, title, image_key, entity):
        self.shard_id = shard_id
        self.document_id = document_id
        self.title = title
        self.image_key = image_key
        self.entity = entity
        self.key = f"{shard_id}:{document_id}"

    @classmethod
    def from_db(cls, db_data):
        shard_id = db_data.get('shardId')
        document_id = db_data.get('documentId')
        title = db_data.get('documentData', {}).get('title')
        image_key = db_data.get('documentData', {}).get('image_key')
        entity_data = db_data.get('documentData', {}).get('entity', {})
        entity = Entity(
            invoice_number=entity_data.get('invoice_number'),
            invoice_date=entity_data.get('invoice_date'),
            total_amount=entity_data.get('total_amount'),
            vat_amount=entity_data.get('vat_amount')
        )
        return cls(shard_id, document_id, title, image_key, entity)

