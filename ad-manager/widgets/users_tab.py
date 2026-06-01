"""Onglet « Utilisateurs » : liste des utilisateurs et actions de gestion."""

from __future__ import annotations

import logging

from models.ad_user import ADUser
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from services.ad_service import ADService

from core.theme import ThemeManager

logger = logging.getLogger(__name__)

_COLUMNS = ("Nom", "Login", "Email", "État")
_STATE_ENABLED = "Activé"
_STATE_DISABLED = "Désactivé"

# Erreurs métier remontées à l'utilisateur sans planter l'application.
_ACTION_ERRORS = (PermissionError, KeyError, RuntimeError)


class UserDialog(QDialog):
    """Dialogue de saisie d'un utilisateur (création ou modification).

    En mode modification (``user`` fourni), le login est verrouillé et le mot
    de passe laissé vide signifie « inchangé ».
    """

    def __init__(
        self,
        theme: ThemeManager,
        user: ADUser | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise le dialogue.

        Args:
            theme: Gestionnaire de thème pour les styles.
            user: Utilisateur à pré-remplir (mode modification), ou ``None``.
            parent: Widget parent optionnel.
        """
        super().__init__(parent)
        self._theme = theme
        self._user = user
        self._build_ui()

    def _build_ui(self) -> None:
        """Construit le formulaire (nom, login, email, mot de passe)."""
        self.setWindowTitle("Modifier l'utilisateur" if self._user else "Créer un utilisateur")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._edit_name = QLineEdit(self)
        self._edit_login = QLineEdit(self)
        self._edit_email = QLineEdit(self)
        self._edit_password = QLineEdit(self)
        self._edit_password.setEchoMode(QLineEdit.EchoMode.Password)

        if self._user is not None:
            self._edit_name.setText(self._user.display_name)
            self._edit_login.setText(self._user.username)
            self._edit_login.setEnabled(False)  # le login n'est pas modifiable
            self._edit_email.setText(self._user.email)

        form.addRow("Nom", self._edit_name)
        form.addRow("Login", self._edit_login)
        form.addRow("Email", self._edit_email)
        form.addRow("Mot de passe", self._edit_password)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setStyleSheet(self._theme.global_style())

    def values(self) -> dict[str, str]:
        """Retourne les valeurs saisies.

        Returns:
            Un mapping ``username``/``display_name``/``email``/``password``.
        """
        return {
            "username": self._edit_login.text().strip(),
            "display_name": self._edit_name.text().strip(),
            "email": self._edit_email.text().strip(),
            "password": self._edit_password.text(),
        }


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
        super().__init__(parent)
        self._service = service
        self._theme = theme
        self._users: list[ADUser] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construit l'interface (table des utilisateurs, boutons d'action)."""
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            len(_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        self._btn_create = QPushButton("Créer", self)
        self._btn_modify = QPushButton("Modifier", self)
        self._btn_delete = QPushButton("Supprimer", self)
        self._btn_create.clicked.connect(self._on_create_clicked)
        self._btn_modify.clicked.connect(self._on_modify_clicked)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        buttons.addWidget(self._btn_create)
        buttons.addWidget(self._btn_modify)
        buttons.addWidget(self._btn_delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Applique le thème courant aux widgets de l'onglet."""
        self.setStyleSheet(self._theme.global_style())
        self._btn_create.setStyleSheet(self._theme.button_style())
        self._btn_modify.setStyleSheet(self._theme.button_style())
        self._btn_delete.setStyleSheet(self._theme.button_style())

    def refresh(self) -> None:
        """Recharge la liste des utilisateurs depuis le service."""
        try:
            self._users = self._service.list_users()
        except _ACTION_ERRORS as exc:
            logger.error("Chargement des utilisateurs échoué: %s", exc)
            self._on_error(str(exc))
            return

        self._table.setRowCount(len(self._users))
        for row, user in enumerate(self._users):
            etat = _STATE_ENABLED if user.enabled else _STATE_DISABLED
            self._table.setItem(row, 0, QTableWidgetItem(user.display_name))
            self._table.setItem(row, 1, QTableWidgetItem(user.username))
            self._table.setItem(row, 2, QTableWidgetItem(user.email))
            self._table.setItem(row, 3, QTableWidgetItem(etat))

    def _selected_user(self) -> ADUser | None:
        """Retourne l'utilisateur de la ligne sélectionnée, ou ``None``."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._users):
            return None
        return self._users[row]

    def _on_create_clicked(self) -> None:
        """Slot : ouvre le dialogue de création et crée l'utilisateur."""
        dialog = UserDialog(self._theme, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self._service.create_user(
                values["username"],
                values["password"],
                display_name=values["display_name"],
                email=values["email"],
            )
        except _ACTION_ERRORS as exc:
            logger.error("Création d'utilisateur échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_modify_clicked(self) -> None:
        """Slot : ouvre le dialogue pré-rempli et modifie l'utilisateur."""
        user = self._selected_user()
        if user is None:
            QMessageBox.warning(self, "Aucune sélection", "Sélectionnez un utilisateur à modifier.")
            return
        dialog = UserDialog(self._theme, user=user, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self._service.modify_user(
                user.username,
                display_name=values["display_name"],
                email=values["email"],
            )
        except _ACTION_ERRORS as exc:
            logger.error("Modification d'utilisateur échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_delete_clicked(self) -> None:
        """Slot : supprime l'utilisateur sélectionné après confirmation."""
        user = self._selected_user()
        if user is None:
            QMessageBox.warning(
                self, "Aucune sélection", "Sélectionnez un utilisateur à supprimer."
            )
            return
        confirm = QMessageBox.question(
            self, "Confirmer la suppression", f"Supprimer l'utilisateur {user.username} ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_user(user.username)
        except _ACTION_ERRORS as exc:
            logger.error("Suppression d'utilisateur échouée: %s", exc)
            self._on_error(str(exc))
            return
        self.refresh()

    def _on_error(self, message: str) -> None:
        """Slot : affiche une erreur via ``QMessageBox``.

        Args:
            message: Message d'erreur à afficher.
        """
        QMessageBox.critical(self, "Erreur", message)
