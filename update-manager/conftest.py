"""Configuration pytest pour l'Update Manager.

Rend importables :
- les packages intra-app (``models``, ``services``, ``widgets``) via le dossier
  de l'app ;
- la lib partagée ``core`` via la racine du projet.
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent

for _path in (str(_APP_DIR), str(_PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
