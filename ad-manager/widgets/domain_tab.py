"""Onglet « Domaine » : informations du domaine (nom, DC, statut Samba)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from services.ad_service import ADService

from core.theme import ThemeManager


class DomainTab(QWidget):
    """Onglet affichant les informations du domaine et l'état de Samba."""

    def __init__(
        self,
        service: ADService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service des opérations AD.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit l'interface (nom du domaine, DC, statut Samba)."""
        raise NotImplementedError

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Recharge les informations du domaine depuis le service."""
        raise NotImplementedError

    def _on_refresh_clicked(self) -> None:
        """Slot : rafraîchit les informations du domaine."""
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
