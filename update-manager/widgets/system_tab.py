"""Onglet « Système » : mises à jour des paquets via PackageKit."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from core.theme import ThemeManager
from services.packagekit_service import PackageKitService


class SystemUpdateTab(QWidget):
    """Onglet listant et appliquant les mises à jour système (PackageKit)."""

    def __init__(
        self,
        service: PackageKitService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise l'onglet.

        Args:
            service: Service PackageKit fournissant les mises à jour système.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit l'interface (liste des paquets, boutons, barre de progression)."""
        raise NotImplementedError

    def _connect_signals(self) -> None:
        """Connecte les signaux du service PackageKit aux slots de l'onglet."""
        raise NotImplementedError

    def _on_refresh_clicked(self) -> None:
        """Slot : rafraîchit le cache puis demande la liste des mises à jour."""
        raise NotImplementedError

    def _on_install_clicked(self) -> None:
        """Slot : installe les mises à jour système sélectionnées."""
        raise NotImplementedError

    def _on_updates_found(self, updates: list) -> None:
        """Slot : peuple la liste avec les mises à jour trouvées.

        Args:
            updates: Liste de ``SystemPackageUpdate`` émise par le service.
        """
        raise NotImplementedError

    def _on_progress_changed(self, percent: int) -> None:
        """Slot : met à jour la barre de progression.

        Args:
            percent: Avancement de la transaction (0-100).
        """
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
