"""Service de mises à jour système via PackageKit (D-Bus).

Les transactions PackageKit étant asynchrones, ce service est un ``QObject``
qui expose des signaux Qt (progression, fin, erreurs). Toute opération
privilégiée (installation) passe par Polkit AVANT l'appel D-Bus.

Modèle PackageKit : le démon crée une *transaction* (objet D-Bus jetable) ;
on connecte ses signaux (``Package``, ``ItemProgress``/propriétés, ``Finished``,
``ErrorCode``) puis on lance la méthode (``GetUpdates``, ``RefreshCache``,
``UpdatePackages``).

Règle absolue : jamais ``subprocess``/``apt`` — uniquement l'API D-Bus
PackageKit via ``core.dbus_helper``.
"""

from __future__ import annotations

import logging

from dasbus.error import DBusError
from PySide6.QtCore import QObject, Signal

from core.dbus_helper import get_system_bus, service_available
from core.polkit import PolkitClient
from models.update_item import SystemPackageUpdate

logger = logging.getLogger(__name__)

PACKAGEKIT_SERVICE = "org.freedesktop.PackageKit"
PACKAGEKIT_OBJECT = "/org/freedesktop/PackageKit"
POLKIT_ACTION_INSTALL_SYSTEM = "org.fenixserver.update.install-system"

# Bitfields PackageKit (org.freedesktop.PackageKit).
_FILTER_NONE = 0
_TRANSACTION_FLAG_NONE = 0


def _unwrap(value: object) -> object:
    """Déballe une valeur éventuellement enveloppée dans un variant GLib."""
    depth = 0
    while hasattr(value, "unpack") and depth < 5:
        value = value.unpack()
        depth += 1
    return value


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
        super().__init__(parent)
        self._polkit = PolkitClient()
        # Garde une référence vivante aux proxies de transaction tant qu'ils
        # peuvent émettre des signaux (sinon ils seraient ramassés par le GC).
        self._transactions: list[object] = []

    # --- transactions -----------------------------------------------------

    def _create_transaction(self) -> object:
        """Crée une transaction PackageKit et retourne son proxy D-Bus.

        Raises:
            RuntimeError: si PackageKit n'est pas disponible.
        """
        if not service_available(PACKAGEKIT_SERVICE):
            raise RuntimeError("PackageKit non disponible")
        bus = get_system_bus()
        manager = bus.get_proxy(PACKAGEKIT_SERVICE, PACKAGEKIT_OBJECT)
        transaction_path = manager.CreateTransaction()
        return bus.get_proxy(PACKAGEKIT_SERVICE, transaction_path)

    def _track(self, transaction: object) -> None:
        self._transactions.append(transaction)

    def _forget(self, transaction: object) -> None:
        if transaction in self._transactions:
            self._transactions.remove(transaction)

    # --- opérations publiques --------------------------------------------

    def refresh_cache(self) -> None:
        """Rafraîchit le cache des dépôts (transaction PackageKit ``RefreshCache``).

        Asynchrone : la fin est signalée par :attr:`finished`, les erreurs par
        :attr:`error_occurred`.
        """
        transaction = self._begin()
        if transaction is None:
            return
        transaction.Finished.connect(self._make_finished_handler(transaction))
        transaction.RefreshCache(False)

    def request_updates(self) -> None:
        """Demande la liste des mises à jour disponibles (``GetUpdates``).

        Asynchrone : le résultat est émis via :attr:`updates_found`.
        """
        transaction = self._begin()
        if transaction is None:
            return

        found: list[SystemPackageUpdate] = []

        def on_package(info: int, package_id: str, summary: str) -> None:
            parts = package_id.split(";")
            name = parts[0] if parts else package_id
            version = parts[1] if len(parts) > 1 else ""
            found.append(SystemPackageUpdate(package_id, name, version, summary))

        def on_finished(exit_code: int, runtime: int) -> None:
            self._forget(transaction)
            self.updates_found.emit(found)

        transaction.Package.connect(on_package)
        transaction.Finished.connect(on_finished)
        transaction.GetUpdates(_FILTER_NONE)

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
        if not self._polkit.check_authorization(POLKIT_ACTION_INSTALL_SYSTEM):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_INSTALL_SYSTEM}")

        transaction = self._begin()
        if transaction is None:
            return
        transaction.PropertiesChanged.connect(self._on_properties_changed)
        transaction.Finished.connect(self._make_finished_handler(transaction))
        transaction.UpdatePackages(_TRANSACTION_FLAG_NONE, package_ids)

    # --- helpers de connexion / handlers ----------------------------------

    def _begin(self) -> object | None:
        """Crée une transaction, branche le handler d'erreur, la suit.

        Returns:
            Le proxy de transaction, ou ``None`` si la création a échoué (un
            ``error_occurred`` a alors déjà été émis).
        """
        try:
            transaction = self._create_transaction()
        except (RuntimeError, DBusError) as exc:
            logger.error("Création de transaction PackageKit impossible: %s", exc)
            self.error_occurred.emit(str(exc))
            return None
        transaction.ErrorCode.connect(self._make_error_handler(transaction))
        self._track(transaction)
        return transaction

    def _on_properties_changed(
        self, interface: str, changed: dict[str, object], invalidated: list[str]
    ) -> None:
        """Émet :attr:`progress_changed` quand la propriété ``Percentage`` évolue."""
        if "Percentage" in changed:
            percent = _unwrap(changed["Percentage"])
            if isinstance(percent, int) and 0 <= percent <= 100:
                self.progress_changed.emit(percent)

    def _make_error_handler(self, transaction: object):
        def on_error(code: int, details: str) -> None:
            self._forget(transaction)
            self.error_occurred.emit(str(details))

        return on_error

    def _make_finished_handler(self, transaction: object):
        def on_finished(exit_code: int, runtime: int) -> None:
            self._forget(transaction)
            self.finished.emit()

        return on_finished
