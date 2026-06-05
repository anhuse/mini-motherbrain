from elasticsearch import Elasticsearch

from mini_motherbrain.config import settings


def get_client() -> Elasticsearch:
    return Elasticsearch(settings.es_url, basic_auth=(settings.es_user, settings.es_password))
