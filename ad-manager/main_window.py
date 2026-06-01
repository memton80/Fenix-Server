"""Fenêtre principale de l'AD Manager : onglets Utilisateurs / Groupes / Domaine."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget

from core.theme import ThemeManager

WINDOW_TITLE = "Fenix Server — Gestionnaire Active Directory"
WINDOW_ICON_NAME = "system-users"


class ADManagerWindow(QMainWindow):
    """Fenêtre principale avec un ``QTabWidget`` à trois onglets.

    Onglets :
        - « Utilisateurs » : gestion des comptes du domaine.
        - « Groupes »      : gestion des groupes du domaine.
        - « Domaine »      : informations du domaine et état de Samba.
    """

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        """Initialise la fenêtre, les services et les onglets.

        Args:
            theme: Gestionnaire de thème appliqué à la fenêtre.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit la barre d'onglets et instancie les trois onglets."""
        raise NotImplementedError
