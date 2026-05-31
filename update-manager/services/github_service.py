"""Service de mises à jour des services Fenix via l'API GitHub Releases.

Compare la version installée de chaque service Fenix à la dernière release
publiée sur GitHub. Accès en lecture seule à l'API REST GitHub (stdlib
``urllib``, aucune dépendance supplémentaire) ; l'installation effective d'une
mise à jour de service (download + redéploiement via systemd) relève d'un autre
flux protégé par Polkit (``org.fenixserver.update.install-service``).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from models.update_item import ServiceUpdate

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
POLKIT_ACTION_INSTALL_SERVICE = "org.fenixserver.update.install-service"

_ACCEPT_HEADER = "application/vnd.github+json"


class GitHubReleaseService:
    """Vérifie les dernières releases GitHub des services Fenix."""

    def __init__(self, api_base: str = GITHUB_API_BASE, *, timeout: float = 10.0) -> None:
        """Initialise le service.

        Args:
            api_base: URL de base de l'API GitHub (surchargeable pour les tests).
            timeout: Délai d'attente réseau en secondes.
        """
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout

    def _get_json(self, url: str) -> dict[str, object]:
        """Effectue un GET et décode la réponse JSON.

        Args:
            url: URL absolue à interroger.

        Returns:
            Le corps de réponse JSON décodé.

        Raises:
            RuntimeError: en cas d'erreur réseau ou de JSON invalide.
        """
        request = urllib.request.Request(url, headers={"Accept": _ACCEPT_HEADER})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = response.read()
        except urllib.error.URLError as exc:
            logger.error("Requête GitHub échouée (%s): %s", url, exc)
            raise RuntimeError(f"Requête GitHub échouée: {url}") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.error("Réponse GitHub invalide (%s): %s", url, exc)
            raise RuntimeError(f"Réponse GitHub invalide: {url}") from exc

    def latest_release(self, repo: str) -> dict[str, object]:
        """Retourne les métadonnées de la dernière release d'un dépôt.

        Args:
            repo: Dépôt au format ``"owner/name"``.

        Returns:
            Le JSON de la release décodé (tag, URL, assets, ...).

        Raises:
            RuntimeError: en cas d'erreur réseau ou de réponse API invalide.
        """
        return self._get_json(f"{self._api_base}/repos/{repo}/releases/latest")

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
        release = self.latest_release(repo)
        latest_version = str(release.get("tag_name", ""))
        release_url = str(release.get("html_url", ""))
        return ServiceUpdate(
            service_id=service_id,
            name=repo.rsplit("/", 1)[-1],
            current_version=current_version,
            latest_version=latest_version,
            release_url=release_url,
        )

    def check_all(self, services: dict[str, tuple[str, str]]) -> list[ServiceUpdate]:
        """Vérifie plusieurs services en une passe.

        Un service dont la vérification échoue est ignoré (loggé) pour ne pas
        empêcher la vérification des autres.

        Args:
            services: Mapping ``service_id -> (repo, current_version)``.

        Returns:
            La liste des :class:`ServiceUpdate` vérifiés avec succès.
        """
        results: list[ServiceUpdate] = []
        for service_id, (repo, current_version) in services.items():
            try:
                results.append(self.check_update(service_id, repo, current_version))
            except RuntimeError as exc:
                logger.warning("Vérification de %s (%s) ignorée: %s", service_id, repo, exc)
        return results
