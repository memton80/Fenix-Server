"""Vue dashboard : état des rôles et boutons activer/désactiver."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from core.theme import ThemeManager
from services.role_service import RoleService


class DashboardWidget(QWidget):
    """Dashboard listant les rôles (actif/inactif) avec actions d'activation."""

    def __init__(
        self,
        service: RoleService,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise le dashboard.

        Args:
            service: Service d'activation/désactivation des rôles.
            theme: Gestionnaire de thème pour les styles.
            parent: Widget parent optionnel.
        """
        raise NotImplementedError

    def _build_ui(self) -> None:
        """Construit l'interface (table des rôles, boutons Activer/Désactiver)."""
        raise NotImplementedError

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets du dashboard."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Recharge l'état des rôles depuis le service et met à jour la table."""
        raise NotImplementedError

    def _on_refresh_clicked(self) -> None:
        """Slot : rafraîchit l'état des rôles."""
        raise NotImplementedError

    def _on_activate_clicked(self) -> None:
        """Slot : active le rôle sélectionné."""
        raise NotImplementedError

    def _on_deactivate_clicked(self) -> None:
        """Slot : désactive le rôle sélectionné."""
        raise NotImplementedError

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        raise NotImplementedError
