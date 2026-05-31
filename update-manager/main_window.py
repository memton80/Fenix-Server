"""Fenêtre principale de l'Update Manager : deux onglets Système / Services."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from core.theme import ThemeManager
from services.github_service import GitHubReleaseService
from services.packagekit_service import PackageKitService
from widgets.services_tab import ServicesUpdateTab
from widgets.system_tab import SystemUpdateTab

WINDOW_TITLE = "Fenix Server — Gestionnaire de mises à jour"
WINDOW_ICON_NAME = "system-software-update"


class UpdateManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à deux onglets.

    Onglets :
        - « Système »  : mises à jour des paquets (PackageKit).
        - « Services » : mises à jour des services Fenix (GitHub Releases).
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre et ses onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self.packagekit_service = PackageKitService(self)
        self.github_service = GitHubReleaseService()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les deux onglets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(self._theme.icon(WINDOW_ICON_NAME))
        self.setStyleSheet(self._theme.global_style())

        self.system_tab = SystemUpdateTab(self.packagekit_service, self._theme, self)
        self.services_tab = ServicesUpdateTab(self.github_service, self._theme, self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.system_tab, "Système")
        self._tabs.addTab(self.services_tab, "Services")
        self.setCentralWidget(self._tabs)
