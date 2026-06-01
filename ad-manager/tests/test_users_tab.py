"""Tests pour widgets.users_tab — ADService et UserDialog mockés (Qt offscreen)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.ad_user import ADUser
from PySide6.QtWidgets import QDialog, QMessageBox
from widgets.users_tab import UsersTab

from core.theme import ThemeManager


def _users() -> list[ADUser]:
    return [
        ADUser("jdoe", "John Doe", "jdoe@example.lan", True, "CN=jdoe,DC=x"),
        ADUser("svc", "Service", "", False, "CN=svc,DC=x"),
    ]


@pytest.fixture
def service() -> MagicMock:
    svc = MagicMock()
    svc.list_users.return_value = _users()
    return svc


@pytest.fixture
def tab(service: MagicMock) -> UsersTab:
    return UsersTab(service, ThemeManager())


def _accepted_dialog(values: dict[str, str]) -> MagicMock:
    """Patch de UserDialog renvoyant un dialogue accepté avec les valeurs données."""
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.values.return_value = values
    return dialog


# --- construction / refresh ------------------------------------------------


def test_refresh_auto_peuple_la_table(service: MagicMock):
    tab = UsersTab(service, ThemeManager())
    service.list_users.assert_called_once_with()
    assert tab._table.rowCount() == 2
    assert tab._table.item(0, 0).text() == "John Doe"
    assert tab._table.item(0, 1).text() == "jdoe"
    assert tab._table.item(0, 2).text() == "jdoe@example.lan"
    assert tab._table.item(0, 3).text() == "Activé"
    assert tab._table.item(1, 3).text() == "Désactivé"


def test_theme_applique_sur_les_boutons(tab: UsersTab):
    expected = ThemeManager().button_style()
    assert tab._btn_create.styleSheet() == expected
    assert tab._btn_modify.styleSheet() == expected
    assert tab._btn_delete.styleSheet() == expected


# --- créer -----------------------------------------------------------------


def test_creer_accepte_appelle_create_user_et_rafraichit(tab: UsersTab, service: MagicMock):
    values = {
        "username": "asmith",
        "display_name": "Alice Smith",
        "email": "a@example.lan",
        "password": "pw",
    }
    service.list_users.reset_mock()
    with patch("widgets.users_tab.UserDialog", return_value=_accepted_dialog(values)):
        tab._btn_create.click()

    service.create_user.assert_called_once_with(
        "asmith", "pw", display_name="Alice Smith", email="a@example.lan"
    )
    service.list_users.assert_called_once_with()  # refresh


def test_creer_annule_ne_cree_pas(tab: UsersTab, service: MagicMock):
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected
    with patch("widgets.users_tab.UserDialog", return_value=dialog):
        tab._btn_create.click()
    service.create_user.assert_not_called()


def test_creer_erreur_affiche_messagebox(tab: UsersTab, service: MagicMock):
    service.create_user.side_effect = RuntimeError("Commande samba-tool échouée: user create")
    values = {"username": "x", "display_name": "X", "email": "", "password": "p"}
    with patch("widgets.users_tab.UserDialog", return_value=_accepted_dialog(values)), patch(
        "widgets.users_tab.QMessageBox.critical"
    ) as critical:
        tab._btn_create.click()
    critical.assert_called_once()
    assert "samba-tool" in critical.call_args.args[2]


def test_creer_message_politique_mot_de_passe_affiche_tel_quel(tab: UsersTab, service: MagicMock):
    message = (
        "Le mot de passe ne respecte pas la politique de complexité AD :\n"
        "- 8 caractères minimum\n"
        "- Majuscule, minuscule, chiffre et caractère spécial requis"
    )
    service.create_user.side_effect = RuntimeError(message)
    values = {"username": "x", "display_name": "X", "email": "", "password": "weak"}
    with patch("widgets.users_tab.UserDialog", return_value=_accepted_dialog(values)), patch(
        "widgets.users_tab.QMessageBox.critical"
    ) as critical:
        tab._btn_create.click()
    # Le message multi-lignes est affiché verbatim dans le QMessageBox.
    assert critical.call_args.args[2] == message


# --- modifier --------------------------------------------------------------


def test_modifier_sans_selection_affiche_warning(tab: UsersTab, service: MagicMock):
    tab._table.setCurrentCell(-1, -1)
    with patch("widgets.users_tab.QMessageBox.warning") as warning:
        tab._btn_modify.click()
    warning.assert_called_once()
    service.modify_user.assert_not_called()


def test_modifier_accepte_appelle_modify_user(tab: UsersTab, service: MagicMock):
    tab._table.selectRow(0)
    values = {
        "username": "jdoe",
        "display_name": "John D.",
        "email": "new@example.lan",
        "password": "",
    }
    with patch("widgets.users_tab.UserDialog", return_value=_accepted_dialog(values)):
        tab._btn_modify.click()
    service.modify_user.assert_called_once_with(
        "jdoe", display_name="John D.", email="new@example.lan"
    )


# --- supprimer -------------------------------------------------------------


def test_supprimer_sans_selection_affiche_warning(tab: UsersTab, service: MagicMock):
    tab._table.setCurrentCell(-1, -1)
    with patch("widgets.users_tab.QMessageBox.warning") as warning:
        tab._btn_delete.click()
    warning.assert_called_once()
    service.delete_user.assert_not_called()


def test_supprimer_confirme_appelle_delete_user(tab: UsersTab, service: MagicMock):
    tab._table.selectRow(0)
    with patch(
        "widgets.users_tab.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        tab._btn_delete.click()
    service.delete_user.assert_called_once_with("jdoe")


def test_supprimer_refuse_la_confirmation_ne_supprime_pas(tab: UsersTab, service: MagicMock):
    tab._table.selectRow(0)
    with patch(
        "widgets.users_tab.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        tab._btn_delete.click()
    service.delete_user.assert_not_called()
