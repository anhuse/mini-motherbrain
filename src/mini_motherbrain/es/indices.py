from elasticsearch import Elasticsearch

from mini_motherbrain.config import settings
from mini_motherbrain.es.mappings import COMPANIES_MAPPING

# Bump when COMPANIES_MAPPING changes, then run `migrate` to reindex and
# move the alias. Searches always go through the alias (settings.companies_index);
# writes target the physical index.
INDEX_VERSION = 3


def physical_index() -> str:
    return f"{settings.companies_index}-v{INDEX_VERSION}"


def ensure_index(client: Elasticsearch) -> str:
    """Create the current versioned index if missing and return its name.
    The public alias is attached only if nothing else holds it yet."""
    name = physical_index()
    if not client.indices.exists(index=name):
        client.indices.create(index=name, **COMPANIES_MAPPING)
    if not client.indices.exists_alias(name=settings.companies_index):
        client.indices.put_alias(index=name, name=settings.companies_index)
    return name


def migrate(client: Elasticsearch) -> str:
    """After bumping INDEX_VERSION: copy documents from the previous version
    and swap the alias atomically. No-op if the alias is already current."""
    target = ensure_index(client)
    previous = [i for i in client.indices.get_alias(name=settings.companies_index) if i != target]
    for old in previous:
        client.reindex(source={"index": old}, dest={"index": target}, wait_for_completion=True)
        client.indices.update_aliases(
            actions=[
                {"remove": {"index": old, "alias": settings.companies_index}},
                {"add": {"index": target, "alias": settings.companies_index}},
            ]
        )
    return target
