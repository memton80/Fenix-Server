"""Tests pour l'onglet Baux actifs (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.dhcp_lease import DhcpLease
from PySide6.QtWidgets import QMessageBox
from widgets.leases_tab import LeasesTab

from core.theme import ThemeManager


def _service() -> MagicMock:
    service = MagicMock()
    service.list_leases.return_value = [
        DhcpLease("192.168.1.10", "aa:bb:cc:dd:ee:ff", "pc1", "active"),
    ]
    return service


def test_refresh_liste_les_baux():
    tab = LeasesTab(_service(), ThemeManager())
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 0).text() == "192.168.1.10"
    assert tab._table.item(0, 1).text() == "aa:bb:cc:dd:ee:ff"


def test_restart_delegue_au_service(monkeypatch):
    service = _service()
    monkeypatch.setattr(
        "widgets.leases_tab.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    tab = LeasesTab(service, ThemeManager())
    tab._on_restart_clicked()
    service.control_service.assert_called_once_with("restart")
