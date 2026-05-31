"""Service de mises à jour système via PackageKit (D-Bus).

Les transactions PackageKit étant asynchrones, ce service est un ``QObject``
qui expose des signaux Qt (progression, fin, erreurs). Toute opération
privilégiée (installation) passe par Polkit AVANT l'appel D-Bus.

Règle absolue : jamais ``subprocess``/``apt`` — uniquement l'API D-Bus
PackageKit via ``core.dbus_helper``.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from models.update_item import SystemPackageUpdate

PACKAGEKIT_SERVICE = "org.freedesktop.PackageKit"
PACKAGEKIT_OBJECT = "/org/freedesktop/PackageKit"
POLKIT_ACTION_INSTALL_SYSTEM = "org.fenixserver.update.install-system"


class PackageKitService(QObject):
    """Interroge et applique les mises à jour système via PackageKit.

    Signals:
        updates_found: Émis avec la ``list[SystemPackageUpdate]`` disponible.
        progress_changed: Émis avec l'avancement (0-100) d'une transaction.
        finished: Émis à la fin d'une transaction réussie.
        error_occurred: Émis avec un message d'erreur lisible.
    """

    updates_found = Signal(list)
    progress_changed = Signal(int)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialise le service et prépare l'accès au démon PackageKit.

        Args:
            parent: Parent Qt optionnel.
        """
        raise NotImplementedError

    def refresh_cache(self) -> None:
        """Rafraîchit le cache des dépôts (transaction PackageKit ``RefreshCache``).

        Asynchrone : la fin est signalée par :attr:`finished`, les erreurs par
        :attr:`error_occurred`.
        """
        raise NotImplementedError

    def request_updates(self) -> None:
        """Demande la liste des mises à jour disponibles (``GetUpdates``).

        Asynchrone : le résultat est émis via :attr:`updates_found`.
        """
        raise NotImplementedError

    def install_updates(self, package_ids: list[str]) -> None:
        """Installe les paquets indiqués (``UpdatePackages``).

        Vérifie l'autorisation Polkit
        (``org.fenixserver.update.install-system``) AVANT toute action.
        Asynchrone : progression via :attr:`progress_changed`, fin via
        :attr:`finished`.

        Args:
            package_ids: Identifiants PackageKit des paquets à mettre à jour.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
        """
        raise NotImplementedError
