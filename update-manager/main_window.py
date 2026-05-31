"""Fenêtre principale de l'Update Manager : deux onglets Système / Services."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget

from core.theme import ThemeManager


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
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les deux onglets."""
        raise NotImplementedError
