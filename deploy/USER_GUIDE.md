# Picking Entrepôt — Guide utilisateur

Application mobile-first pour le picking de commandes à partir d'un
**bon de livraison PDF**. Le PDF est le centre de l'expérience : le
préparateur tape directement sur chaque ligne pour valider chaque produit,
ligne par ligne, sans quitter le document.

## Écrans

### 1. Connexion (code opérateur)
Composez votre code sur le pavé numérique puis appuyez sur **OK**.

Codes par défaut : `1234`, `5678`, `0000`.

### 2. Liste des commandes
- **Rechercher** par n° de commande dans la barre du haut.
- **Nouvelle commande** → écran d'import.
- Appuyer sur une carte → ouvre la commande.
- Corbeille → suppression (confirmation demandée).

### 3. Import
- Sélectionner le **bon de livraison** PDF (obligatoire).
- Optionnellement, l'**étiquette Chronopost** PDF (elle sera automatiquement
  recadrée pour n'imprimer que l'étiquette utile).
- Appuyer sur **Créer la commande**. Le PDF est analysé (2-3 secondes)
  puis vous êtes redirigé vers la vue de picking.

### 4. Vue de picking
- Le PDF est affiché plein écran (rendu net via PDF.js).
- Chaque ligne produit est **une zone tactile**.
- **1 tap = 1 produit préparé**. Le badge affiche `1/5`, `2/5`… `5/5 ✓`.
- Ligne **partielle** → surlignée en **orange**.
- Ligne **terminée** → surlignée en **vert**, badge coche.
- **Appui long** sur une ligne = remise à zéro.
- **Barre du haut** = n° commande, produits validés (`X/Y`), % global.
  Progresse en direct via un remplissage vert/orange.

### 5. Étiquette Chronopost
- Depuis la vue de picking → bouton **Actions** → **Étiquette**.
- L'étiquette **recadrée** (marges blanches supprimées) s'affiche pour
  impression via le bouton **Imprimer** (ouvre la boîte système du
  navigateur - imprimante Bluetooth ou USB).

### 6. Impression
- Depuis n'importe quelle vue PDF : bouton **Imprimer** → dialogue système.

## Reprise / persistance

Toute la progression est sauvegardée automatiquement en base SQLite
côté serveur. Vous pouvez fermer / rouvrir la page, changer de téléphone,
la commande garde son état.

## Astuces

- L'application est conçue pour un usage **mobile / tactile avec gants**.
  Tous les boutons font ≥80 px de hauteur.
- Chrome, Edge, Safari (iOS), Android WebView : compatible.
- Ajoutez le site à l'écran d'accueil (PWA-like) pour une utilisation
  plein écran.
