# Règles de style — Fenix Server

## Python / PySide6

### Général
- Python 3.12+ uniquement
- Type hints obligatoires sur toutes les fonctions publiques
- Docstrings sur toutes les classes et méthodes publiques
- Linter : ruff (pas flake8, pas pylint)
- Formatter : black (line-length = 100)

### Nommage
```python
# Classes : PascalCase
class AdUserManager:

# Méthodes/fonctions : snake_case
def create_user(self, username: str) -> bool:

# Constantes : SCREAMING_SNAKE_CASE
MAX_USERNAME_LENGTH = 64

# Fichiers : snake_case
ad_user_manager.py
```

### Structure d'une app PySide6
```
<app>/
├── main.py          # point d'entrée, QApplication
├── main_window.py   # fenêtre principale
├── widgets/         # widgets custom
├── services/        # logique métier (D-Bus calls)
├── models/          # modèles de données
└── tests/           # tests pytest
```

### Widgets PySide6
- Hériter de QWidget ou QDialog, jamais créer des widgets inline sans classe
- Signaux/slots : toujours nommer les slots avec le préfixe `_on_`
```python
self.btn_create.clicked.connect(self._on_create_clicked)

def _on_create_clicked(self) -> None:
    ...
```

### Thème
- Jamais de couleurs ou polices hardcodées dans les widgets
- Toujours utiliser `from core.theme import ThemeManager`
```python
# BIEN
label.setStyleSheet(ThemeManager.label_style())

# INTERDIT
label.setStyleSheet("color: #2a9d8f; font-size: 14px;")
```

## Gestion des erreurs
- Logger toujours les erreurs D-Bus avec le module `logging`
- Afficher les erreurs utilisateur via `QMessageBox` (jamais print)
- Pas de `except Exception` générique sans re-raise ou log

## Tests
- pytest uniquement
- Mocker les appels D-Bus avec `unittest.mock`
- Nommer les tests : `test_<ce_qui_est_testé>_<condition>`
