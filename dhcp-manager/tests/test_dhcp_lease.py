"""Tests pour le modèle DhcpLease (mapping depuis l'API Kea)."""

from __future__ import annotations

from models.dhcp_lease import DhcpLease


def test_from_kea_mappe_les_champs():
    lease = DhcpLease.from_kea(
        {
            "ip-address": "192.168.1.10",
            "hw-address": "aa:bb:cc:dd:ee:ff",
            "hostname": "pc1",
            "state": 0,
        }
    )
    assert lease == DhcpLease("192.168.1.10", "aa:bb:cc:dd:ee:ff", "pc1", "active")


def test_from_kea_traduit_les_etats():
    assert DhcpLease.from_kea({"state": 1}).state == "declined"
    assert DhcpLease.from_kea({"state": 2}).state == "expired"


def test_from_kea_etat_inconnu_garde_le_code():
    assert DhcpLease.from_kea({"state": 9}).state == "9"


def test_from_kea_champs_absents_par_defaut():
    lease = DhcpLease.from_kea({})
    assert lease.ip_address == ""
    assert lease.hostname == ""
    assert lease.state == "active"
