"""Service d'activation/désactivation des rôles Fenix Server.

S'appuie sur ``core.roles.RoleRegistry`` pour connaître les rôles et leur état,
et pilote les services systemd correspondants (start/stop + enable/disable) via
D-Bus. Toute activation/désactivation passe par Polkit AVANT l'action.

Nomenclature Polkit : ``org.fenixserver.server.enable-role`` /
``org.fenixserver.server.disable-role``.
"""

from __future__ import annotations

import logging

from models.role_status import RoleStatus

from core.dbus_helper import get_service_proxy
from core.polkit import PolkitClient
from core.roles import RoleRegistry

logger = logging.getLogger(__name__)

POLKIT_ACTION_ENABLE_ROLE = "org.fenixserver.server.enable-role"
POLKIT_ACTION_DISABLE_ROLE = "org.fenixserver.server.disable-role"

SYSTEMD_SERVICE = "org.freedesktop.systemd1"
SYSTEMD_OBJECT = "/org/freedesktop/systemd1"

# Suffixes d'unités systemd ; sans suffixe connu, ".service" est ajouté.
_SYSTEMD_SUFFIXES = (
    ".service",
    ".socket",
    ".target",
    ".timer",
    ".mount",
    ".path",
    ".slice",
)
_DEFAULT_SYSTEMD_SUFFIX = ".service"

# Mode de remplacement des jobs systemd (cf. StartUnit/StopUnit).
_JOB_MODE_REPLACE = "replace"


def _unit_name(service_name: str) -> str:
    """Normalise un nom de service en nom d'unité systemd.

    Args:
        service_name: Nom du service tel que défini dans le rôle (ex. ``"smbd"``).

    Returns:
        Le nom d'unité systemd, suffixé en ``.service`` si nécessaire.
    """
    if service_name.endswith(_SYSTEMD_SUFFIXES):
        return service_name
    return f"{service_name}{_DEFAULT_SYSTEMD_SUFFIX}"


class RoleService:
    """Expose l'état des rôles et leur activation/désactivation."""

    def __init__(self, registry: RoleRegistry, polkit: PolkitClient | None = None) -> None:
        """Initialise le service.

        Args:
            registry: Registre des rôles (déjà chargé) de ``core.roles``.
            polkit: Client Polkit (injectable pour les tests) ; un client par
                défaut est créé si absent.
        """
        self._registry = registry
        self._polkit = polkit or PolkitClient()

    def list_roles(self) -> list[RoleStatus]:
        """Retourne l'état (actif/inactif) de tous les rôles connus.

        Returns:
            La liste des :class:`RoleStatus`, triée comme ``RoleRegistry``.
        """
        return [
            RoleStatus(role=role, active=self._registry.is_active(role.id))
            for role in self._registry.all_roles()
        ]

    def enable_role(self, role_id: str) -> None:
        """Active un rôle : démarre et active son service systemd.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.server.enable-role``) AVANT toute action.

        Args:
            role_id: Identifiant du rôle à activer.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si le rôle est inconnu.
        """
        role = self._registry.get(role_id)
        if not self._polkit.check_authorization(POLKIT_ACTION_ENABLE_ROLE):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_ENABLE_ROLE}")

        unit = _unit_name(role.service_name)
        logger.info("Activation du rôle %s (unité %s)", role_id, unit)
        manager = get_service_proxy(SYSTEMD_SERVICE, SYSTEMD_OBJECT)
        # Activation persistante (enable) puis démarrage immédiat (start).
        manager.EnableUnitFiles([unit], False, True)
        manager.StartUnit(unit, _JOB_MODE_REPLACE)

    def disable_role(self, role_id: str) -> None:
        """Désactive un rôle : arrête et désactive son service systemd.

        Vérifie l'autorisation Polkit
        (``org.fenixserver.server.disable-role``) AVANT toute action.

        Args:
            role_id: Identifiant du rôle à désactiver.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si le rôle est inconnu.
        """
        role = self._registry.get(role_id)
        if not self._polkit.check_authorization(POLKIT_ACTION_DISABLE_ROLE):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_DISABLE_ROLE}")

        unit = _unit_name(role.service_name)
        logger.info("Désactivation du rôle %s (unité %s)", role_id, unit)
        manager = get_service_proxy(SYSTEMD_SERVICE, SYSTEMD_OBJECT)
        # Arrêt immédiat (stop) puis désactivation persistante (disable).
        manager.StopUnit(unit, _JOB_MODE_REPLACE)
        manager.DisableUnitFiles([unit], False)
