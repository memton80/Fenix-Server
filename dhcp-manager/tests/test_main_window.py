"""Tests pour la fenêtre principale du DHCP Manager (service mocké)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from main_window import DhcpManagerWindow

from core.theme import ThemeManager


def _theme() -> ThemeManager:
    return ThemeManager()


def _service() -> MagicMock:
    service = MagicMock()
    service.list_leases.return_value = []
    service.list_subnets.return_value = []
    service.list_reservations.return_value = []
    return service


def test_fenetre_a_trois_onglets():
    with patch("main_window.KeaService", return_value=_service()):
        window = DhcpManagerWindow(_theme())
    assert window._tabs.count() == 3
    assert window._tabs.tabText(0) == "Baux actifs"
    assert window._tabs.tabText(1) == "Plages"
    assert window._tabs.tabText(2) == "Réservations"


def test_fenetre_a_un_titre():
    with patch("main_window.KeaService", return_value=_service()):
        window = DhcpManagerWindow(_theme())
    assert "DHCP" in window.windowTitle()
