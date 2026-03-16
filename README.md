# ERPNext Docker Multi-Client (Dev, sans image `frappe/erpnext`)

Ce setup multi-client est orienté développement et n'utilise pas l'image Docker Hub `frappe/erpnext`.

Principe:
- image locale buildée depuis ce repo (`Dockerfile`)
- code `frappe`/`erpnext` cloné en Git dans `clients/<client>/data/apps`
- stack compose explicite (backend, websocket, workers, scheduler, db, redis)

## Structure

- `./client` : CLI Bash
- `./Dockerfile` : image dev locale Frappe (bench)
- `clients/<nom>/` : environnement client (`.env`, `docker-compose.yml`, `data/*`)
- `templates/docker-compose.client.yml` : template compose

## Prérequis

- Docker + plugin Docker Compose (`docker compose`)
- Git
- Bash

## Démarrage rapide

```bash
# 1) Créer un client (branche Frappe/ERPNext)
#    -> clone apps, build, up, mapping hosts, create site automatiquement
./client create acme version-15 8080 acme.local

# 2) URL
./client url acme
```

## Commandes

```bash
./client list
./client create <client> [frappe_branch] [http_port] [site_name]
./client host-map <client>
./client up <client>
./client down <client>
./client delete <client>
./client restart <client>
./client status [client]
./client logs <client> [service]
./client shell <client>
./client site-create <client>
./client restore <client> <backup_sql_gz> [site_name]
./client app-list <client>
./client app-get <client> <repo_url> [branch]
./client app-install <client> <app_name>
./client app-get-install <client> <repo_url> [branch] [app_name]
./client bench-update <client> [bench_update_args...]
./client fix-perms <client>
./client url <client>
```

## Notes

- `version-15` / `v15` / `15` sont normalisés vers `version-15` pour le clone Git.
- `./client create` démarre automatiquement la stack et initialise le site ERPNext.
- `./client up <client>` fait le build/démarrage sans recréer le site (utiliser `site-create` si besoin).
- `./client bench-update <client>` force par défaut `--reset --no-backup` (sauf si déjà fournis).
- Le script attend la disponibilité du backend et affiche la progression pendant le démarrage.
- Le backend est exposé directement sur `http://localhost:<port>`.
