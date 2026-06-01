"""Tests pour le modèle DnsRecord (parser de `samba-tool dns query`)."""

from __future__ import annotations

from models.dns_record import DnsRecord

_QUERY = """  Name=, Records=2, Children=0
    A: 192.168.1.10 (flags=600000f0, serial=110, ttl=900)
    NS: dc1.example.lan. (flags=600000f0, serial=110, ttl=3600)
  Name=web, Records=1, Children=0
    A: 192.168.1.20 (flags=f0, serial=110, ttl=900)
  Name=alias, Records=1, Children=0
    CNAME: web.example.lan (flags=f0, serial=110, ttl=900)
"""


def test_parse_query_mappe_les_enregistrements_geres():
    records = DnsRecord.parse_query(_QUERY, "example.lan")
    assert records == [
        DnsRecord("@", "A", "192.168.1.10", "example.lan"),
        DnsRecord("web", "A", "192.168.1.20", "example.lan"),
        DnsRecord("alias", "CNAME", "web.example.lan", "example.lan"),
    ]


def test_parse_query_ignore_les_types_non_geres():
    # Le NS de la racine ne fait pas partie de RECORD_TYPES : il est filtré.
    records = DnsRecord.parse_query(_QUERY, "example.lan")
    assert all(record.record_type != "NS" for record in records)


def test_parse_query_nom_racine_devient_arobase():
    records = DnsRecord.parse_query(_QUERY, "example.lan")
    assert records[0].name == "@"


def test_parse_query_vide_retourne_liste_vide():
    assert DnsRecord.parse_query("", "example.lan") == []
