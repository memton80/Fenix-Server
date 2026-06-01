"""Tests pour la fenêtre principale du DNS Manager (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from main_window import DnsManagerWindow

from core.theme import ThemeManager


def _theme() -> ThemeManager:
    return ThemeManager()


def _service() -> MagicMock:
    service = MagicMock()
    service.list_zones.return_value = []
    service.list_records.return_value = []
    return service


def test_fenetre_a_deux_onglets():
    with patch("main_window.DnsService", return_value=_service()):
        window = DnsManagerWindow(_theme())
    assert window._tabs.count() == 2
    assert window._tabs.tabText(0) == "Zones"
    assert window._tabs.tabText(1) == "Enregistrements"


def test_fenetre_a_un_titre():
    with patch("main_window.DnsService", return_value=_service()):
        window = DnsManagerWindow(_theme())
    assert "DNS" in window.windowTitle()
