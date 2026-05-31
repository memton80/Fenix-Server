"""Fenêtre principale du Server Manager : dashboard d'activation des rôles."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget

from core.theme import ThemeManager

WINDOW_TITLE = "Fenix Server — Gestionnaire de serveur"
WINDOW_ICON_NAME = "preferences-system"


class ServerManagerWindow(QMainWindow):
    """Fenêtre principale exposant le dashboard des rôles."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre et le dashboard.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit l'interface : charge les rôles et place le dashboard au centre."""
        raise NotImplementedError
