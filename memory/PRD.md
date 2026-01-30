# L'Éclaireur - PRD (Product Requirements Document)

## Description
Outil d'aide pour les travailleurs québécois accidentés permettant d'analyser des documents CNESST/TAT avec anonymisation automatique.

## Créateur
Henri Albert Pertzing (accident le 31/12/2021) avec l'aide de E1 par Emergent.sh

## Architecture Technique
- **Frontend**: React.js avec Tailwind CSS
- **Backend**: FastAPI (Python)
- **Base de données**: MongoDB
- **IA**: Google Gemini 2.5 Flash via Emergent Universal Key

## Fonctionnalités Implémentées ✅

### Session 30/01/2026

#### Interface (Frontend)
- [x] Boutons Ko-fi sous crédit auteur (petites icônes) avec texte "pour améliorer l'appli"
- [x] Email direct pertzinghenrialbert@yahoo.ca (pas bouton "Me contacter")
- [x] Mention anti-haine "La haine et la violence ne seront jamais acceptées"
- [x] Flèches navigation haut/bas/témoignages à droite
- [x] Email répété en footer
- [x] Mode sombre (toggle en haut à droite)
- [x] Bouton imprimer dans page d'analyse

#### Mentions Légales (Popup)
- [x] Popup avant utilisation avec mentions complètes
- [x] Checkbox 1 (obligatoire): "Je comprends que ce rapport ne remplace pas un avis professionnel"
- [x] Checkbox 2 (optionnel): Consentement apprentissage IA anonymisé
- [x] Mentions: rapport uniquement pour TAT/CNESST/Avocats/Défenseur
- [x] Mention: aucune copie gardée par Henri Albert Pertzing
- [x] Mention: peut être déposé en "combiné défense"

#### Rapport d'Analyse Défense
- [x] Tableau récapitulatif systématique des contradictions EN FIN de rapport
- [x] Explications termes médicaux entre parenthèses systématiquement
- [x] Barème des indemnisations CNESST
- [x] Questions stratégiques pour audience TAT
- [x] Délais importants (30 jours CNESST, 45 jours TAT)

#### Anonymisation (2 niveaux)
- [x] Rapport final: masque NAS, RAMQ, Permis, Coordonnées bancaires
- [x] Rapport final: GARDE noms, téléphones, adresses
- [x] Version IA: anonymisation COMPLÈTE (si consentement)

#### Sécurité
- [x] Destruction sécurisée DOD 5220.22-M (3 passes)
- [x] Popup confirmation après téléchargement
- [x] Aucune copie conservée

#### Liens Officiels (Footer + Section médecins)
- [x] CNESST
- [x] TAT
- [x] Barreau du Québec (Trouver un avocat)
- [x] Aide juridique Québec
- [x] Collège des médecins (CMQ)
- [x] SOQUIJ
- [x] CMQ Décisions disciplinaires

#### Base de Données Médecins
- [x] Recherche par nom
- [x] % pro-employeur / pro-employé
- [x] Contributions utilisateurs
- [x] Lien vers CMQ décisions disciplinaires

### Fonctionnalités Existantes (Sessions précédentes)
- [x] Page d'accueil avec phare animé
- [x] Upload PDF (drag & drop, jusqu'à 100 Mo)
- [x] Analyse IA avec segmentation des gros documents
- [x] Téléchargement rapport (PDF, Word, TXT, HTML, RTF)
- [x] Base de données médecins avec statistiques
- [x] Contributions utilisateurs
- [x] Témoignages
- [x] Compteur de visiteurs
- [x] Partage social (Facebook, X, LinkedIn, WhatsApp)
- [x] Bouton Ko-fi

## Backlog / Non implémenté

### P0 (Haute priorité)
- [ ] PayPal (à venir selon Henri)
- [ ] Stripe (à venir selon Henri)

### P1 (Moyenne priorité)
- [ ] Traduction anglais

### P2 (Basse priorité)
- [ ] QR Code dans PDF (complexe)

### Refusé
- [x] Historique des analyses (NON - aucune copie gardée)
- [x] Mise à jour automatique mensuelle des liens (trop complexe)
- [x] Liens actifs dans PDF téléchargé (limitation jsPDF)

## Personas Utilisateurs
1. **Travailleur accidenté**: Comprendre son dossier, préparer sa défense
2. **Avocat spécialisé**: Synthétiser rapidement des dossiers volumineux
3. **Représentant syndical**: Aider les membres avec leurs dossiers

## Contact
pertzinghenrialbert@yahoo.ca

---
*Dernière mise à jour: 30/01/2026*
