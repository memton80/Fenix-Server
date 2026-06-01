"""Onglet « Utilisateurs » : liste des utilisateurs et actions de gestion."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from services.ad_service import ADService

from core.theme import ThemeManager


class UsersTab(QWidget):
    """Onglet listant les utilisateurs du domaine (créer / modifier / supprimer)."""

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
        """Construit l'interface (table des utilisateurs, boutons d'action)."""
        raise NotImplementedError

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Recharge la liste des utilisateurs depuis le service."""
        raise NotImplementedError

    def _on_create_clicked(self) -> None:
        """Slot : crée un nouvel utilisateur."""
        raise NotImplementedError

    def _on_modify_clicked(self) -> None:
        """Slot : modifie l'utilisateur sélectionné."""
        raise NotImplementedError

    def _on_delete_clicked(self) -> None:
        """Slot : supprime l'utilisateur sélectionné."""
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
