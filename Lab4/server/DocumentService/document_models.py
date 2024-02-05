# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


class Document:
    key = ""

    def __init__(
        self,
        shardId,
        documentId,
        invoice_number,
        invoice_date,
        total_amount,
        vat_amount,
        image_key,
        title,
    ):
        self.shardId = shardId
        self.documentId = documentId
        self.key = shardId + ":" + documentId
        self.invoice_number = invoice_number
        self.invoice_date = invoice_date
        self.total_amount = total_amount
        self.vat_amount = vat_amount
        self.image_key = image_key
        self.title = title
