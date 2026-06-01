"""Tests pour widgets.groups_tab — ADService et GroupDialog mockés (Qt offscreen)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.ad_group import ADGroup
from PySide6.QtWidgets import QDialog, QMessageBox
from widgets.groups_tab import GroupsTab

from core.theme import ThemeManager


def _groups() -> list[ADGroup]:
    return [
        ADGroup("admins", "Administrateurs", "CN=admins,DC=x", ("CN=jdoe,DC=x", "CN=svc,DC=x")),
        ADGroup("ventes", "", "CN=ventes,DC=x"),
    ]


@pytest.fixture
def service() -> MagicMock:
    svc = MagicMock()
    svc.list_groups.return_value = _groups()
    return svc


@pytest.fixture
def tab(service: MagicMock) -> GroupsTab:
    return GroupsTab(service, ThemeManager())


def _accepted_dialog(values: dict[str, str]) -> MagicMock:
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.values.return_value = values
    return dialog


# --- construction / refresh ------------------------------------------------


def test_refresh_auto_peuple_la_table(service: MagicMock):
    tab = GroupsTab(service, ThemeManager())
    service.list_groups.assert_called_once_with()
    assert tab._table.rowCount() == 2
    assert tab._table.item(0, 0).text() == "admins"
    assert tab._table.item(0, 1).text() == "Administrateurs"
    assert tab._table.item(0, 2).text() == "2"  # nombre de membres
    assert tab._table.item(1, 2).text() == "0"


def test_theme_applique_sur_les_boutons(tab: GroupsTab):
    expected = ThemeManager().button_style()
    assert tab._btn_create.styleSheet() == expected
    assert tab._btn_delete.styleSheet() == expected


# --- créer -----------------------------------------------------------------


def test_creer_accepte_appelle_create_group_et_rafraichit(tab: GroupsTab, service: MagicMock):
    service.list_groups.reset_mock()
    values = {"name": "support", "description": "Équipe support"}
    with patch("widgets.groups_tab.GroupDialog", return_value=_accepted_dialog(values)):
        tab._btn_create.click()
    service.create_group.assert_called_once_with("support", description="Équipe support")
    service.list_groups.assert_called_once_with()


def test_creer_annule_ne_cree_pas(tab: GroupsTab, service: MagicMock):
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected
    with patch("widgets.groups_tab.GroupDialog", return_value=dialog):
        tab._btn_create.click()
    service.create_group.assert_not_called()


def test_creer_erreur_affiche_messagebox(tab: GroupsTab, service: MagicMock):
    service.create_group.side_effect = RuntimeError("LDAP indisponible")
    values = {"name": "x", "description": ""}
    with patch("widgets.groups_tab.GroupDialog", return_value=_accepted_dialog(values)), patch(
        "widgets.groups_tab.QMessageBox.critical"
    ) as critical:
        tab._btn_create.click()
    critical.assert_called_once()
    assert "LDAP indisponible" in critical.call_args.args[2]


# --- supprimer -------------------------------------------------------------


def test_supprimer_sans_selection_affiche_warning(tab: GroupsTab, service: MagicMock):
    tab._table.setCurrentCell(-1, -1)
    with patch("widgets.groups_tab.QMessageBox.warning") as warning:
        tab._btn_delete.click()
    warning.assert_called_once()
    service.delete_group.assert_not_called()


def test_supprimer_confirme_appelle_delete_group(tab: GroupsTab, service: MagicMock):
    tab._table.selectRow(0)
    with patch(
        "widgets.groups_tab.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        tab._btn_delete.click()
    service.delete_group.assert_called_once_with("admins")


def test_supprimer_refuse_la_confirmation_ne_supprime_pas(tab: GroupsTab, service: MagicMock):
    tab._table.selectRow(0)
    with patch(
        "widgets.groups_tab.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        tab._btn_delete.click()
    service.delete_group.assert_not_called()
