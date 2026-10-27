"""Filtering / de-dup logic of scripts/fire_stations/import_fire_stations.py."""

import json

from scripts.fire_stations.import_fire_stations import clean_rows


def _row(**overrides):
    row = {
        "title": "Navrangpura Fire Station",
        "category": "Fire station",
        "address": "Navrangpura, Ahmedabad, Gujarat 380009",
        "phone": "079 2658 3333",
        "latitude": "23.036",
        "longtitude": "72.561",
        "place_id": "ChIJ-a",
        "link": "https://www.google.com/maps/place/x",
        "status": "",
        "complete_address": json.dumps({"city": "Ahmedabad", "state": "Gujarat", "postal_code": "380009"}),
    }
    row.update(overrides)
    return row


def test_keeps_gujarat_fire_station():
    [s] = clean_rows([_row()])
    assert s["city"] == "Ahmedabad"
    assert s["longitude"] == 72.561
    assert s["source"] == "google_maps"


def test_drops_extinguisher_shop():
    assert clean_rows([_row(title="Shree Fire Safety", category="Fire protection equipment supplier")]) == []


def test_drops_other_state():
    other = _row(
        address="Udaipur, Rajasthan",
        latitude="24.58",
        longtitude="73.71",
        complete_address=json.dumps({"state": "Rajasthan"}),
    )
    assert clean_rows([other]) == []


def test_drops_permanently_closed():
    assert clean_rows([_row(status="Permanently closed")]) == []


def test_keeps_station_that_is_only_closed_right_now():
    assert len(clean_rows([_row(status="Closed")])) == 1


def test_keeps_named_station_filed_as_government_office():
    assert len(clean_rows([_row(title="Sargasan Fire Station", category="Government office")])) == 1


def test_drops_landmark_named_after_station():
    rows = [
        _row(title="Fire station circle", category="Transportation service"),
        _row(title="Odhav Fire Station", category="Bus station"),
        _row(title="NR. FIRE STATION", category="Building"),
    ]
    assert clean_rows(rows) == []


def test_drops_mis_tagged_non_station():
    assert clean_rows([_row(title="Mukti Dham Gagodar", category="Fire station")]) == []


def test_keeps_gujarati_name():
    assert len(clean_rows([_row(title="ફાયર સ્ટેશન સુરેન્દ્રનગર", category="Fire station")])) == 1


def test_merges_generic_listing_near_named_station():
    rows = [_row(place_id="a", title="Fire station", phone=""), _row(place_id="b", latitude="23.0365")]
    [s] = clean_rows(rows)
    assert s["place_id"] == "b"


def test_keeps_two_differently_named_stations_close_together():
    rows = [
        _row(place_id="a", title="Vadodara Central Fire Headquarter Station"),
        _row(place_id="b", title="Waghodia Road Panigate Fire Station", latitude="23.0365"),
    ]
    assert len(clean_rows(rows)) == 2


def test_dedups_same_place_from_two_queries():
    rows = [_row(phone=""), _row()]
    [s] = clean_rows(rows)
    assert s["phone"] == "079 2658 3333"
