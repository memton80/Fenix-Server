"""Onglet « Groupes » : liste des groupes et actions de gestion."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from services.ad_service import ADService

from core.theme import ThemeManager


class GroupsTab(QWidget):
    """Onglet listant les groupes du domaine (créer / supprimer)."""

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
        """Construit l'interface (table des groupes, boutons d'action)."""
        raise NotImplementedError

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Recharge la liste des groupes depuis le service."""
        raise NotImplementedError

    def _on_create_clicked(self) -> None:
        """Slot : crée un nouveau groupe."""
        raise NotImplementedError

    def _on_delete_clicked(self) -> None:
        """Slot : supprime le groupe sélectionné."""
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
