"""Tests pour le modèle DnsZone (parser de `samba-tool dns zonelist`)."""

from __future__ import annotations

from models.dns_zone import DnsZone

_ZONELIST = """
  2 zone(s)

  pszZoneName                 : example.lan
  Flags                       : DNS_RPC_ZONE_DSINTEGRATED
  ZoneType                    : DNS_ZONE_TYPE_PRIMARY

  pszZoneName                 : 1.168.192.in-addr.arpa
  Flags                       : DNS_RPC_ZONE_DSINTEGRATED
  ZoneType                    : DNS_ZONE_TYPE_PRIMARY
"""


def test_parse_zonelist_extrait_les_noms():
    zones = DnsZone.parse_zonelist(_ZONELIST)
    assert [zone.name for zone in zones] == ["example.lan", "1.168.192.in-addr.arpa"]


def test_parse_zonelist_detecte_les_zones_inverses():
    zones = DnsZone.parse_zonelist(_ZONELIST)
    assert zones[0].reverse is False
    assert zones[1].reverse is True


def test_parse_zonelist_vide_retourne_liste_vide():
    assert DnsZone.parse_zonelist("  0 zone(s)\n") == []


def test_from_name_detecte_ipv6_reverse():
    zone = DnsZone.from_name("0.0.0.0.ip6.arpa")
    assert zone.reverse is True
