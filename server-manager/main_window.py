"""Fenêtre principale du Server Manager : dashboard d'activation des rôles."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget
from services.role_service import RoleService
from widgets.dashboard import DashboardWidget

from core.roles import RoleRegistry
from core.theme import ThemeManager

WINDOW_TITLE = "Fenix Server — Gestionnaire de serveur"
WINDOW_ICON_NAME = "preferences-system"

# Dossier des définitions de rôles, à la racine du dépôt (../roles).
ROLES_DIR = Path(__file__).resolve().parent.parent / "roles"


class ServerManagerWindow(QMainWindow):
    """Fenêtre principale exposant le dashboard des rôles."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre et le dashboard.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self._registry = RoleRegistry(ROLES_DIR)
        self._registry.load()
        self.role_service = RoleService(self._registry)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit l'interface : charge les rôles et place le dashboard au centre."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.dashboard = DashboardWidget(self.role_service, self._theme, self)
        self.setCentralWidget(self.dashboard)
