"""Tests pour main_window — assemblage des trois onglets (Qt offscreen).

LDAPService/ADService sont patchés pour éviter toute connexion réelle lors du
rafraîchissement automatique des onglets à la construction.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import main_window as mw
import pytest
from main_window import WINDOW_TITLE, ADManagerWindow
from widgets.domain_tab import DomainTab
from widgets.groups_tab import GroupsTab
from widgets.users_tab import UsersTab

from core.theme import ThemeManager


@pytest.fixture
def ad_service() -> MagicMock:
    svc = MagicMock()
    svc.list_users.return_value = []
    svc.list_groups.return_value = []
    svc.domain_info.return_value = {}
    return svc


@pytest.fixture
def window(ad_service: MagicMock) -> ADManagerWindow:
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ):
        ldap_cls.from_smb_conf.return_value = MagicMock()
        yield ADManagerWindow(ThemeManager())


def test_titre_de_la_fenetre(window: ADManagerWindow):
    assert window.windowTitle() == WINDOW_TITLE
    assert window.windowTitle() == "Fenix Server — Gestionnaire AD"


def test_trois_onglets(window: ADManagerWindow):
    tabs = window._tabs
    assert tabs.count() == 3
    assert tabs.tabText(0) == "Utilisateurs"
    assert tabs.tabText(1) == "Groupes"
    assert tabs.tabText(2) == "Domaine"


def test_les_onglets_sont_du_bon_type(window: ADManagerWindow):
    assert isinstance(window.users_tab, UsersTab)
    assert isinstance(window.groups_tab, GroupsTab)
    assert isinstance(window.domain_tab, DomainTab)


def test_les_onglets_partagent_le_service(window: ADManagerWindow, ad_service: MagicMock):
    assert window.users_tab._service is ad_service
    assert window.groups_tab._service is ad_service
    assert window.domain_tab._service is ad_service


def test_construit_le_service_depuis_smb_conf(ad_service: MagicMock):
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ):
        ldap = ldap_cls.from_smb_conf.return_value
        ADManagerWindow(ThemeManager())
    ldap_cls.from_smb_conf.assert_called_once_with()
    ldap.connect.assert_called_once_with()


def test_connexion_initiale_en_echec_non_fatale(ad_service: MagicMock):
    # Une RuntimeError au connect ne doit pas empêcher l'ouverture de la fenêtre.
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ):
        ldap_cls.from_smb_conf.return_value.connect.side_effect = RuntimeError("pas de DC")
        window = ADManagerWindow(ThemeManager())
    assert window._tabs.count() == 3


def test_style_global_applique(window: ADManagerWindow):
    assert window.styleSheet() == ThemeManager().global_style()
