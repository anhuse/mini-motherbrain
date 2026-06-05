# Index definition for the normalised Company shape (see ingestion/models.py).
COMPANIES_MAPPING = {
    "mappings": {
        "properties": {
            "org_number": {"type": "keyword"},
            "name": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "country": {"type": "keyword"},
            "org_form": {"type": "keyword"},
            "industry_code": {"type": "keyword"},
            "industry_text": {"type": "text"},
            "employees": {"type": "integer"},
            "municipality": {"type": "keyword"},
            "registered_at": {"type": "date"},
            "description": {"type": "text"},
        }
    }
}
