# ERPNext Docker Multi-Client

Projet pour créer et gérer des environnements Docker ERPNext/Frappe par client via un client Bash, sur le même modèle d'exploitation que tes stacks `~/Dev/*-docker`.

## Structure

- `./client` : CLI Bash principale
- `clients/<nom>/` : environnement d'un client (`.env`, `docker-compose.yml`, données persistantes dont `data/apps`)
- `templates/docker-compose.client.yml` : template compose ERPNext/Frappe

## Prérequis

- Docker + Docker Compose plugin (`docker compose`)
- Bash

## Démarrage rapide

```bash
# 1) Créer un client
./client create acme v16.5.0 8080 acme.local

# 2) Démarrer les services
./client up acme

# 3) Créer le site ERPNext (première fois)
./client site-create acme

# 4) Ouvrir ERPNext
./client url acme
```

## Commandes

```bash
./client list
./client create <client> [erpnext_version] [http_port] [site_name]
./client up <client>
./client down <client>
./client restart <client>
./client status [client]
./client logs <client> [service]
./client shell <client>
./client site-create <client>
./client app-list <client>
./client app-get <client> <repo_url> [branch]
./client app-install <client> <app_name>
./client app-get-install <client> <repo_url> [branch] [app_name]
./client restore <client> <dump.sql|dump.sql.gz> [db_name]
./client url <client>
```

## Installation d'apps

```bash
# Lister apps disponibles dans le bench + apps installées sur le site
./client app-list acme

# Récupérer une app custom depuis Git
./client app-get acme https://github.com/frappe/hrms.git version-16

# Repo SSH privé: le clone est fait sur l'hôte puis copié dans le conteneur
./client app-get acme git@github.com:my-org/my-private-app.git version-16

# Installer une app déjà présente dans le bench
./client app-install acme hrms

# Récupérer + installer en une commande
./client app-get-install acme https://github.com/frappe/payments.git version-16 payments
```

## Restauration BDD

```bash
# Restaure dans la DB du site (détectée via site_config.json)
./client restore acme /path/to/dump.sql

# Dump compressé
./client restore acme /path/to/dump.sql.gz

# Forcer une base cible spécifique
./client restore acme /path/to/dump.sql.gz acme_db
```

Note: si le dump référence des apps non présentes dans `data/apps`, la commande échoue explicitement avec la liste des apps à installer (pour éviter une erreur 500 silencieuse).

## Notes d'exploitation

- Chaque client est isolé avec son propre projet compose, sa base MariaDB, Redis et volumes.
- Le dossier des apps est exposé sur l'hôte dans `clients/<client>/data/apps`.
- Les apps de base (`frappe`, `erpnext`) sont automatiquement seedées depuis l'image au create/up/site-create si `data/apps` est vide.
- Le port HTTP est exposé en local (`localhost:<port>`).
- Si le port n'est pas fourni à la création, le script prend automatiquement le prochain port libre à partir de `8080`.
- Les mots de passe admin/db sont générés automatiquement dans `clients/<client>/.env`.
