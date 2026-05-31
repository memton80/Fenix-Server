"""Helpers de connexion D-Bus pour les services système Fenix Server.

Toutes les apps passent par ces helpers pour parler aux services système
(PackageKit, systemd, home1, ...). On utilise exclusivement ``dasbus`` et le
**system bus** — jamais le session bus, jamais dbus-python ou gi.repository.Gio.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dasbus.connection import MessageBus
    from dasbus.client.proxy import InterfaceProxy


def get_system_bus() -> "MessageBus":
    """Retourne la connexion au bus système D-Bus (dasbus ``SystemMessageBus``).

    La connexion doit être réutilisée par l'appelant plutôt que recréée à
    chaque appel.

    Returns:
        La connexion au bus système.

    Raises:
        RuntimeError: si le bus système est indisponible.
    """
    raise NotImplementedError


def service_available(service_name: str) -> bool:
    """Indique si un service est disponible (activable ou déjà actif) sur le bus système.

    À appeler AVANT tout appel à un proxy D-Bus, conformément aux règles
    d'architecture.

    Args:
        service_name: Nom bus du service, ex. ``"org.freedesktop.PackageKit"``.

    Returns:
        ``True`` si le service peut être contacté, ``False`` sinon.
    """
    raise NotImplementedError


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
    raise NotImplementedError
