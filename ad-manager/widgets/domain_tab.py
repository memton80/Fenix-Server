"""Onglet « Domaine » : informations du domaine (nom, DC, statut Samba)."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from services.ad_service import ADService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_PLACEHOLDER = "—"

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, RuntimeError)


class DomainTab(QWidget):
    """Onglet affichant les informations du domaine et l'état de Samba (lecture seule)."""

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
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (champs en lecture seule, bouton Rafraîchir)."""
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._value_domain = QLabel(_PLACEHOLDER, self)
        self._value_dc = QLabel(_PLACEHOLDER, self)
        self._value_samba = QLabel(_PLACEHOLDER, self)
        form.addRow("Domaine", self._value_domain)
        form.addRow("Contrôleur de domaine", self._value_dc)
        form.addRow("Statut Samba", self._value_samba)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self._btn_refresh = QPushButton("Rafraîchir", self)
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)
        buttons.addWidget(self._btn_refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addStretch(1)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._value_domain.setStyleSheet(self._theme.label_style())
        self._value_dc.setStyleSheet(self._theme.label_style())
        self._value_samba.setStyleSheet(self._theme.label_style())
        self._btn_refresh.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge les informations du domaine depuis le service."""
        try:
            info = self._service.domain_info()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des infos domaine échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._value_domain.setText(info.get("name") or _PLACEHOLDER)
        self._value_dc.setText(info.get("dc") or _PLACEHOLDER)
        self._value_samba.setText(info.get("samba") or _PLACEHOLDER)

    def _on_refresh_clicked(self) -> None:
        """Slot : rafraîchit les informations du domaine."""
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
