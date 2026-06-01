"""Tests pour widgets.domain_tab — ADService mocké (Qt offscreen)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from widgets.domain_tab import DomainTab

from core.theme import ThemeManager

_INFO = {"name": "example.lan", "dc": "ldap://example.lan", "samba": "connecté"}


@pytest.fixture
def service() -> MagicMock:
    svc = MagicMock()
    svc.domain_info.return_value = dict(_INFO)
    return svc


@pytest.fixture
def tab(service: MagicMock) -> DomainTab:
    return DomainTab(service, ThemeManager())


def test_refresh_auto_affiche_les_infos(service: MagicMock):
    tab = DomainTab(service, ThemeManager())
    service.domain_info.assert_called_once_with()
    assert tab._value_domain.text() == "example.lan"
    assert tab._value_dc.text() == "ldap://example.lan"
    assert tab._value_samba.text() == "connecté"


def test_theme_applique_sur_le_bouton(tab: DomainTab):
    assert tab._btn_refresh.styleSheet() == ThemeManager().button_style()


def test_rafraichir_recharge_les_infos(tab: DomainTab, service: MagicMock):
    service.domain_info.reset_mock()
    service.domain_info.return_value = {
        "name": "corp.lan",
        "dc": "ldap://corp.lan",
        "samba": "déconnecté",
    }
    tab._btn_refresh.click()
    service.domain_info.assert_called_once_with()
    assert tab._value_domain.text() == "corp.lan"
    assert tab._value_samba.text() == "déconnecté"


def test_infos_manquantes_affichent_placeholder(service: MagicMock):
    service.domain_info.return_value = {}
    tab = DomainTab(service, ThemeManager())
    assert tab._value_domain.text() == "—"
    assert tab._value_dc.text() == "—"
    assert tab._value_samba.text() == "—"


def test_erreur_affiche_messagebox(service: MagicMock):
    service.domain_info.side_effect = RuntimeError("LDAP indisponible")
    with patch("widgets.domain_tab.QMessageBox.critical") as critical:
        DomainTab(service, ThemeManager())
    critical.assert_called_once()
    assert "LDAP indisponible" in critical.call_args.args[2]
