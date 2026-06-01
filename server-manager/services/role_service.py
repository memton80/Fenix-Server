"""Service d'activation/désactivation des rôles Fenix Server.

S'appuie sur ``core.roles.RoleRegistry`` pour connaître les rôles et leur état,
et pilote les services systemd correspondants (enable/disable + start/stop) via
``pkexec systemctl`` en ``subprocess``. Toute activation/désactivation passe par
Polkit AVANT l'action.

L'élévation se fait via ``pkexec`` (même approche que ``install_service`` dans
l'update-manager) ; l'autorisation Polkit a déjà été vérifiée AVANT l'appel.

Nomenclature Polkit : ``org.fenixserver.server.enable-role`` /
``org.fenixserver.server.disable-role``.
"""

from __future__ import annotations

import logging
import subprocess

from models.role_status import RoleStatus

from core.polkit import PolkitClient
from core.roles import RoleRegistry

logger = logging.getLogger(__name__)

POLKIT_ACTION_ENABLE_ROLE = "org.fenixserver.server.enable-role"
POLKIT_ACTION_DISABLE_ROLE = "org.fenixserver.server.disable-role"

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
        """Active un rôle : active et démarre son unité (``systemctl enable --now``).

        Vérifie l'autorisation Polkit
        (``org.fenixserver.server.enable-role``) AVANT toute action.

        Args:
            role_id: Identifiant du rôle à activer.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si le rôle est inconnu.
            RuntimeError: si la commande ``systemctl`` échoue.
        """
        role = self._registry.get(role_id)
        if not self._polkit.check_authorization(POLKIT_ACTION_ENABLE_ROLE):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_ENABLE_ROLE}")

        unit = _unit_name(role.service_name)
        logger.info("Activation du rôle %s (unité %s)", role_id, unit)
        self._run_systemctl("enable", unit)

    def disable_role(self, role_id: str) -> None:
        """Désactive un rôle : arrête et désactive son unité (``systemctl disable --now``).

        Vérifie l'autorisation Polkit
        (``org.fenixserver.server.disable-role``) AVANT toute action.

        Args:
            role_id: Identifiant du rôle à désactiver.

        Raises:
            PermissionError: si l'action est refusée par Polkit.
            KeyError: si le rôle est inconnu.
            RuntimeError: si la commande ``systemctl`` échoue.
        """
        role = self._registry.get(role_id)
        if not self._polkit.check_authorization(POLKIT_ACTION_DISABLE_ROLE):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_DISABLE_ROLE}")

        unit = _unit_name(role.service_name)
        logger.info("Désactivation du rôle %s (unité %s)", role_id, unit)
        self._run_systemctl("disable", unit)

    def _run_systemctl(self, verb: str, unit: str) -> None:
        """Exécute ``pkexec systemctl <verb> --now <unit>`` (action privilégiée).

        L'élévation se fait via ``pkexec`` ; l'autorisation Polkit a déjà été
        vérifiée par l'appelant (jamais après l'action).

        Args:
            verb: ``"enable"`` ou ``"disable"``.
            unit: Nom de l'unité systemd, ex. ``"smbd.service"``.

        Raises:
            RuntimeError: si la commande ``systemctl`` échoue.
        """
        command = ["pkexec", "systemctl", verb, "--now", unit]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Commande systemctl échouée (%s): code=%s stderr=%s",
                " ".join(command),
                exc.returncode,
                exc.stderr,
            )
            raise RuntimeError(f"Commande systemctl échouée (code {exc.returncode})") from exc
