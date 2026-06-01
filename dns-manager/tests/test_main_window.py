"""Tests pour la fenêtre principale du DNS Manager (service et login mockés).

DnsService et LoginDialog sont patchés pour éviter tout appel samba-tool réel
et tout dialogue bloquant lors de la construction de la fenêtre.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import main_window as mw
from main_window import DnsManagerWindow, LoginDialog
from PySide6.QtWidgets import QDialog

from core.theme import ThemeManager


def _theme() -> ThemeManager:
    return ThemeManager()


def _service() -> MagicMock:
    service = MagicMock()
    service.list_zones.return_value = []
    service.list_records.return_value = []
    return service


def test_fenetre_a_deux_onglets():
    with patch.object(mw, "DnsService", return_value=_service()), patch.object(
        mw, "LoginDialog"
    ) as login_cls:
        login_cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
        login_cls.return_value.credentials.return_value = ("Administrator", "pw")
        window = DnsManagerWindow(_theme())
    assert window._tabs.count() == 2
    assert window._tabs.tabText(0) == "Zones"
    assert window._tabs.tabText(1) == "Enregistrements"


def test_fenetre_a_un_titre():
    with patch.object(mw, "DnsService", return_value=_service()), patch.object(
        mw, "LoginDialog"
    ) as login_cls:
        login_cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
        login_cls.return_value.credentials.return_value = ("Administrator", "pw")
        window = DnsManagerWindow(_theme())
    assert "DNS" in window.windowTitle()


def test_credentials_du_dialogue_passes_au_service():
    with patch.object(mw, "DnsService", return_value=_service()) as svc_cls, patch.object(
        mw, "LoginDialog"
    ) as login_cls:
        login_cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
        login_cls.return_value.credentials.return_value = ("admin", "s3cret")
        DnsManagerWindow(_theme())
    svc_cls.assert_called_once_with(username="admin", password="s3cret")


def test_login_annule_construit_service_sans_credentials():
    with patch.object(mw, "DnsService", return_value=_service()) as svc_cls, patch.object(
        mw, "LoginDialog"
    ) as login_cls:
        login_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
        window = DnsManagerWindow(_theme())
    svc_cls.assert_called_once_with()
    assert window._tabs.count() == 2


# --- LoginDialog -----------------------------------------------------------


def test_login_dialog_utilisateur_par_defaut():
    dialog = LoginDialog(_theme())
    assert dialog._edit_user.text() == "Administrator"


def test_login_dialog_credentials():
    dialog = LoginDialog(_theme())
    dialog._edit_user.setText("admin")
    dialog._edit_password.setText("secret")
    assert dialog.credentials() == ("admin", "secret")
