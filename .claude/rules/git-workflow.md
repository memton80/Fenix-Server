# Git Workflow — Fenix Server

## Branches
```
main          → code stable uniquement
dev           → branche de travail principale
feature/<nom> → nouvelle fonctionnalité
fix/<nom>     → correction de bug
```

## Commits — format
```
<type>(<scope>): <description courte>

Types : feat | fix | refactor | docs | test | chore
Scope : core | server-manager | ad-manager | update-manager | bootstrap

Exemples :
feat(ad-manager): ajouter la création d'utilisateur via LDAP
fix(core): corriger le timeout de connexion D-Bus
docs(architecture): mettre à jour le schéma D-Bus
```

## Règles
- Un commit = une chose logique
- Pas de "WIP" ou "fix stuff" dans les messages
- Toujours tester avant de commit sur `main`
- Les fichiers `.env` et `CLAUDE.local.md` ne sont jamais commités (.gitignore)

## .gitignore minimum
```
__pycache__/
*.pyc
.env
CLAUDE.local.md
*.egg-info/
dist/
.pytest_cache/
```
