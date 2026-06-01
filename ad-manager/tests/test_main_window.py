"""Tests pour main_window — assemblage des trois onglets (Qt offscreen).

LDAPService/ADService/LoginDialog sont patchés pour éviter toute connexion
réelle et tout dialogue bloquant lors de la construction de la fenêtre.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import main_window as mw
import pytest
from main_window import WINDOW_TITLE, ADManagerWindow, LoginDialog
from PySide6.QtWidgets import QDialog
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
    ), patch.object(mw, "LoginDialog") as login_cls:
        ldap_cls.from_smb_conf.return_value = MagicMock()
        login = login_cls.return_value
        login.exec.return_value = QDialog.DialogCode.Accepted
        login.credentials.return_value = ("Administrator", "pw")
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


def test_connexion_passe_les_credentials_du_dialogue(ad_service: MagicMock):
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ), patch.object(mw, "LoginDialog") as login_cls:
        ldap = ldap_cls.from_smb_conf.return_value
        login = login_cls.return_value
        login.exec.return_value = QDialog.DialogCode.Accepted
        login.credentials.return_value = ("admin", "s3cret")
        ADManagerWindow(ThemeManager())

    ldap_cls.from_smb_conf.assert_called_once_with()
    ldap.set_credentials.assert_called_once_with(bind_dn="admin", password="s3cret")
    ldap.connect.assert_called_once_with()


def test_reprompt_si_la_connexion_echoue(ad_service: MagicMock):
    # Premier bind en échec : les identifiants sont redemandés, puis ça réussit.
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ), patch.object(mw, "LoginDialog") as login_cls, patch(
        "main_window.QMessageBox.warning"
    ) as warning:
        ldap = ldap_cls.from_smb_conf.return_value
        ldap.connect.side_effect = [RuntimeError("identifiants invalides"), None]
        login = login_cls.return_value
        login.exec.return_value = QDialog.DialogCode.Accepted
        login.credentials.side_effect = [("admin", "faux"), ("admin", "bon")]
        window = ADManagerWindow(ThemeManager())

    assert ldap.connect.call_count == 2
    assert ldap.set_credentials.call_count == 2
    warning.assert_called_once()
    assert window._tabs.count() == 3


def test_login_annule_ouvre_sans_connexion(ad_service: MagicMock):
    with patch.object(mw, "LDAPService") as ldap_cls, patch.object(
        mw, "ADService", return_value=ad_service
    ), patch.object(mw, "LoginDialog") as login_cls:
        ldap = ldap_cls.from_smb_conf.return_value
        login_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
        window = ADManagerWindow(ThemeManager())

    ldap.connect.assert_not_called()
    ldap.set_credentials.assert_not_called()
    assert window._tabs.count() == 3


def test_style_global_applique(window: ADManagerWindow):
    assert window.styleSheet() == ThemeManager().global_style()


# --- Samba non configuré ---------------------------------------------------


@pytest.mark.parametrize("error", [ValueError("pas de realm"), FileNotFoundError("smb.conf")])
def test_samba_non_configure_avertit_et_desactive_les_onglets(error: Exception):
    with patch.object(mw.LDAPService, "from_smb_conf", side_effect=error), patch(
        "main_window.QMessageBox.warning"
    ) as warning:
        window = ADManagerWindow(ThemeManager())

    warning.assert_called_once()
    assert "Samba non configuré" in warning.call_args.args[2]
    assert window._samba_configured is False

    tabs = window._tabs
    # L'onglet Domaine reste accessible ; les autres sont désactivés.
    assert tabs.isTabEnabled(tabs.indexOf(window.domain_tab)) is True
    assert tabs.isTabEnabled(tabs.indexOf(window.users_tab)) is False
    assert tabs.isTabEnabled(tabs.indexOf(window.groups_tab)) is False
    assert tabs.currentWidget() is window.domain_tab


def test_samba_non_configure_domaine_affiche_non_configure():
    with patch.object(mw.LDAPService, "from_smb_conf", side_effect=ValueError), patch(
        "main_window.QMessageBox.warning"
    ):
        window = ADManagerWindow(ThemeManager())
    # L'onglet Domaine s'ouvre sans erreur via le service de repli.
    assert window.domain_tab._value_samba.text() == "non configuré"


# --- LoginDialog -----------------------------------------------------------


def test_login_dialog_utilisateur_par_defaut():
    dialog = LoginDialog(ThemeManager())
    assert dialog._edit_user.text() == "Administrator"


def test_login_dialog_credentials():
    dialog = LoginDialog(ThemeManager())
    dialog._edit_user.setText("admin")
    dialog._edit_password.setText("secret")
    assert dialog.credentials() == ("admin", "secret")
