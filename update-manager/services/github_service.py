"""Service de mises à jour des services Fenix via l'API GitHub Releases.

Compare la version installée de chaque service Fenix à la dernière release
publiée sur GitHub (accès en lecture seule à l'API REST GitHub via la stdlib
``urllib``) et installe la mise à jour à partir d'un asset de la release.

Flux d'installation :
1. Récupération de la dernière release du dépôt.
2. Sélection de l'asset correspondant au motif ``asset_pattern``.
3. Téléchargement de l'asset dans un dossier temporaire.
4. Installation, protégée par Polkit
   (``org.fenixserver.update.install-service``) :
   - ``type": "deb"`` → ``dpkg -i`` (via ``pkexec``) ;
   - ``type": "script"`` → exécution du script (via ``pkexec``).

Un rôle sans champ ``install`` (``InstallSpec`` à ``None``) requiert une
installation manuelle : :class:`ManualInstallRequired` est alors levée.

``dpkg``/script en ``subprocess`` est un cas exceptionnel explicitement autorisé
(asset hors dépôt apt) ; la règle « jamais ``apt`` en ``subprocess`` » reste
valable, l'installation système passant elle par PackageKit.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from models.update_item import ServiceUpdate

from core.polkit import PolkitClient
from core.roles import INSTALL_TYPE_DEB, INSTALL_TYPE_SCRIPT

if TYPE_CHECKING:
    from core.roles import InstallSpec

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
POLKIT_ACTION_INSTALL_SERVICE = "org.fenixserver.update.install-service"

_ACCEPT_HEADER = "application/vnd.github+json"
_DOWNLOAD_ACCEPT_HEADER = "application/octet-stream"


class ManualInstallRequired(RuntimeError):
    """Levée quand un service n'a pas de champ ``install`` (install manuelle)."""


class GitHubReleaseService:
    """Vérifie et installe les dernières releases GitHub des services Fenix."""

    def __init__(
        self,
        api_base: str = GITHUB_API_BASE,
        *,
        timeout: float = 10.0,
        polkit: PolkitClient | None = None,
    ) -> None:
        """Initialise le service.

        Args:
            api_base: URL de base de l'API GitHub (surchargeable pour les tests).
            timeout: Délai d'attente réseau en secondes.
            polkit: Client Polkit (injectable pour les tests) ; un client par
                défaut est créé si absent.
        """
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._polkit = polkit or PolkitClient()

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

    # --- flux d'installation ----------------------------------------------

    def find_asset(self, release: dict[str, object], pattern: str) -> tuple[str, str]:
        """Sélectionne dans une release l'asset correspondant à un motif.

        Args:
            release: JSON de release GitHub décodé (doit contenir ``assets``).
            pattern: Motif glob (``fnmatch``) comparé au nom des assets, ex.
                ``"*.deb"`` ou ``"install.sh"``.

        Returns:
            Le couple ``(nom, url_de_téléchargement)`` du premier asset trouvé.

        Raises:
            RuntimeError: si aucun asset ne correspond au motif.
        """
        assets = release.get("assets") or []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", ""))
            if fnmatch.fnmatch(name, pattern):
                url = str(asset.get("browser_download_url", ""))
                if not url:
                    continue
                return name, url
        raise RuntimeError(f"Aucun asset ne correspond au motif '{pattern}'")

    def download_asset(self, url: str, dest_dir: str | Path) -> Path:
        """Télécharge un asset de release dans un dossier.

        Args:
            url: URL de téléchargement de l'asset.
            dest_dir: Dossier de destination (typiquement temporaire).

        Returns:
            Le chemin du fichier téléchargé.

        Raises:
            RuntimeError: en cas d'erreur réseau.
        """
        filename = url.rsplit("/", 1)[-1] or "asset"
        dest = Path(dest_dir) / filename
        request = urllib.request.Request(url, headers={"Accept": _DOWNLOAD_ACCEPT_HEADER})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                with dest.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
        except urllib.error.URLError as exc:
            logger.error("Téléchargement de l'asset échoué (%s): %s", url, exc)
            raise RuntimeError(f"Téléchargement de l'asset échoué: {url}") from exc
        return dest

    def install_service(self, repo: str, install: InstallSpec | None) -> None:
        """Installe (ou met à jour) un service depuis sa dernière release GitHub.

        Flux complet : vérification Polkit, récupération de la release,
        sélection puis téléchargement de l'asset, installation via ``dpkg`` ou
        script. Le dossier temporaire est nettoyé en fin d'opération.

        Args:
            repo: Dépôt GitHub ``"owner/name"`` hébergeant les releases.
            install: Modalités d'installation, ou ``None``.

        Raises:
            ManualInstallRequired: si ``install`` est ``None`` (pas d'asset
                automatisable → installation manuelle requise).
            PermissionError: si l'action est refusée par Polkit.
            RuntimeError: en cas d'erreur réseau, d'asset introuvable ou d'échec
                de l'installation.
        """
        if install is None:
            raise ManualInstallRequired(
                f"Aucune modalité d'installation pour {repo}: installation manuelle requise"
            )

        if not self._polkit.check_authorization(POLKIT_ACTION_INSTALL_SERVICE):
            raise PermissionError(f"Action refusée par Polkit: {POLKIT_ACTION_INSTALL_SERVICE}")

        release = self.latest_release(repo)
        _, url = self.find_asset(release, install.asset_pattern)
        with tempfile.TemporaryDirectory(prefix="fenix-install-") as tmp_dir:
            asset_path = self.download_asset(url, tmp_dir)
            self._run_install(install.type, asset_path)

    def _run_install(self, install_type: str, asset_path: Path) -> None:
        """Exécute la commande d'installation privilégiée de l'asset téléchargé.

        L'élévation se fait via ``pkexec`` ; l'autorisation Polkit a déjà été
        vérifiée par :meth:`install_service` (jamais après l'action).

        Args:
            install_type: ``"deb"`` ou ``"script"``.
            asset_path: Chemin de l'asset téléchargé.

        Raises:
            RuntimeError: si le type est inconnu ou si la commande échoue.
        """
        if install_type == INSTALL_TYPE_DEB:
            command = ["pkexec", "dpkg", "-i", str(asset_path)]
        elif install_type == INSTALL_TYPE_SCRIPT:
            command = ["pkexec", "sh", str(asset_path)]
        else:
            raise RuntimeError(f"Type d'installation non supporté: {install_type}")

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Installation échouée (%s): code=%s stderr=%s",
                " ".join(command),
                exc.returncode,
                exc.stderr,
            )
            raise RuntimeError(f"Installation échouée (code {exc.returncode})") from exc
