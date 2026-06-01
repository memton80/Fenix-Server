"""Configuration pytest pour l'AD Manager.

Rend importables :
- les packages intra-app (``models``, ``services``, ``widgets``) via le dossier
  de l'app ;
- la lib partagée ``core`` via la racine du projet.

Fournit aussi une ``QApplication`` headless (plateforme ``offscreen``) partagée
par tous les tests Qt.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent

for _path in (str(_APP_DIR), str(_PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ``ldap3`` est une dépendance runtime (cf. requirements.txt) mais peut être
# absente de l'environnement de test : on injecte un module factice pour que
# ``services.ldap_service`` s'importe. Les tests pilotent finement le
# comportement en patchant Server/Connection. Si ldap3 est réellement
# installé, ``setdefault`` n'écrase rien.
sys.modules.setdefault("ldap3", MagicMock())

# Tests sans serveur d'affichage : plateforme Qt offscreen (ni X11 ni Wayland).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """QApplication unique pour la session de test (requise par les QWidget)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
