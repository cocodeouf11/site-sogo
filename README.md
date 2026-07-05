# Picking Entrepôt

Application web de picking d'entrepôt : import de bon de livraison PDF,
détection automatique des lignes produit, validation tactile ligne par
ligne, recadrage automatique d'étiquettes Chronopost, historique
persistant. Conçue **Mobile First** pour un usage quotidien avec gants.

- **Frontend** : React 19 + TailwindCSS + PDF.js
- **Backend** : FastAPI (Python 3.12) + SQLite (aiosqlite) + PyMuPDF
- **Deploy** : Docker Compose sur Debian 12

Voir :
- [`deploy/README.md`](deploy/README.md) — installation Debian 12 avec Docker
- [`deploy/USER_GUIDE.md`](deploy/USER_GUIDE.md) — guide utilisateur

## Codes opérateurs par défaut
`1234` · `5678` · `0000`

## Architecture

```
/app
├── backend/               # FastAPI + SQLite + PyMuPDF
│   ├── server.py          # API HTTP (/api/*)
│   ├── database.py        # Init SQLite + tables
│   ├── pdf_parser.py      # Analyse du bon de livraison (bbox par ligne)
│   ├── chronopost_cropper.py  # Recadrage étiquette
│   └── storage/           # data.db + PDFs uploadés (persistant)
├── frontend/              # React SPA
│   └── src/
│       ├── components/    # Numpad, PdfViewer, UploadZone
│       ├── pages/         # Login, Orders, OrderView, UploadPage, LabelPrint
│       └── lib/           # api.js, auth.jsx
└── deploy/                # Dockerfile, docker-compose.yml, nginx.conf, docs
```

## API principale

| Method | Endpoint | Description |
|-------|----------|-------------|
| POST  | `/api/auth/login` | `{ code }` → `{ operator, token }` |
| GET   | `/api/orders?q=` | liste (recherche par n°) |
| POST  | `/api/orders` | multipart : `delivery` + `label` optionnel |
| GET   | `/api/orders/{id}` | détails + lignes + bboxes |
| DELETE| `/api/orders/{id}` | supprime commande + fichiers |
| POST  | `/api/orders/{id}/lines/{line_id}/increment` | `{delta: 1 | -1}` |
| POST  | `/api/orders/{id}/lines/{line_id}/reset` | remet la ligne à 0 |
| GET   | `/api/orders/{id}/pdf` | fichier PDF bon de livraison |
| GET   | `/api/orders/{id}/label?cropped=true` | étiquette recadrée |
