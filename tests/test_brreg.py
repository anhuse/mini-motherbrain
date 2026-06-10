from datetime import date

from mini_motherbrain.ingestion.adapters.brreg import BrregAdapter


def test_normalise_maps_core_fields():
    raw = {
        "organisasjonsnummer": "923609016",
        "navn": "EQUINOR ASA",
        "organisasjonsform": {"kode": "ASA"},
        "naeringskode1": {"kode": "06.100", "beskrivelse": "Utvinning av råolje"},
        "antallAnsatte": 20000,
        "forretningsadresse": {"kommune": "STAVANGER"},
        "registreringsdatoEnhetsregisteret": "1995-09-18",
        "stiftelsesdato": "1972-07-14",
        "sisteInnsendteAarsregnskap": 2024,
        "konkurs": False,
        "underAvvikling": False,
        "registrertIMvaregisteret": True,
        "erIKonsern": True,
        "aktivitet": ["Petroleumsvirksomhet"],
    }

    company = BrregAdapter._normalise(raw)

    assert company.org_number == "923609016"
    assert company.country == "NO"
    assert company.org_form == "ASA"
    assert company.industry_text == "Utvinning av råolje"
    assert company.employees == 20000
    assert company.municipality == "STAVANGER"
    assert company.registered_at == date(1995, 9, 18)
    assert company.founded_at == date(1972, 7, 14)
    assert company.last_accounts_year == 2024
    assert company.bankrupt is False
    assert company.vat_registered is True
    assert company.in_group is True
    assert company.description == "Petroleumsvirksomhet"


def test_normalise_handles_missing_optionals():
    company = BrregAdapter._normalise({"organisasjonsnummer": "1", "navn": "X AS"})

    assert company.industry_code is None
    assert company.employees is None
    assert company.description is None
    assert company.founded_at is None
    assert company.last_accounts_year is None
    assert company.bankrupt is False
    assert company.under_liquidation is False
    assert company.in_group is False
