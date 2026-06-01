"""Tests pour widgets.dashboard — RoleService mocké (Qt offscreen)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.role_status import RoleStatus
from widgets.dashboard import DashboardWidget

from core.roles import Role
from core.theme import ThemeManager


def _role(role_id: str) -> Role:
    return Role(
        id=role_id,
        name=role_id.upper(),
        description=f"Rôle {role_id}",
        service_name=f"{role_id}.service",
        service_type="systemd",
        app=f"{role_id}-manager",
    )


def _statuses() -> list[RoleStatus]:
    return [
        RoleStatus(role=_role("ad"), active=False),
        RoleStatus(role=_role("updates"), active=True),
    ]


@pytest.fixture
def service() -> MagicMock:
    svc = MagicMock()
    svc.list_roles.return_value = _statuses()
    return svc


@pytest.fixture
def dashboard(service: MagicMock) -> DashboardWidget:
    return DashboardWidget(service, ThemeManager())


# --- construction / refresh auto ------------------------------------------


def test_refresh_auto_au_lancement_peuple_la_table(service: MagicMock):
    dashboard = DashboardWidget(service, ThemeManager())
    service.list_roles.assert_called_once_with()
    assert dashboard._table.rowCount() == 2
    assert dashboard._table.item(0, 0).text() == "AD"
    assert dashboard._table.item(0, 1).text() == "Inactif"
    assert dashboard._table.item(0, 2).text() == "Rôle ad"
    assert dashboard._table.item(1, 1).text() == "Actif"


def test_theme_applique_sur_les_boutons(dashboard: DashboardWidget):
    expected = ThemeManager().button_style()
    assert dashboard._btn_refresh.styleSheet() == expected
    assert dashboard._btn_activate.styleSheet() == expected
    assert dashboard._btn_deactivate.styleSheet() == expected


def test_refresh_clicked_recharge(dashboard: DashboardWidget, service: MagicMock):
    service.list_roles.reset_mock()
    dashboard._btn_refresh.click()
    service.list_roles.assert_called_once_with()


def test_refresh_erreur_affiche_messagebox(service: MagicMock):
    service.list_roles.side_effect = RuntimeError("bus indisponible")
    with patch("widgets.dashboard.QMessageBox.critical") as critical:
        DashboardWidget(service, ThemeManager())
    critical.assert_called_once()
    assert "bus indisponible" in critical.call_args.args[2]


# --- activer ---------------------------------------------------------------


def test_activer_sans_selection_affiche_warning(dashboard: DashboardWidget, service: MagicMock):
    dashboard._table.setCurrentCell(-1, -1)
    with patch("widgets.dashboard.QMessageBox.warning") as warning:
        dashboard._btn_activate.click()
    warning.assert_called_once()
    service.enable_role.assert_not_called()


def test_activer_role_deja_actif_affiche_info(dashboard: DashboardWidget, service: MagicMock):
    dashboard._table.selectRow(1)  # "updates" actif
    with patch("widgets.dashboard.QMessageBox.information") as info:
        dashboard._btn_activate.click()
    info.assert_called_once()
    service.enable_role.assert_not_called()


def test_activer_role_inactif_appelle_enable_et_rafraichit(
    dashboard: DashboardWidget, service: MagicMock
):
    dashboard._table.selectRow(0)  # "ad" inactif
    service.list_roles.reset_mock()
    dashboard._btn_activate.click()
    service.enable_role.assert_called_once_with("ad")
    service.list_roles.assert_called_once_with()  # refresh après action


def test_activer_erreur_polkit_affiche_messagebox(
    dashboard: DashboardWidget, service: MagicMock
):
    service.enable_role.side_effect = PermissionError("refusé par Polkit")
    dashboard._table.selectRow(0)
    with patch("widgets.dashboard.QMessageBox.critical") as critical:
        dashboard._btn_activate.click()
    critical.assert_called_once()
    assert "Polkit" in critical.call_args.args[2]


# --- désactiver ------------------------------------------------------------


def test_desactiver_role_actif_appelle_disable_et_rafraichit(
    dashboard: DashboardWidget, service: MagicMock
):
    dashboard._table.selectRow(1)  # "updates" actif
    service.list_roles.reset_mock()
    dashboard._btn_deactivate.click()
    service.disable_role.assert_called_once_with("updates")
    service.list_roles.assert_called_once_with()


def test_desactiver_role_deja_inactif_affiche_info(
    dashboard: DashboardWidget, service: MagicMock
):
    dashboard._table.selectRow(0)  # "ad" inactif
    with patch("widgets.dashboard.QMessageBox.information") as info:
        dashboard._btn_deactivate.click()
    info.assert_called_once()
    service.disable_role.assert_not_called()
