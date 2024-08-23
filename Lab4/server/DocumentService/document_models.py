class Document:
    def __init__(self, shard_id, document_id, processed_images, image_key, summary_fields, line_items):
        self.shard_id = shard_id
        self.document_id = document_id
        self.processed_images = processed_images
        self.image_key = image_key  # Reference to the original image in S3
        self.summary_fields = summary_fields  # Summary fields extracted from the document
        self.line_items = line_items  # Line items extracted from the document
        self.key = f"{shard_id}:{document_id}"  # Unique key combining shard ID and document ID

    @classmethod
    def from_db(cls, db_data):
        shard_id = db_data.get('shardId')
        document_id = db_data.get('documentId')
        processed_images = db_data.get('processed_images')
        image_key = db_data.get('documentData', {}).get('image_key')
        summary_fields = db_data.get('documentData', {}).get('summary_fields', {})
        line_items = db_data.get('documentData', {}).get('line_items', [])
        return cls(shard_id, document_id, processed_images, image_key, summary_fields, line_items)
