# Index definition for the normalised Company shape (see models.py).
# Norwegian text fields use the built-in `norwegian` analyzer (stemming +
# stopwords) so inflected forms match; `name` stays on the standard analyzer to
# avoid distorting proper nouns, with `name^3` carrying precise matching.
COMPANIES_MAPPING = {
    "mappings": {
        "properties": {
            "org_number": {"type": "keyword"},
            "name": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "country": {"type": "keyword"},
            "org_form": {"type": "keyword"},
            "industry_code": {"type": "keyword"},
            "industry_text": {
                "type": "text",
                "analyzer": "norwegian",
                "fields": {"raw": {"type": "keyword", "ignore_above": 256}},
            },
            # All NACE codes (primary + secondary + tertiary), queried by the
            # industry filter so secondary lines of business are not missed.
            "industry_codes": {"type": "keyword"},
            # All NACE labels joined, for free-text matching across every code.
            "industry_text_all": {"type": "text", "analyzer": "norwegian"},
            "employees": {"type": "integer"},
            "municipality": {"type": "keyword"},
            "registered_at": {"type": "date"},
            "founded_at": {"type": "date"},
            "last_accounts_year": {"type": "integer"},
            "bankrupt": {"type": "boolean"},
            "under_liquidation": {"type": "boolean"},
            "under_forced_liquidation": {"type": "boolean"},
            "vat_registered": {"type": "boolean"},
            "in_group": {"type": "boolean"},
            "description": {"type": "text", "analyzer": "norwegian"},
            "purpose": {"type": "text", "analyzer": "norwegian"},
        }
    }
}
