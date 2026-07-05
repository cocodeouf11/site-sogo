# PRD — Warehouse Order Picking App

## Original problem statement
Application web complète pour gérer le picking de commandes en entrepôt.
L'utilisateur importe un bon de livraison PDF (SOGO TECH FRANCE, cmd n°56747
en exemple, 173+ lignes) et une étiquette Chronopost. Le PDF est affiché
tel quel via PDF.js. Chaque ligne devient tactile : le préparateur tape 1×
par produit (0/5 → 1/5 → … → 5/5 ✓). Barre de progression en haut.
Historique, recherche, suppression, reprise après reload. Étiquette
Chronopost recadrée automatiquement pour impression. Mobile-first,
grosses zones tactiles pour usage avec gants. Debian 12 + Docker Compose.

## User personas
- Préparateur de commandes en entrepôt SOGO TECH, gants, téléphone à
  une main. Objectif : ne JAMAIS quitter le PDF.

## Core requirements
- PDF.js pour affichage sans transformation visuelle
- Détection automatique de lignes (PyMuPDF : nom produit / réf / emplacement
  Étagère/Colonne/Tiroir/Bac / quantité) + bbox normalisé
- Overlay cliquable synchronisé sur le PDF (états : todo / partiel / terminé)
- Persistance SQLite + reprise à chaud
- Historique + recherche + suppression
- Recadrage automatique étiquette Chronopost (marges blanches supprimées)
- Login par code opérateur simple (numpad tactile)
- Interface Mobile First : boutons ≥80 px, IBM Plex Sans, neo-brutalist
- Compatibilité Android + iPhone + Chrome + Edge
- Déploiement Docker Compose Debian 12

## Stack choisie
- Backend : FastAPI (Python) + SQLite (aiosqlite) + PyMuPDF + pdfplumber
- Frontend : React 19 + TailwindCSS + PDF.js (pdfjs-dist@4.10.38) + lucide-react
- Auth : header `X-Operator-Code` — 3 opérateurs seedés

## What's been implemented (2026-02-05)
- ✅ SQLite schema (operators, orders, order_lines) + init/seed
- ✅ PDF parsing SOGO TECH format — 180 lignes détectées sur bon 56747
- ✅ Chronopost auto-crop (union bbox drawings + text)
- ✅ REST API complète (auth, upload, list, get, delete, increment, reset, PDF, label)
- ✅ Login numpad avec 3 codes seedés
- ✅ Liste commandes + recherche + suppression + barre progression par carte
- ✅ Upload PDFs avec drag&drop + progression
- ✅ Vue picking : PDF.js multi-page + overlay tactile synchronisé
- ✅ Header progression sticky (cmd #, X/Y, %, remplissage visuel)
- ✅ Écran étiquette Chronopost recadrée + impression
- ✅ Appui long = reset ligne
- ✅ Docker Compose (nginx + backend + volume persistant)
- ✅ Documentation utilisateur et install Debian 12

## Deferred / next tasks (P1/P2)
- P1 : Mode "focus" ligne active (jump to next todo line)
- P1 : Statistiques journalières (nb commandes préparées, produits/heure)
- P1 : Export PDF annoté (avec les surbrillances vert/orange)
- P2 : PWA (installable + offline resume)
- P2 : Multi-tenant (opérateurs assignés à des zones)
- P2 : Version Node.js/Express du backend (si le client insiste malgré
  la parité fonctionnelle avec FastAPI)

## Files of note
- `/app/backend/server.py` — FastAPI routes
- `/app/backend/pdf_parser.py` — détection lignes SOGO TECH (double-row layout)
- `/app/backend/chronopost_cropper.py` — recadrage étiquette
- `/app/frontend/src/components/PdfViewer.jsx` — canvas + overlay tactile
- `/app/frontend/src/pages/OrderView.jsx` — écran principal picking
- `/app/deploy/` — Docker Compose Debian 12
