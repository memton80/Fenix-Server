"""Service d'activation/désactivation des rôles Fenix Server.

S'appuie sur ``core.roles.RoleRegistry`` pour connaître les rôles et leur état,
et pilote les services systemd correspondants (start/stop + enable/disable) via
D-Bus. Toute activation/désactivation passe par Polkit AVANT l'action.

Nomenclature Polkit : ``org.fenixserver.server.enable-role`` /
``org.fenixserver.server.disable-role``.
"""

from __future__ import annotations

from core.roles import RoleRegistry
from models.role_status import RoleStatus

POLKIT_ACTION_ENABLE_ROLE = "org.fenixserver.server.enable-role"
POLKIT_ACTION_DISABLE_ROLE = "org.fenixserver.server.disable-role"


class RoleService:
    """Expose l'état des rôles et leur activation/désactivation."""

    def __init__(self, registry: RoleRegistry) -> None:
        """Initialise le service.

        Args:
            registry: Registre des rôles (déjà chargé) de ``core.roles``.
        """
        raise NotImplementedError

    def list_roles(self) -> list[RoleStatus]:
        """Retourne l'état (actif/inactif) de tous les rôles connus.

        Returns:
            La liste des :class:`RoleStatus`, triée comme ``RoleRegistry``.
        """
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError
