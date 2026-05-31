"""Onglet « Services » : mises à jour des services Fenix via GitHub Releases."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from core.theme import ThemeManager
from services.github_service import GitHubReleaseService


class ServicesUpdateTab(QWidget):
    """Onglet listant les mises à jour des services Fenix (releases GitHub)."""

    def __init__(
        self,
        service: GitHubReleaseService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service interrogeant l'API GitHub Releases.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit l'interface (liste des services, versions, boutons)."""
        raise NotImplementedError

    def _on_refresh_clicked(self) -> None:
        """Slot : interroge GitHub pour rafraîchir l'état des services."""
        raise NotImplementedError

    def _on_update_clicked(self) -> None:
        """Slot : déclenche la mise à jour du service sélectionné."""
        raise NotImplementedError

    def _on_services_checked(self, updates: list) -> None:
        """Slot : peuple la liste avec l'état de mise à jour des services.

        Args:
            updates: Liste de ``ServiceUpdate`` à afficher.
        """
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
