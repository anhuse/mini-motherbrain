"""Acceptance checks for the search-recall changes (Norwegian analyzer,
secondary NACE codes, purpose clause, fuzziness).

Run it twice to see the effect:

    # baseline, before the migration (alias still on the old index)
    .venv\\Scripts\\python.exe scripts\\validate_search.py

    # ...then re-ingest into v3 and swap the alias, and run it again
    .venv\\Scripts\\python.exe scripts\\validate_search.py

Each probe targets one mechanism we changed and prints the total match count
plus a few top hits, so the before/after deltas are visible at a glance.
"""

from mini_motherbrain.es.client import get_client
from mini_motherbrain.es.indices import physical_index
from mini_motherbrain.config import settings
from mini_motherbrain.search.models import SearchRequest
from mini_motherbrain.search.service import search


def _resolve_index(client) -> None:
    """Show which physical index the alias points at and whether the
    Norwegian analyzer is in place, so it is unambiguous which version we hit."""
    alias = settings.companies_index
    targets = list(client.indices.get_alias(name=alias))
    mapping = client.indices.get_mapping(index=alias)
    # The mapping comes back keyed by the physical index name.
    props = next(iter(mapping.values()))["mappings"]["properties"]
    analyzer = props.get("description", {}).get("analyzer", "standard (default)")
    has_purpose = "purpose" in props
    print(f"alias '{alias}' -> {targets}")
    print(f"  current versioned name would be: {physical_index()}")
    print(f"  description analyzer: {analyzer}")
    print(f"  purpose field present: {has_purpose}")
    print()


def _probe(label: str, mechanism: str, expectation: str, request: SearchRequest) -> None:
    result = search(request)
    print(f"[{label}] {mechanism}")
    print(f"  expect: {expectation}")
    print(f"  total hits: {result.total}")
    for company in result.companies[:5]:
        codes = ", ".join(company.industry_codes) or company.industry_code or "-"
        print(f"    - {company.name}  ({codes})")
    print()


def _secondary_code_delta(client, code: str) -> None:
    """Quantify the secondary-code win directly: how many companies carry `code`
    at all versus only as their primary NACE."""
    alias = settings.companies_index
    primary = client.count(index=alias, query={"term": {"industry_code": code}})["count"]
    any_code = client.count(index=alias, query={"term": {"industry_codes": code}})["count"]
    print(f"[secondary-codes] NACE {code}")
    print(f"  expect: 'any' >= 'primary'; the gap is companies surfaced only via secondary codes")
    print(f"  primary only:   {primary}")
    print(f"  any (primary+secondary): {any_code}")
    print(f"  extra surfaced: {any_code - primary}")
    print()


def main() -> None:
    client = get_client()
    _resolve_index(client)

    # Stemming: inflected/plural forms should collapse to the same stem.
    _probe(
        "stemming",
        "Norwegian analyser stems inflected forms",
        "matches both 'tjenester' and 'tjeneste' forms",
        SearchRequest(text="tjenester", size=5),
    )

    # Compounding: the known Tier-A limit. Built-in stemming does NOT split
    # compounds, so this is expected to stay weak until a decompounder (Tier B).
    _probe(
        "compounding",
        "compound splitting (Tier-A limit)",
        "likely still misses 'fiskeoppdrett'; confirms whether Tier B is needed",
        SearchRequest(text="oppdrett", size=5),
    )

    # Purpose clause: a term that tends to live in the articles-of-association
    # purpose, not the name or NACE label.
    _probe(
        "purpose",
        "free text reaches the purpose clause",
        "matches companies whose only mention of the term is in vedtektsfestetFormaal",
        SearchRequest(text="eiendom", size=5),
    )

    # Fuzziness: a one-character typo should still find the company.
    _probe(
        "fuzziness",
        "typo tolerance (fuzziness AUTO)",
        "'konslent' (typo) still returns 'konsulent' companies",
        SearchRequest(text="konslent", size=5),
    )

    # Secondary codes: råolje (06.100) is commonly a secondary code behind
    # naturgass (06.200) and similar — a good candidate to show the gap.
    _secondary_code_delta(client, "06.100")


if __name__ == "__main__":
    main()
