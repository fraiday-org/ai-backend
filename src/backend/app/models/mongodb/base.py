from mongoengine import Document, fields
from .utils import datetime_utc_now


class BaseDocument(Document):
    created_at = fields.DateTimeField(default=datetime_utc_now)
    updated_at = fields.DateTimeField(default=datetime_utc_now)

    meta = {"abstract": True, "strict": False}

    def to_serializable_dict(self):
        """Custom method for serialization with _id as string."""
        data = self.to_mongo().to_dict()
        if "_id" in data:
            data["id"] = str(data["_id"])
        return data
