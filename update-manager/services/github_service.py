"""Service de mises à jour des services Fenix via l'API GitHub Releases.

Compare la version installée de chaque service Fenix à la dernière release
publiée sur GitHub. Accès en lecture seule à l'API REST GitHub ; l'installation
effective d'une mise à jour de service (download + redéploiement via systemd)
relève d'un autre flux protégé par Polkit
(``org.fenixserver.update.install-service``).
"""

from __future__ import annotations

from models.update_item import ServiceUpdate

GITHUB_API_BASE = "https://api.github.com"
POLKIT_ACTION_INSTALL_SERVICE = "org.fenixserver.update.install-service"


class GitHubReleaseService:
    """Vérifie les dernières releases GitHub des services Fenix."""

    def __init__(self, api_base: str = GITHUB_API_BASE) -> None:
        """Initialise le service.

        Args:
            api_base: URL de base de l'API GitHub (surchargeable pour les tests).
        """
        raise NotImplementedError

    def latest_release(self, repo: str) -> dict[str, object]:
        """Retourne les métadonnées de la dernière release d'un dépôt.

        Args:
            repo: Dépôt au format ``"owner/name"``.

        Returns:
            Le JSON de la release décodé (tag, URL, assets, ...).

        Raises:
            RuntimeError: en cas d'erreur réseau ou de réponse API invalide.
        """
        raise NotImplementedError

    def check_update(self, service_id: str, repo: str, current_version: str) -> ServiceUpdate:
        """Construit le :class:`ServiceUpdate` d'un service en interrogeant GitHub.

        Args:
            service_id: Identifiant du service Fenix.
            repo: Dépôt GitHub ``"owner/name"`` hébergeant les releases.
            current_version: Version actuellement installée.

        Returns:
            L'état de mise à jour du service.

        Raises:
            RuntimeError: en cas d'erreur réseau ou de réponse API invalide.
        """
        raise NotImplementedError

    def check_all(self, services: dict[str, tuple[str, str]]) -> list[ServiceUpdate]:
        """Vérifie plusieurs services en une passe.

        Args:
            services: Mapping ``service_id -> (repo, current_version)``.

        Returns:
            La liste des :class:`ServiceUpdate` correspondants.
        """
        raise NotImplementedError
