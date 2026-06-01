"""Tests pour l'onglet Plages (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.dhcp_subnet import DhcpSubnet
from widgets.subnets_tab import SubnetsTab

from core.theme import ThemeManager


def _service() -> MagicMock:
    service = MagicMock()
    service.list_subnets.return_value = [
        DhcpSubnet(1, "192.168.1.0/24", "192.168.1.100-192.168.1.200"),
    ]
    return service


def test_refresh_liste_les_plages():
    tab = SubnetsTab(_service(), ThemeManager())
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 1).text() == "192.168.1.0/24"


def test_next_subnet_id_suit_le_max():
    tab = SubnetsTab(_service(), ThemeManager())
    assert tab._next_subnet_id() == 2


def test_save_delegue_au_service():
    service = _service()
    tab = SubnetsTab(service, ThemeManager())
    tab._save({"subnet_id": 2, "subnet": "10.0.0.0/24", "pool": "10.0.0.10-10.0.0.20"})
    service.set_subnet.assert_called_once_with(
        "10.0.0.0/24", "10.0.0.10-10.0.0.20", subnet_id=2
    )
