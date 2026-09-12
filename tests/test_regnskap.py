from mini_motherbrain.ingestion.adapters.regnskap import RegnskapAdapter


def _account(currency="NOK", revenue=1000, operating=200, year="2024", regnskapstype="SELSKAP"):
    return {
        "regnskapstype": regnskapstype,
        "regnskapsperiode": {"tilDato": f"{year}-12-31"},
        "valuta": currency,
        "resultatregnskapResultat": {
            "driftsresultat": {
                "driftsinntekter": {"sumDriftsinntekter": revenue},
                "driftsresultat": operating,
            },
            "aarsresultat": 150,
        },
        "eiendeler": {"sumEiendeler": 5000},
        "egenkapitalGjeld": {
            "egenkapital": {"sumEgenkapital": 3000},
            "gjeldOversikt": {"sumGjeld": 2000},
        },
    }


def test_normalise_maps_and_computes_margin():
    fields = RegnskapAdapter._normalise(_account(revenue=1000, operating=200))

    assert fields["revenue"] == 1000
    assert fields["operating_profit"] == 200
    assert fields["operating_margin"] == 0.2
    assert fields["net_result"] == 150
    assert fields["total_assets"] == 5000
    assert fields["equity"] == 3000
    assert fields["total_debt"] == 2000
    assert fields["accounts_year"] == 2024
    assert fields["accounts_currency"] == "NOK"


def test_normalise_converts_foreign_currency_to_nok():
    fields = RegnskapAdapter._normalise(_account(currency="USD", revenue=1000, operating=100))

    # 1000 USD × 10.5 reference rate → 10,500 NOK; original currency retained.
    assert fields["revenue"] == 10_500
    assert fields["operating_profit"] == 1_050
    assert fields["accounts_currency"] == "USD"
    # Margin is a ratio, so conversion leaves it unchanged.
    assert fields["operating_margin"] == 0.1


def test_normalise_handles_missing_figures():
    fields = RegnskapAdapter._normalise({"regnskapsperiode": {"tilDato": "2023-12-31"}})

    assert fields["revenue"] is None
    assert fields["operating_profit"] is None
    assert fields["operating_margin"] is None
    assert fields["accounts_year"] == 2023
    # Absent currency defaults to NOK (rate 1.0).
    assert fields["accounts_currency"] == "NOK"


def test_normalise_no_margin_when_revenue_zero():
    # Holding companies with ~0 revenue must not divide by near-zero.
    fields = RegnskapAdapter._normalise(_account(revenue=0, operating=200))

    assert fields["operating_margin"] is None


def test_select_latest_prefers_company_accounts_and_newest_year():
    accounts = [
        _account(year="2022", regnskapstype="SELSKAP"),
        _account(year="2024", regnskapstype="KONSERN"),
        _account(year="2023", regnskapstype="SELSKAP"),
    ]

    latest = RegnskapAdapter._select_latest(accounts)

    # Newest SELSKAP (2023), not the newer KONSERN (2024) group figures.
    assert latest["regnskapsperiode"]["tilDato"] == "2023-12-31"
    assert latest["regnskapstype"] == "SELSKAP"


def test_select_latest_empty_returns_none():
    assert RegnskapAdapter._select_latest([]) is None
