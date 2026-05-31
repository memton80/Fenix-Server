"""Helpers de connexion D-Bus pour les services système Fenix Server.

Toutes les apps passent par ces helpers pour parler aux services système
(PackageKit, systemd, home1, ...). On utilise exclusivement ``dasbus`` et le
**system bus** — jamais le session bus, jamais dbus-python ou gi.repository.Gio.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dasbus.connection import SystemMessageBus
from dasbus.error import DBusError

if TYPE_CHECKING:
    from dasbus.connection import MessageBus
    from dasbus.client.proxy import InterfaceProxy

logger = logging.getLogger(__name__)


def get_system_bus() -> "MessageBus":
    """Retourne la connexion au bus système D-Bus (dasbus ``SystemMessageBus``).

    La connexion doit être réutilisée par l'appelant plutôt que recréée à
    chaque appel.

    Returns:
        La connexion au bus système.

    Raises:
        RuntimeError: si le bus système est indisponible.
    """
    try:
        bus = SystemMessageBus()
        # Force l'établissement de la connexion pour détecter tout de suite
        # un bus système absent (plutôt qu'à la première utilisation).
        _ = bus.connection
        return bus
    except DBusError as exc:
        logger.error("Bus système D-Bus indisponible: %s", exc)
        raise RuntimeError("Bus système D-Bus indisponible") from exc


def service_available(service_name: str) -> bool:
    """Indique si un service est disponible (activable ou déjà actif) sur le bus système.

    À appeler AVANT tout appel à un proxy D-Bus, conformément aux règles
    d'architecture. Un service est considéré disponible s'il possède déjà un
    propriétaire sur le bus (actif) ou s'il est activable à la demande.

    Args:
        service_name: Nom bus du service, ex. ``"org.freedesktop.PackageKit"``.

    Returns:
        ``True`` si le service peut être contacté, ``False`` sinon.
    """
    try:
        dbus_daemon = get_system_bus().proxy
        if dbus_daemon.NameHasOwner(service_name):
            return True
        return service_name in dbus_daemon.ListActivatableNames()
    except (DBusError, RuntimeError) as exc:
        logger.error("Vérification de disponibilité de %s échouée: %s", service_name, exc)
        return False


def get_service_proxy(service_name: str, object_path: str) -> "InterfaceProxy":
    """Retourne un proxy D-Bus vers un objet d'un service système.

    Vérifie au préalable la disponibilité du service via :func:`service_available`.

    Args:
        service_name: Nom bus du service, ex. ``"org.freedesktop.PackageKit"``.
        object_path: Chemin de l'objet, ex. ``"/org/freedesktop/PackageKit"``.

    Returns:
        Le proxy d'interface vers l'objet demandé.

    Raises:
        RuntimeError: si le service n'est pas disponible.
    """
    if not service_available(service_name):
        raise RuntimeError(f"Service D-Bus indisponible: {service_name}")
    return get_system_bus().get_proxy(service_name, object_path)
