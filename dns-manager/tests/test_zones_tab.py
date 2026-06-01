"""Tests pour l'onglet Zones (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.dns_zone import DnsZone
from widgets.zones_tab import ZonesTab

from core.theme import ThemeManager


def _service() -> MagicMock:
    service = MagicMock()
    service.list_zones.return_value = [
        DnsZone("example.lan", reverse=False),
        DnsZone("1.168.192.in-addr.arpa", reverse=True),
    ]
    return service


def test_refresh_liste_les_zones():
    tab = ZonesTab(_service(), ThemeManager())
    assert tab._table.rowCount() == 2
    assert tab._table.item(0, 0).text() == "example.lan"
    assert tab._table.item(0, 1).text() == "Directe"
    assert tab._table.item(1, 1).text() == "Inverse"


def test_refresh_erreur_affiche_message(monkeypatch):
    service = MagicMock()
    service.list_zones.side_effect = RuntimeError("boom")
    shown: list[str] = []
    monkeypatch.setattr(
        "widgets.zones_tab.QMessageBox.critical",
        lambda *args, **kwargs: shown.append(args[-1]),
    )
    ZonesTab(service, ThemeManager())
    assert shown
