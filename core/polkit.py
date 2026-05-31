"""Client Polkit pour les opérations privilégiées de Fenix Server.

Wrapper autour de ``org.freedesktop.PolicyKit1.Authority``. Toute action qui
modifie le système DOIT passer par une vérification Polkit AVANT l'action.

Nomenclature des actions : ``org.fenixserver.<module>.<action>``
(ex. ``org.fenixserver.ad.create-user``).
"""

from __future__ import annotations


class PolkitClient:
    """Vérifie les autorisations Polkit via le bus système.

    Usage type dans une app::

        polkit = PolkitClient()
        if polkit.check_authorization("org.fenixserver.ad.create-user"):
            ...  # action privilégiée
    """

    def __init__(self) -> None:
        """Initialise le client et prépare la connexion à l'autorité Polkit."""
        raise NotImplementedError

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
        raise NotImplementedError

    def is_challenge(self, action_id: str) -> bool:
        """Indique si l'action requiert une authentification (challenge) sans la déclencher.

        Permet à l'UI d'anticiper l'affichage d'un cadenas / d'une invite.

        Args:
            action_id: ID de l'action Polkit à inspecter.

        Returns:
            ``True`` si une authentification serait demandée, ``False`` si
            l'action est déjà autorisée ou refusée d'office.
        """
        raise NotImplementedError
