"""Tests pour le modèle DhcpReservation (mapping Kea aller/retour)."""

from __future__ import annotations

from models.dhcp_reservation import DhcpReservation


def test_from_kea_mappe_les_champs():
    reservation = DhcpReservation.from_kea(
        {"hw-address": "aa:bb:cc:dd:ee:ff", "ip-address": "192.168.1.50", "hostname": "pc2"},
        subnet_id=1,
    )
    assert reservation == DhcpReservation("aa:bb:cc:dd:ee:ff", "192.168.1.50", "pc2", subnet_id=1)


def test_to_kea_inclut_le_hostname_si_present():
    reservation = DhcpReservation("aa:bb:cc:dd:ee:ff", "192.168.1.50", "pc2", subnet_id=1)
    payload = reservation.to_kea()
    assert payload == {
        "hw-address": "aa:bb:cc:dd:ee:ff",
        "ip-address": "192.168.1.50",
        "hostname": "pc2",
    }


def test_to_kea_omet_le_hostname_vide():
    reservation = DhcpReservation("aa:bb:cc:dd:ee:ff", "192.168.1.50", "", subnet_id=1)
    assert "hostname" not in reservation.to_kea()
