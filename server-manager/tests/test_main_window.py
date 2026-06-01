"""Tests pour main_window — assemblage du dashboard (Qt offscreen).

``RoleService.list_roles`` est patché pour éviter tout appel D-Bus réel lors du
rafraîchissement automatique du dashboard à la construction.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from main_window import ROLES_DIR, WINDOW_TITLE, ServerManagerWindow
from services.role_service import RoleService
from widgets.dashboard import DashboardWidget

from core.theme import ThemeManager


@pytest.fixture
def window() -> ServerManagerWindow:
    with patch.object(RoleService, "list_roles", return_value=[]):
        yield ServerManagerWindow(ThemeManager())


def test_titre_de_la_fenetre(window: ServerManagerWindow):
    assert window.windowTitle() == WINDOW_TITLE
    assert window.windowTitle() == "Fenix Server — Gestionnaire de serveur"


def test_dashboard_au_centre(window: ServerManagerWindow):
    assert isinstance(window.dashboard, DashboardWidget)
    assert window.centralWidget() is window.dashboard


def test_dashboard_partage_le_service_de_la_fenetre(window: ServerManagerWindow):
    assert window.dashboard._service is window.role_service
    assert isinstance(window.role_service, RoleService)


def test_roles_dir_pointe_vers_la_racine_du_depot():
    # ../roles relativement à server-manager/, et le dossier existe dans le dépôt.
    assert ROLES_DIR.name == "roles"
    assert ROLES_DIR.is_dir()


def test_icone_appliquee(window: ServerManagerWindow):
    assert window.windowIcon() is not None


def test_style_global_applique(window: ServerManagerWindow):
    assert window.styleSheet() == ThemeManager().global_style()
