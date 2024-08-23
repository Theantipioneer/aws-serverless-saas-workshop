from PyPDF2 import PdfReader
from PIL import Image
from io import BytesIO
import time
import hashlib


def count_pages(doc_content, doc_type):
    if doc_type == "pdf":
        reader = PdfReader(BytesIO(doc_content))
        return len(reader.pages)
    elif doc_type in ["jpeg", "jpg", "png"]:
        image = Image.open(BytesIO(doc_content))
        return 1  # Each image is considered as one page
    else:
        raise ValueError("Unsupported document type")

def generate_unique_key(file_content, file_name):
    file_extension = file_name.split(".").pop()
    file_name_base = file_name.split(".")[0]

    hash_object = hashlib.sha1(file_content)
    hash_hex = hash_object.hexdigest()

    timestamp = str(int(time.time()))
    unique_file_name = f"{timestamp}-{hash_hex[:10]}-{file_name_base}.{file_extension}"
    
    return unique_file_name