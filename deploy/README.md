# Installation Debian 12 — Picking Entrepôt

Application web de picking pour préparation de commandes en entrepôt.
Frontend React + Backend FastAPI + SQLite. Déployé via Docker Compose.

> Note pour la stack : le préparateur initial a demandé **Node.js/Express** mais
> l'environnement de développement Emergent exige Python/uvicorn. Le backend
> livré est écrit en **Python 3.12 + FastAPI** avec **SQLite** — même comportement,
> même schéma d'API, prêt à déployer via Docker sur Debian 12.

---

## 1. Prérequis sur Debian 12

```bash
# Installer Docker + Compose (rootful)
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# (optionnel) ne pas préfixer par sudo :
sudo usermod -aG docker $USER && newgrp docker
```

## 2. Récupération du code

```bash
git clone <votre-repo> picking && cd picking
```

## 3. Démarrage

Depuis la racine du projet :

```bash
cd deploy
# Port exposé par défaut : 8080
WEB_PORT=8080 docker compose up -d --build
```

L'application est ensuite disponible sur `http://<ip-serveur>:8080`.

## 4. HTTPS (recommandé pour usage mobile)

Il est fortement conseillé de placer un reverse-proxy TLS (Caddy ou Traefik) devant :

**Exemple Caddyfile :**
```
picking.exemple.fr {
    reverse_proxy 127.0.0.1:8080
}
```

## 5. Persistance

- **SQLite DB + PDFs** sont stockés dans le volume nommé `picking-data`.
- Pour sauvegarder : `docker run --rm -v picking-data:/data -v $(pwd):/backup alpine tar czf /backup/picking-backup.tgz -C /data .`
- Pour restaurer : `docker run --rm -v picking-data:/data -v $(pwd):/backup alpine tar xzf /backup/picking-backup.tgz -C /data`

## 6. Mise à jour

```bash
git pull && docker compose up -d --build
```

## 7. Logs

```bash
docker compose logs -f            # tout
docker compose logs -f backend    # backend seulement
```

## 8. Codes opérateurs par défaut

Trois opérateurs sont créés au premier démarrage :

| Code   | Nom              |
|--------|------------------|
| 1234   | Préparateur 1    |
| 5678   | Préparateur 2    |
| 0000   | Admin            |

Vous pouvez en ajouter directement en base :

```bash
docker compose exec backend python -c "
import asyncio, aiosqlite
async def add(code, name):
    async with aiosqlite.connect('/app/storage/data.db') as db:
        await db.execute('INSERT INTO operators (code, name) VALUES (?, ?)', (code, name))
        await db.commit()
asyncio.run(add('9999', 'Chef d\\\'équipe'))
"
```

## 9. Sécurité minimale (checklist)

- [x] Fichiers uploadés limités à **PDF** (extension + content-type)
- [x] Taille max **25 Mo** par PDF
- [x] Erreurs de parsing capturées → HTTP 400
- [x] Injection SQL impossible (paramètres liés)
- [x] Auth : header `X-Operator-Code` requis pour créer/supprimer
- [ ] **À ajouter en production** : reverse-proxy TLS + fail2ban + backups automatiques

## 10. Arrêt / suppression

```bash
docker compose down          # arrêt (données conservées)
docker compose down -v       # arrêt + suppression du volume (RESET total)
```
