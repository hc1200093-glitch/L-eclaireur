# L'Éclaireur - PRD

## Problem Statement
Application d'aide pour les travailleurs québécois permettant d'analyser des documents PDF (CNESST, TAT, rapports médicaux) avec anonymisation automatique des données sensibles.

## Architecture
- **Frontend**: React.js avec drag & drop PDF upload
- **Backend**: FastAPI avec intégration Google Gemini
- **Database**: MongoDB pour stocker l'historique des analyses
- **LLM**: Google Gemini 2.5 Flash via Emergent Universal Key

## User Personas
- Travailleurs québécois ayant subi un accident de travail
- Personnes devant comprendre des décisions CNESST/TAT
- Utilisateurs cherchant à anonymiser leurs documents

## Core Requirements
- [x] Upload de fichiers PDF (jusqu'à 60 Mo)
- [x] Analyse automatique via Gemini
- [x] Anonymisation des données sensibles (NAS, adresses, noms, téléphones)
- [x] Liens vers ressources (CNESST, TAT, avocats, Collège des médecins)
- [x] Note de sécurité DOD 5220.22-M

## What's Been Implemented (2026-01-27)
- Backend API /api/analyze pour analyse PDF
- Frontend avec zone drag & drop
- Intégration Gemini avec Emergent Universal Key
- Anonymisation automatique des données sensibles
- Design fidèle aux captures d'écran originales

## Prioritized Backlog
- P0: ✅ Fonctionnalité d'analyse PDF
- P1: Page d'accueil avec présentation de l'outil
- P1: Historique des analyses
- P2: Export PDF du rapport d'analyse
- P2: Multi-langue (anglais)

## Next Tasks
- Ajouter une page d'accueil
- Implémenter l'historique des analyses avec liste consultable
- Permettre la suppression des analyses
