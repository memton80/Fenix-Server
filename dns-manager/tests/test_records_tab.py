"""Tests pour l'onglet Enregistrements (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.dns_record import DnsRecord
from models.dns_zone import DnsZone
from widgets.records_tab import RecordsTab

from core.theme import ThemeManager


def _service() -> MagicMock:
    service = MagicMock()
    service.list_zones.return_value = [DnsZone("example.lan")]
    service.list_records.return_value = [
        DnsRecord("web", "A", "192.168.1.20", "example.lan"),
    ]
    return service


def test_reload_zones_remplit_le_selecteur():
    tab = RecordsTab(_service(), ThemeManager())
    assert tab._combo_zone.count() == 1
    assert tab._combo_zone.currentText() == "example.lan"


def test_refresh_liste_les_enregistrements():
    tab = RecordsTab(_service(), ThemeManager())
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 0).text() == "web"
    assert tab._table.item(0, 1).text() == "A"


def test_add_record_delegue_au_service():
    service = _service()
    tab = RecordsTab(service, ThemeManager())
    tab._service.add_record("example.lan", "mail", "A", "192.168.1.30")
    service.add_record.assert_called_once_with("example.lan", "mail", "A", "192.168.1.30")
