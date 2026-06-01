"""Tests pour le modèle DhcpSubnet (mapping depuis la config Kea)."""

from __future__ import annotations

from models.dhcp_subnet import DhcpSubnet


def test_from_kea_mappe_id_reseau_et_pool():
    subnet = DhcpSubnet.from_kea(
        {
            "id": 1,
            "subnet": "192.168.1.0/24",
            "pools": [{"pool": "192.168.1.100-192.168.1.200"}],
        }
    )
    assert subnet == DhcpSubnet(1, "192.168.1.0/24", "192.168.1.100-192.168.1.200")


def test_from_kea_sans_pool():
    subnet = DhcpSubnet.from_kea({"id": 2, "subnet": "10.0.0.0/24"})
    assert subnet.pool == ""


def test_from_kea_champs_absents_par_defaut():
    subnet = DhcpSubnet.from_kea({})
    assert subnet.subnet_id == 0
    assert subnet.subnet == ""
