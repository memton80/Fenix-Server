"""Client Polkit pour les opérations privilégiées de Fenix Server.

Wrapper autour de ``org.freedesktop.PolicyKit1.Authority``. Toute action qui
modifie le système DOIT passer par une vérification Polkit AVANT l'action.

Nomenclature des actions : ``org.fenixserver.<module>.<action>``
(ex. ``org.fenixserver.ad.create-user``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dasbus.error import DBusError
from dasbus.typing import Str, get_variant

from core.dbus_helper import get_system_bus, service_available

if TYPE_CHECKING:
    from dasbus.client.proxy import InterfaceProxy

logger = logging.getLogger(__name__)

POLKIT_SERVICE = "org.freedesktop.PolicyKit1"
POLKIT_OBJECT = "/org/freedesktop/PolicyKit1/Authority"

# Drapeaux de org.freedesktop.PolicyKit1.AuthorityFlags.
_FLAG_NONE = 0
_FLAG_ALLOW_USER_INTERACTION = 1


class PolkitClient:
    """Vérifie les autorisations Polkit via le bus système.

    Usage type dans une app::

        polkit = PolkitClient()
        if polkit.check_authorization("org.fenixserver.ad.create-user"):
            ...  # action privilégiée
    """

    def __init__(self) -> None:
        """Initialise le client et prépare la connexion à l'autorité Polkit."""
        self._authority: InterfaceProxy | None = None

    def _get_authority(self) -> "InterfaceProxy":
        """Retourne (en le créant à la demande) le proxy vers l'autorité Polkit.

        Raises:
            RuntimeError: si le service Polkit n'est pas disponible.
        """
        if self._authority is None:
            if not service_available(POLKIT_SERVICE):
                raise RuntimeError("Service Polkit indisponible")
            self._authority = get_system_bus().get_proxy(POLKIT_SERVICE, POLKIT_OBJECT)
        return self._authority

    def _build_subject(self) -> tuple[str, dict[str, object]]:
        """Construit le sujet Polkit identifiant le processus appelant.

        On utilise le sujet ``system-bus-name`` basé sur le nom unique de la
        connexion au bus système : c'est la forme recommandée pour qu'un
        processus s'identifie lui-même auprès de Polkit.
        """
        unique_name = get_system_bus().connection.get_unique_name()
        return ("system-bus-name", {"name": get_variant(Str, unique_name)})

    def _check(self, action_id: str, allow_interaction: bool) -> tuple[bool, bool]:
        """Appelle ``CheckAuthorization`` et renvoie ``(is_authorized, is_challenge)``.

        Raises:
            RuntimeError: si l'autorité Polkit est injoignable.
        """
        subject = self._build_subject()
        flags = _FLAG_ALLOW_USER_INTERACTION if allow_interaction else _FLAG_NONE
        try:
            result = self._get_authority().CheckAuthorization(
                subject,
                action_id,
                {},  # details
                flags,
                "",  # cancellation_id
            )
        except DBusError as exc:
            logger.error("CheckAuthorization a échoué pour %s: %s", action_id, exc)
            raise RuntimeError(f"Vérification Polkit impossible pour {action_id}") from exc

        is_authorized, is_challenge = bool(result[0]), bool(result[1])
        return is_authorized, is_challenge

    def check_authorization(self, action_id: str, *, allow_interaction: bool = True) -> bool:
        """Vérifie si le sujet courant est autorisé pour une action Polkit.

        Args:
            action_id: ID de l'action, ex. ``"org.fenixserver.ad.create-user"``.
            allow_interaction: Autorise Polkit à demander une authentification
                interactive (saisie de mot de passe) si nécessaire.

        Returns:
            ``True`` si l'action est autorisée, ``False`` sinon.

        Raises:
            RuntimeError: si l'autorité Polkit est injoignable.
        """
        is_authorized, _ = self._check(action_id, allow_interaction)
        return is_authorized

    def is_challenge(self, action_id: str) -> bool:
        """Indique si l'action requiert une authentification (challenge) sans la déclencher.

        Permet à l'UI d'anticiper l'affichage d'un cadenas / d'une invite.
        L'appel se fait sans interaction utilisateur pour ne déclencher aucune
        invite de mot de passe.

        Args:
            action_id: ID de l'action Polkit à inspecter.

        Returns:
            ``True`` si une authentification serait demandée, ``False`` si
            l'action est déjà autorisée ou refusée d'office.
        """
        _, is_challenge = self._check(action_id, allow_interaction=False)
        return is_challenge
