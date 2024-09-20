class Document:
    def __init__(self, shard_id, document_id, pages, image_key):
        self.shard_id = shard_id
        self.document_id = document_id
        self.pages = pages  # List of pages, each containing its own data
        self.image_key = image_key  # Reference to the original image in S3
        self.key = f"{shard_id}:{document_id}"  # Unique key combining shard ID and document ID

    @classmethod
    def from_db(cls, db_data):
        shard_id = db_data.get('shardId')
        document_id = db_data.get('documentId')
        pages = db_data.get('documentData', {}).get('pages', [])
        image_key = db_data.get('documentData', {}).get('image_key')
        return cls(shard_id, document_id, pages, image_key)
