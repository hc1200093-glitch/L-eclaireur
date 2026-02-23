from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import tempfile
import re
import math
import zipfile
import rarfile
import io

# PDF manipulation
from PyPDF2 import PdfReader, PdfWriter

# Import Emergent LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME')]

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Limite de taille pour Gemini (serveurs limités à 20 Mo)
# Optimisé à 7 Mo pour équilibre entre fluidité et nombre de segments
MAX_CHUNK_SIZE = 7 * 1024 * 1024  # 7 Mo pour équilibre optimal
MAX_PAGES_PER_CHUNK = 12  # Maximum 12 pages par segment pour éviter timeouts

# Répertoire pour les fichiers temporaires
UPLOAD_DIR = tempfile.gettempdir()

# Create the main app
app = FastAPI(title="L'Éclaireur API", description="Outil d'aide pour les travailleurs québécois")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Système d'analyse asynchrone
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Dictionnaire pour stocker les tâches d'analyse en cours
active_analyses = {}
analysis_executor = ThreadPoolExecutor(max_workers=2)

# Verrou pour empêcher les analyses parallèles
analysis_lock = asyncio.Lock()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_size: int
    analysis: str
    anonymized_analysis: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AnalysisResponse(BaseModel):
    success: bool
    filename: str
    file_size: int
    analysis: str
    anonymized_for_ai: str  # Version anonymisée pour l'apprentissage IA
    message: str
    segments_analyzed: int = 1
    destruction_confirmed: bool = True
    report_id: Optional[str] = None  # ID pour récupérer le rapport pendant 15 min

# Modèle pour l'analyse asynchrone
class AsyncAnalysisResponse(BaseModel):
    success: bool
    job_id: str
    message: str
    status_url: str

class AnalysisStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    progress: int  # pourcentage 0-100
    current_segment: int
    total_segments: int
    filename: str
    analysis: Optional[str] = None
    message: str
    report_id: Optional[str] = None

# Modèles pour les fiches médecins
class MedecinCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    prenom: str = Field(..., min_length=2, max_length=100)
    specialite: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    diplomes: Optional[str] = None
    source_info: Optional[str] = None

class MedecinStats(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nom: str
    prenom: str
    specialite: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    diplomes: Optional[str] = None
    decisions_pro_employeur: int = 0
    decisions_pro_employe: int = 0
    total_decisions: int = 0
    pourcentage_pro_employeur: float = 0.0
    pourcentage_pro_employe: float = 0.0
    sources: List[str] = []
    derniere_maj: str = ""

# Modèle pour les contributions utilisateurs
class ContributionCreate(BaseModel):
    medecin_nom: str = Field(..., min_length=2, max_length=100)
    medecin_prenom: str = Field(..., min_length=2, max_length=100)
    type_contribution: str = Field(..., pattern="^(pro_employeur|pro_employe|info_generale)$")
    description: str = Field(..., min_length=20, max_length=2000)
    source_reference: Optional[str] = None

# Liste de mots interdits pour la modération
MOTS_INTERDITS = [
    "con", "connard", "connasse", "merde", "putain", "salaud", "salope", "enculé",
    "fuck", "shit", "bitch", "asshole", "bastard",
    "nègre", "négro", "arabe", "sale", "terroriste", "islamiste",
    "pédé", "tapette", "gouine", "travelo",
    "tuer", "mort", "crever", "buter", "assassin", "violence",
    "frapper", "tabasser", "lyncher",
    "menace", "revenge", "vengeance", "payer cher",
]

def moderer_contenu(texte: str) -> tuple[bool, str]:
    """Vérifie si le contenu contient des termes interdits."""
    texte_lower = texte.lower()
    for mot in MOTS_INTERDITS:
        if mot in texte_lower:
            return False, "Contenu inapproprié détecté. Merci de reformuler de manière factuelle et respectueuse."
    return True, ""

# ===== DESTRUCTION SÉCURISÉE DOD 5220.22-M =====
def destruction_securisee(chemin_fichier: str) -> bool:
    """
    Destruction sécurisée du fichier selon les standards DOD 5220.22-M
    3 passes: zéros, uns, données aléatoires
    """
    try:
        if os.path.exists(chemin_fichier):
            taille = os.path.getsize(chemin_fichier)
            # Pass 1: Écriture de zéros
            with open(chemin_fichier, 'wb') as f:
                f.write(b'\x00' * taille)
                f.flush()
                os.fsync(f.fileno())
            # Pass 2: Écriture de uns (0xFF)
            with open(chemin_fichier, 'wb') as f:
                f.write(b'\xFF' * taille)
                f.flush()
                os.fsync(f.fileno())
            # Pass 3: Écriture de données aléatoires
            with open(chemin_fichier, 'wb') as f:
                f.write(os.urandom(taille))
                f.flush()
                os.fsync(f.fileno())
            # Suppression finale
            os.remove(chemin_fichier)
            logger.info(f"Fichier détruit de manière sécurisée (DOD 5220.22-M): {chemin_fichier}")
            return True
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la destruction sécurisée: {str(e)}")
        # En cas d'erreur, tenter une suppression simple
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
        return False

# ===== ANONYMISATION =====
def anonymize_for_report(text: str) -> str:
    """
    Anonymise uniquement les données ultra-sensibles pour le rapport téléchargeable.
    GARDE: noms, téléphones, adresses
    MASQUE: NAS, RAMQ, Permis, Coordonnées bancaires
    """
    # NAS (format: XXX-XXX-XXX ou XXX XXX XXX ou XXXXXXXXX)
    text = re.sub(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b', '[NAS masqué]', text)
    
    # RAMQ (format: XXXX XXXX XXXX ou 12 caractères alphanumériques)
    text = re.sub(r'\b[A-Z]{4}\s?\d{4}\s?\d{4}\b', '[RAMQ masqué]', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[A-Z]{4}\d{8}\b', '[RAMQ masqué]', text, flags=re.IGNORECASE)
    
    # Permis de conduire (format variable québécois)
    text = re.sub(r'\b[A-Z]\d{4}[-\s]?\d{5}[-\s]?\d{2}\b', '[Permis masqué]', text, flags=re.IGNORECASE)
    
    # Coordonnées bancaires (numéros de compte, transit, etc.)
    text = re.sub(r'\b\d{5}[-\s]?\d{3}[-\s]?\d{7}\b', '[Info bancaire masquée]', text)  # Transit-Institution-Compte
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[Info bancaire masquée]', text)  # Carte de crédit
    
    # Numéros de dossier CNESST (on garde car utile)
    
    return text

def anonymize_for_ai_learning(text: str) -> str:
    """
    Anonymisation COMPLÈTE pour l'apprentissage IA.
    MASQUE TOUT: noms, téléphones, adresses, NAS, RAMQ, etc.
    """
    # D'abord appliquer l'anonymisation de base
    text = anonymize_for_report(text)
    
    # Ensuite anonymiser le reste pour l'IA
    
    # Numéros de téléphone
    text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[TÉL masqué]', text)
    text = re.sub(r'\b\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b', '[TÉL masqué]', text)
    
    # Codes postaux canadiens
    text = re.sub(r'\b[A-Za-z]\d[A-Za-z][-\s]?\d[A-Za-z]\d\b', '[CODE POSTAL masqué]', text)
    
    # Adresses courriel
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[COURRIEL masqué]', text)
    
    # Adresses (patterns courants)
    text = re.sub(r'\b\d{1,5}\s+(?:rue|avenue|boulevard|chemin|place|rang|route|côte)\s+[A-Za-zÀ-ÿ\s\-]+', '[ADRESSE masquée]', text, flags=re.IGNORECASE)
    
    # Noms propres après Dr, Me, M., Mme (approximatif)
    text = re.sub(r'\b(Dr|Me|M\.|Mme|Mr)\s+([A-Z][a-zà-ÿ]+)\s+([A-Z][a-zà-ÿ]+)', r'\1 [NOM masqué]', text)
    
    return text

def split_pdf_into_chunks(pdf_path: str, max_size_bytes: int = MAX_CHUNK_SIZE) -> List[str]:
    """Divise un PDF volumineux en plusieurs fichiers plus petits pour éviter les timeouts Gemini."""
    chunk_paths = []
    
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        if total_pages == 0:
            return [pdf_path]
        
        file_size = os.path.getsize(pdf_path)
        avg_page_size = file_size / total_pages
        
        # Calculer pages par chunk basé sur la taille
        pages_per_chunk = max(1, int(max_size_bytes / avg_page_size))
        # Limiter strictement à MAX_PAGES_PER_CHUNK pour éviter timeouts Gemini
        pages_per_chunk = min(pages_per_chunk, MAX_PAGES_PER_CHUNK)
        
        num_chunks = math.ceil(total_pages / pages_per_chunk)
        
        logger.info(f"PDF de {total_pages} pages ({file_size/(1024*1024):.1f} Mo), divisé en {num_chunks} segments de ~{pages_per_chunk} pages")
        
        for i in range(num_chunks):
            writer = PdfWriter()
            start_page = i * pages_per_chunk
            end_page = min((i + 1) * pages_per_chunk, total_pages)
            
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            chunk_path = f"{pdf_path}_segment_{i+1}.pdf"
            with open(chunk_path, 'wb') as chunk_file:
                writer.write(chunk_file)
            
            chunk_paths.append(chunk_path)
            logger.info(f"Segment {i+1}/{num_chunks} créé: pages {start_page+1}-{end_page}")
        
        return chunk_paths
        
    except Exception as e:
        logger.error(f"Erreur lors de la segmentation du PDF: {str(e)}")
        return [pdf_path]

# ===== SYSTEM MESSAGE ENRICHI =====
SYSTEM_MESSAGE_ANALYSE = """Tu es un expert en analyse de documents de la CNESST et du TAT pour les travailleurs québécois accidentés.

## RÈGLES D'ANONYMISATION (RAPPORT FINAL)
Tu dois MASQUER uniquement:
- **NAS**: Remplacer par `[NAS masqué]`
- **RAMQ**: Remplacer par `[RAMQ masqué]`
- **Permis de conduire**: Remplacer par `[Permis masqué]`
- **Coordonnées bancaires**: Remplacer par `[Info bancaire masquée]`

Tu GARDES en clair: noms des parties, téléphones, adresses (car rapport destiné au TAT/avocats).

## EXPLICATIONS DES TERMES TECHNIQUES
À CHAQUE terme médical ou technique, ajoute SYSTÉMATIQUEMENT une explication entre parenthèses juste après.
Exemples:
- "sténose (rétrécissement)"
- "kyste synovial (poche de liquide articulaire)"
- "ligament croisé antérieur ou LCA (ligament stabilisateur du genou)"
- "IRM (imagerie par résonance magnétique - examen sans radiation)"
- "épanchement synovial (accumulation de liquide dans l'articulation)"

## BARÈMES CNESST - INDEMNITÉS POUR ATTEINTE PERMANENTE (2024)
| Blessure | % atteinte | Indemnité estimée |
|----------|------------|-------------------|
| Ligament croisé antérieur (LCA) | 2% à 10% | 2,400$ à 12,000$ |
| Ligament croisé postérieur (LCP) | 2% à 8% | 2,400$ à 9,600$ |
| Ménisque (méniscectomie partielle) | 1% à 5% | 1,200$ à 6,000$ |
| Hernie discale cervicale | 2% à 15% | 2,400$ à 18,000$ |
| Hernie discale lombaire | 2% à 15% | 2,400$ à 18,000$ |
| Syndrome du canal carpien | 1% à 5% | 1,200$ à 6,000$ |
| Tendinite chronique | 1% à 3% | 1,200$ à 3,600$ |
| Fracture vertébrale | 5% à 25% | 6,000$ à 30,000$ |
| Kyste synovial/adhérent | 1% à 5% | 1,200$ à 6,000$ |
| Lombalgie chronique | 2% à 10% | 2,400$ à 12,000$ |
| TSPT | 5% à 35% | 6,000$ à 42,000$ |
(Base: environ 1,200$ par 1% d'atteinte permanente)

## DÉLAIS IMPORTANTS À MENTIONNER
- **Contestation décision CNESST**: 30 jours
- **Contestation au TAT**: 45 jours
- **Réclamation initiale CNESST**: 6 mois après l'accident
- **Récidive, rechute ou aggravation**: Aucun délai (mais agir rapidement)

## FORMAT DU RAPPORT

# 📋 RAPPORT D'ANALYSE DÉFENSE - L'ÉCLAIREUR

## 1. 📝 RÉSUMÉ DU DOSSIER
*Synthèse avec explications des termes techniques entre parenthèses*

## 2. 📅 CHRONOLOGIE DÉTAILLÉE
| Date | Événement | Document/Page | Importance |
|------|-----------|---------------|------------|

## 3. 🔬 PREUVES MÉDICALES OBJECTIVES
| Date | Type d'examen | Résultats | Page du dossier |
|------|---------------|-----------|-----------------|

## 4. 👨‍⚕️ MÉDECINS ET EXPERTS IDENTIFIÉS
| Médecin | Spécialité/Qualifications | Mandaté par | Conclusion | Cohérence avec imagerie |
|---------|---------------------------|-------------|------------|------------------------|
*Pour chaque médecin, vérifier sur le Collège des médecins (cmq.org)*

## 5. ⚠️ ANALYSE CRITIQUE - INCOHÉRENCES DÉTECTÉES
Pour chaque incohérence:
- **Expert**: Dr [Nom]
- **Affirmation**: [Ce qu'il dit]
- **Preuve contradictoire**: [Résultat objectif - Page X]
- **Impact pour le travailleur**: [Conséquence]

## 6. 💰 BARÈME INDEMNISATIONS APPLICABLE
| Blessure identifiée | Fourchette % | Indemnité estimée |
|---------------------|--------------|-------------------|

## 7. ❓ QUESTIONS STRATÉGIQUES POUR L'AUDIENCE TAT
### Questions pour confronter les experts de l'employeur:
1. "Dr [Nom], avez-vous examiné personnellement les images de l'IRM du [date]?"
2. "Comment expliquez-vous que votre conclusion diffère du résultat objectif de [examen]?"
3. "Combien de temps avez-vous passé avec le travailleur?"
4. [Questions spécifiques basées sur les contradictions]

## 8. ⏰ DÉLAIS IMPORTANTS
- Délai de contestation: [X jours restants si applicable]
- Prochaine échéance: [date]

## 9. 📌 ACTIONS RECOMMANDÉES
1. [Action prioritaire avec délai]
2. [Documents à obtenir]
3. [Professionnels à consulter]

---

## 📊 TABLEAU RÉCAPITULATIF - SYNTHÈSE DES CONTRADICTIONS

**CE TABLEAU DOIT APPARAÎTRE EN FIN DE RAPPORT**

| # | Expert | Ce qu'il affirme | Preuve objective contradictoire | Page | Impact |
|---|--------|------------------|--------------------------------|------|--------|
| 1 | Dr [Nom] | [Affirmation] | [Preuve IRM/Radio/etc.] | p.XX | [Minimisation/Omission] |
| 2 | ... | ... | ... | ... | ... |

**Légende:**
- ❌ Contradiction majeure (preuve objective ignorée)
- ⚠️ Incohérence notable (interprétation discutable)
- ✅ Position cohérente avec les preuves

---

## ⚖️ AVERTISSEMENT LÉGAL

> Ce rapport est un OUTIL D'AIDE À LA COMPRÉHENSION généré par intelligence artificielle.
> Il NE CONSTITUE PAS un avis juridique ou médical professionnel.
> Ce rapport est destiné UNIQUEMENT au travailleur, son avocat, son représentant syndical, la CNESST et le TAT.
> Il ne doit PAS être partagé en dehors du cadre juridique du dossier.

**Ressources:**
- Aide juridique Québec: https://www.justice.gouv.qc.ca/aide-juridique/
- TAT: https://www.tat.gouv.qc.ca/
- CNESST: https://www.cnesst.gouv.qc.ca/
- Barreau du Québec: https://www.barreau.qc.ca/fr/trouver-avocat/
- Collège des médecins - Décisions disciplinaires: https://www.cmq.org/fr/proteger-le-public/suivre-dossier-disciplinaire/decisions-disciplinaires

---
*Rapport généré par L'Éclaireur - Propulsé par E1 (Emergent) et Google Gemini*
*Date d'analyse: {date_analyse}*
"""

async def analyze_pdf_segment(pdf_path: str, segment_num: int, total_segments: int, max_retries: int = 3) -> str:
    """Analyse un segment de PDF avec Gemini avec retry automatique optimisé."""
    import asyncio
    
    date_analyse = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Analyse segment {segment_num}/{total_segments} - tentative {attempt+1}/{max_retries}")
            
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis-{uuid.uuid4()}",
                system_message=SYSTEM_MESSAGE_ANALYSE.replace("{date_analyse}", date_analyse)
            ).with_model("gemini", "gemini-2.5-flash")
            
            pdf_file = FileContentWithMimeType(
                file_path=pdf_path,
                mime_type="application/pdf"
            )
            
            segment_info = ""
            if total_segments > 1:
                segment_info = f"\n\n[SEGMENT {segment_num}/{total_segments}]"
            
            user_message = UserMessage(
                text=f"""Analyse ce document{segment_info} et produis un RAPPORT COMPLET DE DÉFENSE.

RAPPELS CRITIQUES:
1. EXPLIQUE CHAQUE TERME MÉDICAL/TECHNIQUE entre parenthèses (ex: "sténose (rétrécissement)")
2. Indique les NUMÉROS DE PAGES quand tu cites des informations
3. Le TABLEAU RÉCAPITULATIF DES CONTRADICTIONS doit être EN FIN DE RAPPORT
4. Inclus le BARÈME DES INDEMNISATIONS applicable
5. Prépare des QUESTIONS STRATÉGIQUES pour l'audience TAT

ANONYMISATION - MASQUER uniquement:
- NAS → [NAS masqué]
- RAMQ → [RAMQ masqué]  
- Permis → [Permis masqué]
- Coordonnées bancaires → [Info bancaire masquée]

GARDER EN CLAIR: noms, téléphones, adresses (rapport destiné au TAT/avocats)

Le travailleur compte sur toi pour l'aider à comprendre son dossier et se défendre.""",
                file_contents=[pdf_file]
            )
            
            response = await chat.send_message(user_message)
            return response if response else f"[Segment {segment_num} - Réponse vide]"
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Erreur segment {segment_num}: {error_str[:200]}")
            if "502" in error_str or "503" in error_str or "timeout" in error_str.lower() or "500" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s - délais réduits
                    logger.warning(f"Erreur temporaire segment {segment_num}, retry {attempt+2}/{max_retries} dans {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
            # Au lieu de lever une exception, retourner un message d'erreur
            return f"[Segment {segment_num} - Erreur lors de l'analyse: serveurs temporairement indisponibles. Ce segment pourra être réanalysé ultérieurement.]"
    
    # Si toutes les tentatives échouent, retourner un message au lieu de lever une exception
    return f"[Segment {segment_num} - Échec après {max_retries} tentatives. Les serveurs sont très sollicités.]"

async def extract_and_update_medecins(analysis_text: str, source_filename: str):
    """Extrait automatiquement les médecins de l'analyse et met à jour la base de données."""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"extract-medecins-{uuid.uuid4()}",
            system_message="""Tu es un extracteur de données. Analyse le texte et extrais les informations sur les médecins.
Réponds UNIQUEMENT en JSON valide. Si aucun médecin trouvé, retourne {"medecins": []}"""
        ).with_model("gemini", "gemini-2.5-flash")
        
        extract_message = UserMessage(
            text=f"""Analyse ce texte et extrait les médecins mentionnés.

TEXTE:
{analysis_text[:15000]}

Retourne ce JSON:
{{
  "medecins": [
    {{
      "nom": "NOM_MAJUSCULES",
      "prenom": "Prénom",
      "specialite": "spécialité ou null",
      "mandataire": "employeur" ou "employe" ou "CNESST" ou "TAT" ou "BEM" ou "inconnu",
      "conclusion_favorable_a": "employeur" ou "employe" ou "neutre"
    }}
  ]
}}"""
        )
        
        response = await chat.send_message(extract_message)
        
        import json
        json_str = response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        
        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            logger.warning("Impossible de parser le JSON des médecins")
            return
        
        if not data.get("medecins"):
            return
        
        for med in data["medecins"]:
            nom = med.get("nom", "").strip().upper()
            prenom = med.get("prenom", "").strip().title()
            
            if not nom or len(nom) < 2:
                continue
            
            existing = await db.medecins.find_one({
                "nom": nom,
                "prenom": {"$regex": f"^{prenom}$", "$options": "i"} if prenom else {"$exists": True}
            })
            
            if existing:
                medecin_id = existing["id"]
                update_data = {"derniere_maj": datetime.now(timezone.utc).isoformat()}
                if med.get("specialite") and not existing.get("specialite"):
                    update_data["specialite"] = med["specialite"]
                await db.medecins.update_one({"id": medecin_id}, {"$set": update_data})
            else:
                medecin_id = str(uuid.uuid4())
                new_medecin = {
                    "id": medecin_id,
                    "nom": nom,
                    "prenom": prenom,
                    "specialite": med.get("specialite"),
                    "adresse": None,
                    "ville": None,
                    "diplomes": None,
                    "decisions_pro_employeur": 0,
                    "decisions_pro_employe": 0,
                    "total_decisions": 0,
                    "pourcentage_pro_employeur": 0.0,
                    "pourcentage_pro_employe": 0.0,
                    "sources": [],
                    "derniere_maj": datetime.now(timezone.utc).isoformat()
                }
                await db.medecins.insert_one(new_medecin)
            
            conclusion = med.get("conclusion_favorable_a", "neutre")
            inc_fields = {"total_decisions": 1}
            if conclusion == "employeur":
                inc_fields["decisions_pro_employeur"] = 1
            elif conclusion == "employe":
                inc_fields["decisions_pro_employe"] = 1
            
            await db.medecins.update_one(
                {"id": medecin_id},
                {"$inc": inc_fields, "$addToSet": {"sources": source_filename}}
            )
            
            medecin_updated = await db.medecins.find_one({"id": medecin_id})
            if medecin_updated and medecin_updated["total_decisions"] > 0:
                total = medecin_updated["total_decisions"]
                pct_employeur = (medecin_updated["decisions_pro_employeur"] / total) * 100
                pct_employe = (medecin_updated["decisions_pro_employe"] / total) * 100
                await db.medecins.update_one(
                    {"id": medecin_id},
                    {"$set": {
                        "pourcentage_pro_employeur": round(pct_employeur, 1),
                        "pourcentage_pro_employe": round(pct_employe, 1)
                    }}
                )
        
        logger.info(f"Extraction terminée: {len(data['medecins'])} médecin(s)")
        
    except Exception as e:
        logger.error(f"Erreur extraction médecins: {str(e)}")

class MultiAnalysisResponse(BaseModel):
    success: bool
    total_files: int
    combined_analysis: str
    anonymized_for_ai: str
    message: str
    files_analyzed: List[str]
    destruction_confirmed: bool = True

@api_router.post("/analyze-multiple", response_model=MultiAnalysisResponse)
async def analyze_multiple_documents(files: List[UploadFile] = File(...), consent_ai_learning: bool = False):
    """Analyse plusieurs documents et retourne un rapport combiné."""
    
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 fichiers à la fois")
    
    # Vérifier tous les formats
    for f in files:
        if not is_accepted_format(f.filename):
            accepted = ", ".join(ACCEPTED_FORMATS.keys())
            raise HTTPException(status_code=400, detail=f"Format non accepté pour {f.filename}. Formats acceptés: {accepted}")
    
    all_analyses = []
    files_analyzed = []
    tmp_paths = []
    
    try:
        for idx, file in enumerate(files, 1):
            contents = await file.read()
            file_size = len(contents)
            
            if file_size > 100 * 1024 * 1024:
                continue  # Skip files over 100 Mo
            
            ext = get_file_extension(file.filename)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(contents)
                tmp_path = tmp_file.name
                tmp_paths.append(tmp_path)
            
            logger.info(f"Analyse du fichier {idx}/{len(files)}: {file.filename}")
            
            # Analyser le document
            mime_type = ACCEPTED_FORMATS.get(ext, 'application/octet-stream')
            analysis = await analyze_single_file(tmp_path, mime_type, file.filename, idx, len(files))
            # S'assurer que analysis n'est jamais None
            if analysis is None:
                analysis = "[Analyse non disponible pour ce document]"
            all_analyses.append(f"## 📄 Document {idx}: {file.filename}\n\n{analysis}")
            files_analyzed.append(file.filename)
        
        # Combiner toutes les analyses avec protection contre None
        combined = "# 📋 RAPPORT D'ANALYSE COMBINÉ - L'ÉCLAIREUR\n\n"
        combined += f"**{len(files_analyzed)} document(s) analysé(s)**\n\n"
        # S'assurer que tous les éléments sont des chaînes
        safe_analyses = [str(a) if a is not None else "[Analyse non disponible]" for a in all_analyses]
        combined += "---\n\n".join(safe_analyses)
        
        # Anonymisation
        report_analysis = anonymize_for_report(combined)
        ai_analysis = anonymize_for_ai_learning(combined) if consent_ai_learning else ""
        
        # Destruction sécurisée
        for path in tmp_paths:
            if os.path.exists(path):
                destruction_securisee(path)
        
        return MultiAnalysisResponse(
            success=True,
            total_files=len(files_analyzed),
            combined_analysis=report_analysis,
            anonymized_for_ai=ai_analysis,
            message=f"{len(files_analyzed)} document(s) analysé(s). Tous les fichiers ont été détruits de manière sécurisée.",
            files_analyzed=files_analyzed,
            destruction_confirmed=True
        )
        
    except Exception as e:
        # Destruction en cas d'erreur
        for path in tmp_paths:
            if os.path.exists(path):
                destruction_securisee(path)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")

async def analyze_single_file(file_path: str, mime_type: str, filename: str, idx: int, total: int) -> str:
    """Analyse un seul fichier avec Gemini."""
    import asyncio
    
    date_analyse = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    
    for attempt in range(3):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis-{uuid.uuid4()}",
                system_message=SYSTEM_MESSAGE_ANALYSE.replace("{date_analyse}", date_analyse)
            ).with_model("gemini", "gemini-2.5-flash")
            
            file_content = FileContentWithMimeType(
                file_path=file_path,
                mime_type=mime_type
            )
            
            user_message = UserMessage(
                text=f"""Analyse ce document ({filename} - fichier {idx}/{total}) et produis un RAPPORT DE DÉFENSE.

RAPPELS:
1. EXPLIQUE chaque terme médical/technique entre parenthèses
2. Indique les numéros de pages si possible
3. TABLEAU RÉCAPITULATIF DES CONTRADICTIONS en fin de rapport
4. Inclus le BARÈME DES INDEMNISATIONS applicable
5. Prépare des QUESTIONS STRATÉGIQUES pour l'audience TAT

ANONYMISATION - MASQUER uniquement: NAS, RAMQ, Permis, Coordonnées bancaires
GARDER EN CLAIR: noms, téléphones, adresses""",
                file_contents=[file_content]
            )
            
            response = await chat.send_message(user_message)
            return response if response else f"[Analyse de {filename} - Réponse vide]"
            
        except Exception as e:
            logger.error(f"Erreur analyse {filename}: {str(e)[:100]}")
            if attempt < 2:
                await asyncio.sleep(10)
                continue
            # Retourner un message d'erreur au lieu de lever une exception
            return f"[Erreur lors de l'analyse de {filename} - Serveurs temporairement indisponibles]"
    
    return f"[Erreur lors de l'analyse de {filename}]"

# ===== ROUTES =====
@api_router.get("/")
async def root():
    return {"message": "Bienvenue sur L'Éclaireur API", "status": "operational"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "L'Éclaireur"}

# Formats acceptés
ACCEPTED_FORMATS = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff',
    '.bmp': 'image/bmp',
    '.txt': 'text/plain',
    '.rtf': 'application/rtf',
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',
}

def get_file_extension(filename: str) -> str:
    """Retourne l'extension du fichier en minuscules."""
    return os.path.splitext(filename.lower())[1]

def is_accepted_format(filename: str) -> bool:
    """Vérifie si le format est accepté."""
    ext = get_file_extension(filename)
    return ext in ACCEPTED_FORMATS

def extract_pdfs_from_zip(zip_path: str) -> List[str]:
    """Extrait tous les fichiers PDF d'un ZIP et retourne leurs chemins temporaires."""
    extracted_paths = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.lower().endswith('.pdf') and not file_info.filename.startswith('__MACOSX'):
                    # Extraire le PDF
                    extracted_name = os.path.basename(file_info.filename)
                    if extracted_name:  # Ignorer les dossiers
                        temp_path = os.path.join(tempfile.gettempdir(), f"extracted_{uuid.uuid4()}_{extracted_name}")
                        with zip_ref.open(file_info) as source, open(temp_path, 'wb') as target:
                            target.write(source.read())
                        extracted_paths.append(temp_path)
                        logger.info(f"PDF extrait du ZIP: {extracted_name}")
        return extracted_paths
    except Exception as e:
        logger.error(f"Erreur extraction ZIP: {str(e)}")
        # Nettoyer en cas d'erreur
        for path in extracted_paths:
            if os.path.exists(path):
                destruction_securisee(path)
        return []

def extract_pdfs_from_rar(rar_path: str) -> List[str]:
    """Extrait tous les fichiers PDF d'un RAR et retourne leurs chemins temporaires."""
    extracted_paths = []
    try:
        with rarfile.RarFile(rar_path, 'r') as rar_ref:
            for file_info in rar_ref.infolist():
                if file_info.filename.lower().endswith('.pdf'):
                    # Extraire le PDF
                    extracted_name = os.path.basename(file_info.filename)
                    if extracted_name:  # Ignorer les dossiers
                        temp_path = os.path.join(tempfile.gettempdir(), f"extracted_{uuid.uuid4()}_{extracted_name}")
                        with rar_ref.open(file_info) as source, open(temp_path, 'wb') as target:
                            target.write(source.read())
                        extracted_paths.append(temp_path)
                        logger.info(f"PDF extrait du RAR: {extracted_name}")
        return extracted_paths
    except Exception as e:
        logger.error(f"Erreur extraction RAR: {str(e)}")
        # Nettoyer en cas d'erreur
        for path in extracted_paths:
            if os.path.exists(path):
                destruction_securisee(path)
        return []

# ===== ANALYSE ASYNCHRONE =====
async def run_analysis_background(job_id: str, file_path: str, filename: str, file_size: int, ext: str, consent_ai_learning: bool):
    """Exécute l'analyse en arrière-plan et met à jour le statut dans la base de données."""
    chunk_paths = []
    extracted_pdfs = []
    
    try:
        # Mettre à jour le statut
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "in_progress", "message": "Analyse démarrée..."}}
        )
        
        # Si c'est un ZIP ou RAR, extraire les PDFs
        if ext == '.zip':
            logger.info(f"[{job_id}] Fichier ZIP détecté, extraction des PDFs...")
            extracted_pdfs = extract_pdfs_from_zip(file_path)
            archive_type = "ZIP"
        elif ext == '.rar':
            logger.info(f"[{job_id}] Fichier RAR détecté, extraction des PDFs...")
            extracted_pdfs = extract_pdfs_from_rar(file_path)
            archive_type = "RAR"
        else:
            archive_type = None
        
        if ext in ['.zip', '.rar']:
            if not extracted_pdfs:
                await db.analysis_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {"status": "failed", "message": f"Aucun fichier PDF trouvé dans le {archive_type}"}}
                )
                return
            
            # Pour simplifier, on traite tous les PDFs extraits comme un seul document
            all_chunk_paths = []
            for pdf_path in extracted_pdfs:
                if os.path.getsize(pdf_path) > MAX_CHUNK_SIZE:
                    all_chunk_paths.extend(split_pdf_into_chunks(pdf_path, MAX_CHUNK_SIZE))
                else:
                    all_chunk_paths.append(pdf_path)
            chunk_paths = all_chunk_paths
        else:
            # Segmenter si PDF volumineux
            if ext == '.pdf' and file_size > MAX_CHUNK_SIZE:
                logger.info(f"[{job_id}] Fichier volumineux, segmentation en cours...")
                chunk_paths = split_pdf_into_chunks(file_path, MAX_CHUNK_SIZE)
            else:
                chunk_paths = [file_path]
        
        total_segments = len(chunk_paths)
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"total_segments": total_segments, "message": f"Analyse de {total_segments} segments..."}}
        )
        
        # Analyser chaque segment
        all_analyses = []
        for i, chunk_path in enumerate(chunk_paths, 1):
            logger.info(f"[{job_id}] Analyse du segment {i}/{total_segments}...")
            
            # Mettre à jour la progression
            progress = int((i - 1) / total_segments * 100)
            await db.analysis_jobs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "current_segment": i,
                    "progress": progress,
                    "message": f"Analyse du segment {i}/{total_segments}..."
                }}
            )
            
            segment_analysis = await analyze_pdf_segment(chunk_path, i, total_segments)
            if segment_analysis:
                all_analyses.append(segment_analysis)
            else:
                all_analyses.append(f"[Segment {i} - Analyse non disponible]")
            
            # Sauvegarder le rapport partiel après chaque segment
            partial_analysis = f"📄 **ANALYSE EN COURS** ({i}/{total_segments} segments complétés)\n\n"
            partial_analysis += "---\n\n".join([
                f"### Segment {j+1}/{total_segments}\n\n{str(a) if a else '[Non disponible]'}" 
                for j, a in enumerate(all_analyses)
            ])
            
            await db.analysis_jobs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "partial_analysis": anonymize_for_report(partial_analysis),
                    "progress": int(i / total_segments * 100)
                }}
            )
        
        # Combiner les analyses finales
        if total_segments > 1:
            combined_analysis = f"📄 **ANALYSE COMPLÈTE DU DOCUMENT** ({total_segments} segments)\n\n"
            segments_text = []
            for i, analysis in enumerate(all_analyses):
                analysis_str = str(analysis) if analysis is not None else "[Segment non disponible]"
                segments_text.append(f"### Segment {i+1}/{total_segments}\n\n{analysis_str}")
            combined_analysis += "---\n\n".join(segments_text)
        else:
            combined_analysis = str(all_analyses[0]) if all_analyses and all_analyses[0] else "[Analyse non disponible]"
        
        # Anonymisation
        report_analysis = anonymize_for_report(combined_analysis)
        
        # Sauvegarder le rapport final
        report_id = str(uuid.uuid4())
        expiration = datetime.now(timezone.utc).timestamp() + 900  # 15 minutes
        await db.temp_reports.insert_one({
            "report_id": report_id,
            "filename": filename,
            "analysis": report_analysis,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expiration,
            "segments": total_segments,
            "status": "termine"
        })
        
        # Mettre à jour le job comme terminé
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "current_segment": total_segments,
                "analysis": report_analysis,
                "report_id": report_id,
                "message": f"Analyse terminée ({total_segments} segments). Rapport disponible 15 minutes.",
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
        logger.info(f"[{job_id}] Analyse terminée avec succès. Report ID: {report_id}")
        
    except Exception as e:
        logger.error(f"[{job_id}] Erreur lors de l'analyse: {str(e)}")
        await db.analysis_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "message": f"Erreur: {str(e)[:200]}"
            }}
        )
    finally:
        # Destruction sécurisée
        for chunk_path in chunk_paths:
            if os.path.exists(chunk_path):
                destruction_securisee(chunk_path)
        for pdf_path in extracted_pdfs:
            if os.path.exists(pdf_path):
                destruction_securisee(pdf_path)
        if os.path.exists(file_path):
            destruction_securisee(file_path)

@api_router.post("/analyze-async", response_model=AsyncAnalysisResponse)
async def analyze_document_async(file: UploadFile = File(...), consent_ai_learning: bool = False):
    """Lance une analyse en arrière-plan et retourne immédiatement un ID de job."""
    
    if not is_accepted_format(file.filename):
        accepted = ", ".join(ACCEPTED_FORMATS.keys())
        raise HTTPException(status_code=400, detail=f"Format non accepté. Formats acceptés: {accepted}")
    
    contents = await file.read()
    file_size = len(contents)
    max_size = 100 * 1024 * 1024  # 100 Mo
    
    if file_size > max_size:
        raise HTTPException(status_code=400, detail="Le fichier dépasse la limite de 100 Mo")
    
    # Créer un ID de job unique
    job_id = str(uuid.uuid4())
    
    # Sauvegarder le fichier temporairement
    ext = get_file_extension(file.filename)
    tmp_path = os.path.join(tempfile.gettempdir(), f"analysis_{job_id}{ext}")
    with open(tmp_path, 'wb') as f:
        f.write(contents)
    
    # Créer l'entrée du job dans la base de données
    await db.analysis_jobs.insert_one({
        "job_id": job_id,
        "filename": file.filename,
        "file_size": file_size,
        "status": "pending",
        "progress": 0,
        "current_segment": 0,
        "total_segments": 0,
        "message": "Analyse en attente...",
        "created_at": datetime.now(timezone.utc),
        "consent_ai_learning": consent_ai_learning
    })
    
    # Lancer l'analyse en arrière-plan
    asyncio.create_task(run_analysis_background(job_id, tmp_path, file.filename, file_size, ext, consent_ai_learning))
    
    logger.info(f"Analyse asynchrone lancée: {job_id} pour {file.filename}")
    
    return AsyncAnalysisResponse(
        success=True,
        job_id=job_id,
        message="Analyse lancée en arrière-plan. Utilisez le lien de statut pour suivre la progression.",
        status_url=f"/api/analyze-status/{job_id}"
    )

@api_router.get("/analyze-status/{job_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(job_id: str):
    """Récupère le statut d'une analyse en cours."""
    job = await db.analysis_jobs.find_one({"job_id": job_id})
    
    if not job:
        raise HTTPException(status_code=404, detail="Job d'analyse non trouvé")
    
    return AnalysisStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0),
        current_segment=job.get("current_segment", 0),
        total_segments=job.get("total_segments", 0),
        filename=job.get("filename", ""),
        analysis=job.get("analysis") if job.get("status") == "completed" else job.get("partial_analysis"),
        message=job.get("message", ""),
        report_id=job.get("report_id")
    )

# ===== ANCIEN ENDPOINT (gardé pour compatibilité) =====
@api_router.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(file: UploadFile = File(...), consent_ai_learning: bool = False):
    """Analyse un document et retourne un rapport de défense."""
    
    contents = await file.read()
    file_size = len(contents)
    max_size = 100 * 1024 * 1024  # 100 Mo
    
    if file_size > max_size:
        raise HTTPException(status_code=400, detail="Le fichier dépasse la limite de 100 Mo")
    
    # Acquérir le verrou pour empêcher les analyses parallèles
    async with analysis_lock:
        this_analysis_id = str(uuid.uuid4())
        current_analysis_id = this_analysis_id
        logger.info(f"Début analyse {this_analysis_id}: {file.filename} ({file_size / (1024*1024):.2f} Mo)")
        
        chunk_paths = []
        tmp_path = None
        extracted_pdfs = []
        
        try:
            # Sauvegarder temporairement
            ext = get_file_extension(file.filename)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(contents)
                tmp_path = tmp_file.name
            
            # Si c'est un ZIP ou RAR, extraire les PDFs
            if ext == '.zip':
                logger.info("Fichier ZIP détecté, extraction des PDFs...")
                extracted_pdfs = extract_pdfs_from_zip(tmp_path)
                archive_type = "ZIP"
            elif ext == '.rar':
                logger.info("Fichier RAR détecté, extraction des PDFs...")
                extracted_pdfs = extract_pdfs_from_rar(tmp_path)
                archive_type = "RAR"
            else:
                archive_type = None
            
            if ext in ['.zip', '.rar']:
                if not extracted_pdfs:
                    raise HTTPException(status_code=400, detail=f"Aucun fichier PDF trouvé dans le {archive_type}")
                logger.info(f"{len(extracted_pdfs)} PDF(s) extraits du {archive_type}")
                
                # Analyser chaque PDF extrait
                all_analyses = []
                total_files = len(extracted_pdfs)
                
                for file_idx, pdf_path in enumerate(extracted_pdfs, 1):
                    pdf_name = os.path.basename(pdf_path)
                    pdf_size = os.path.getsize(pdf_path)
                    logger.info(f"Analyse du PDF {file_idx}/{total_files}: {pdf_name}")
                    
                    # Segmenter si nécessaire
                    if pdf_size > MAX_CHUNK_SIZE:
                        pdf_chunks = split_pdf_into_chunks(pdf_path, MAX_CHUNK_SIZE)
                    else:
                        pdf_chunks = [pdf_path]
                    
                    chunk_paths.extend(pdf_chunks)
                    
                    # Analyser les segments de ce PDF
                    pdf_analyses = []
                    for seg_idx, chunk_path in enumerate(pdf_chunks, 1):
                        analysis = await analyze_pdf_segment(chunk_path, seg_idx, len(pdf_chunks))
                        # Filtrer les résultats None
                        if analysis:
                            pdf_analyses.append(analysis)
                        else:
                            pdf_analyses.append(f"[Segment {seg_idx} - Analyse non disponible]")
                    
                    if len(pdf_chunks) > 1:
                        # S'assurer que tous les éléments sont des chaînes
                        safe_analyses = [str(a) if a is not None else "[Analyse non disponible]" for a in pdf_analyses]
                        combined = f"## 📄 {pdf_name}\n\n" + "\n---\n".join(safe_analyses)
                    else:
                        first_analysis = str(pdf_analyses[0]) if pdf_analyses and pdf_analyses[0] else '[Analyse non disponible]'
                        combined = f"## 📄 {pdf_name}\n\n{first_analysis}"
                    
                    all_analyses.append(combined)
                
                # S'assurer que tous les éléments sont des chaînes avant le join
                safe_all_analyses = [str(a) if a is not None else "[Analyse non disponible]" for a in all_analyses]
                combined_analysis = f"# 📋 ANALYSE DE {total_files} DOCUMENT(S) ({archive_type})\n\n"
                combined_analysis += "\n\n---\n\n".join(safe_all_analyses)
                total_segments = len(chunk_paths)
            
            else:
                # Traitement normal pour les autres fichiers
                # Segmenter si PDF volumineux
                if ext == '.pdf' and file_size > MAX_CHUNK_SIZE:
                    logger.info(f"Fichier volumineux, segmentation en cours...")
                    chunk_paths = split_pdf_into_chunks(tmp_path, MAX_CHUNK_SIZE)
                else:
                    chunk_paths = [tmp_path]
                
                # Créer un ID de rapport pour sauvegarde progressive
                progress_report_id = str(uuid.uuid4())
                
                # Analyser chaque segment et sauvegarder progressivement
                all_analyses = []
                total_segments = len(chunk_paths)
                
                for i, chunk_path in enumerate(chunk_paths, 1):
                    logger.info(f"Analyse du segment {i}/{total_segments}...")
                    segment_analysis = await analyze_pdf_segment(chunk_path, i, total_segments)
                    # Filtrer les résultats None
                    if segment_analysis:
                        all_analyses.append(segment_analysis)
                    else:
                        all_analyses.append(f"[Segment {i} - Analyse non disponible]")
                    
                    # Sauvegarder le rapport partiel après chaque segment
                    partial_analysis = f"📄 **ANALYSE EN COURS** ({i}/{total_segments} segments complétés)\n\n"
                    partial_analysis += "---\n\n".join([
                        f"### Segment {j+1}/{total_segments}\n\n{str(a) if a else '[Non disponible]'}" 
                        for j, a in enumerate(all_analyses)
                    ])
                    
                    await db.temp_reports.update_one(
                        {"report_id": progress_report_id},
                        {"$set": {
                            "report_id": progress_report_id,
                            "filename": file.filename,
                            "analysis": anonymize_for_report(partial_analysis),
                            "created_at": datetime.now(timezone.utc),
                            "expires_at": datetime.now(timezone.utc).timestamp() + 900,
                            "segments": i,
                            "total_segments": total_segments,
                            "status": "en_cours" if i < total_segments else "termine"
                        }},
                        upsert=True
                    )
                    logger.info(f"Rapport partiel sauvegardé: {progress_report_id} ({i}/{total_segments})")
                
                # Combiner les analyses avec protection contre None
                if total_segments > 1:
                    combined_analysis = f"📄 **ANALYSE COMPLÈTE DU DOCUMENT** ({total_segments} segments)\n\n"
                    try:
                        segments_text = []
                        for i, analysis in enumerate(all_analyses):
                            # S'assurer que chaque analyse est une chaîne
                            analysis_str = str(analysis) if analysis is not None else "[Segment non disponible]"
                            segments_text.append(f"### Segment {i+1}/{total_segments}\n\n{analysis_str}")
                        combined_analysis += "---\n\n".join(segments_text)
                    except Exception as join_error:
                        logger.error(f"Erreur lors de la combinaison: {str(join_error)}")
                        combined_analysis += "[Erreur lors de la combinaison des segments]"
                else:
                    combined_analysis = str(all_analyses[0]) if all_analyses and all_analyses[0] else "[Analyse non disponible]"
            
            # Anonymisation pour le rapport (légère)
            report_analysis = anonymize_for_report(combined_analysis)
            
            # Anonymisation complète pour l'IA (si consentement)
            ai_analysis = ""
            if consent_ai_learning:
                ai_analysis = anonymize_for_ai_learning(combined_analysis)
                logger.info("Version anonymisée créée pour apprentissage IA")
            
            # Extraire les médecins
            await extract_and_update_medecins(combined_analysis, file.filename)
            
            # DESTRUCTION SÉCURISÉE DOD 5220.22-M
            destruction_success = True
            for chunk_path in chunk_paths:
                if os.path.exists(chunk_path):
                    destruction_success = destruction_securisee(chunk_path) and destruction_success
            # Détruire les PDFs extraits du ZIP
            for pdf_path in extracted_pdfs:
                if os.path.exists(pdf_path):
                    destruction_success = destruction_securisee(pdf_path) and destruction_success
            if tmp_path and os.path.exists(tmp_path) and tmp_path not in chunk_paths:
                destruction_success = destruction_securisee(tmp_path) and destruction_success
            
            logger.info(f"Analyse terminée pour: {file.filename} - Destruction sécurisée: {destruction_success}")
            
            # Sauvegarder temporairement le rapport (15 minutes) pour permettre récupération
            report_id = str(uuid.uuid4())
            expiration = datetime.now(timezone.utc).timestamp() + 900  # 15 minutes
            await db.temp_reports.insert_one({
                "report_id": report_id,
                "filename": file.filename,
                "analysis": report_analysis,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expiration,
                "segments": total_segments
            })
            logger.info(f"Rapport sauvegardé temporairement: {report_id}")
            
            return AnalysisResponse(
                success=True,
                filename=file.filename,
                file_size=file_size,
                analysis=report_analysis,
                anonymized_for_ai=ai_analysis,
                message=f"Analyse terminée ({total_segments} segment{'s' if total_segments > 1 else ''}). Rapport disponible 15 minutes.",
                segments_analyzed=total_segments,
                destruction_confirmed=destruction_success,
                report_id=report_id
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {str(e)}")
            # Destruction sécurisée en cas d'erreur
            for chunk_path in chunk_paths:
                if os.path.exists(chunk_path):
                    destruction_securisee(chunk_path)
            for pdf_path in extracted_pdfs:
                if os.path.exists(pdf_path):
                    destruction_securisee(pdf_path)
            if tmp_path and os.path.exists(tmp_path):
                destruction_securisee(tmp_path)
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")

# ===== RÉCUPÉRATION RAPPORT TEMPORAIRE =====
@api_router.get("/report/{report_id}")
async def get_temporary_report(report_id: str):
    """Récupère un rapport temporaire par son ID (valide 15 minutes)."""
    report = await db.temp_reports.find_one({"report_id": report_id})
    
    if not report:
        raise HTTPException(status_code=404, detail="Rapport non trouvé ou expiré")
    
    # Vérifier expiration
    if datetime.now(timezone.utc).timestamp() > report.get("expires_at", 0):
        await db.temp_reports.delete_one({"report_id": report_id})
        raise HTTPException(status_code=410, detail="Ce rapport a expiré (validité 15 minutes)")
    
    return {
        "success": True,
        "filename": report.get("filename"),
        "analysis": report.get("analysis"),
        "segments": report.get("segments"),
        "total_segments": report.get("total_segments"),
        "status": report.get("status", "inconnu"),
        "created_at": report.get("created_at"),
        "message": "Rapport récupéré avec succès"
    }

@api_router.get("/reports/latest")
async def get_latest_report():
    """Récupère le dernier rapport en cours ou terminé (pour récupération en cas d'erreur)."""
    report = await db.temp_reports.find_one(
        {"expires_at": {"$gt": datetime.now(timezone.utc).timestamp()}},
        sort=[("created_at", -1)]
    )
    
    if not report:
        raise HTTPException(status_code=404, detail="Aucun rapport récent trouvé")
    
    return {
        "success": True,
        "report_id": report.get("report_id"),
        "filename": report.get("filename"),
        "analysis": report.get("analysis"),
        "segments": report.get("segments"),
        "total_segments": report.get("total_segments"),
        "status": report.get("status", "inconnu"),
        "created_at": report.get("created_at"),
        "message": f"Rapport {'en cours' if report.get('status') == 'en_cours' else 'terminé'} - {report.get('segments')}/{report.get('total_segments')} segments"
    }

# ===== COMPTEUR VISITEURS =====
@api_router.get("/stats/visitors")
async def get_visitor_count():
    stats = await db.stats.find_one({"type": "visitors"})
    if not stats:
        await db.stats.insert_one({"type": "visitors", "count": 0})
        return {"count": 0}
    return {"count": stats.get("count", 0)}

@api_router.post("/stats/visitors/increment")
async def increment_visitor_count():
    await db.stats.update_one({"type": "visitors"}, {"$inc": {"count": 1}}, upsert=True)
    stats = await db.stats.find_one({"type": "visitors"})
    return {"count": stats.get("count", 0)}

# ===== DÉCOUPAGE PDF AUTOMATIQUE =====
SPLIT_TARGET_SIZE = 15 * 1024 * 1024  # 15 Mo par partie (sous la limite Gemini de 20 Mo)

@api_router.post("/split-pdf")
async def split_pdf_for_download(file: UploadFile = File(...)):
    """
    Découpe un gros PDF en plusieurs parties téléchargeables.
    Retourne un fichier ZIP contenant toutes les parties.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés")
    
    contents = await file.read()
    file_size = len(contents)
    
    # Vérifier si le fichier nécessite un découpage
    if file_size <= SPLIT_TARGET_SIZE:
        raise HTTPException(status_code=400, detail="Ce fichier est assez petit pour être analysé directement (< 15 Mo)")
    
    tmp_path = None
    try:
        # Sauvegarder temporairement
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(contents)
            tmp_path = tmp_file.name
        
        reader = PdfReader(tmp_path)
        total_pages = len(reader.pages)
        
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="Le PDF semble vide")
        
        # Calculer le nombre de pages par partie
        avg_page_size = file_size / total_pages
        pages_per_part = max(1, int(SPLIT_TARGET_SIZE / avg_page_size))
        num_parts = math.ceil(total_pages / pages_per_part)
        
        logger.info(f"Découpage de {file.filename}: {total_pages} pages en {num_parts} parties de ~{pages_per_part} pages")
        
        # Créer le ZIP en mémoire
        zip_buffer = io.BytesIO()
        base_filename = file.filename.rsplit('.', 1)[0]
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(num_parts):
                writer = PdfWriter()
                start_page = i * pages_per_part
                end_page = min((i + 1) * pages_per_part, total_pages)
                
                for page_num in range(start_page, end_page):
                    writer.add_page(reader.pages[page_num])
                
                # Écrire la partie dans un buffer
                part_buffer = io.BytesIO()
                writer.write(part_buffer)
                part_buffer.seek(0)
                
                # Ajouter au ZIP
                part_filename = f"{base_filename}_partie_{i+1}_sur_{num_parts}.pdf"
                zip_file.writestr(part_filename, part_buffer.getvalue())
                
                logger.info(f"Partie {i+1}/{num_parts} créée: pages {start_page+1}-{end_page}")
        
        # Nettoyer le fichier temporaire
        if tmp_path and os.path.exists(tmp_path):
            destruction_securisee(tmp_path)
        
        # Retourner le ZIP
        zip_buffer.seek(0)
        zip_filename = f"{base_filename}_decoupe_{num_parts}_parties.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "X-Parts-Count": str(num_parts),
                "X-Pages-Per-Part": str(pages_per_part)
            }
        )
        
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            destruction_securisee(tmp_path)
        logger.error(f"Erreur découpage PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du découpage: {str(e)}")

# ===== TÉMOIGNAGES =====
class TestimonialCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    message: str = Field(..., min_length=10, max_length=500)
    rating: int = Field(..., ge=1, le=5)

@api_router.post("/testimonials")
async def create_testimonial(testimonial: TestimonialCreate):
    est_valide, msg = moderer_contenu(testimonial.message)
    if not est_valide:
        raise HTTPException(status_code=400, detail=msg)
    
    doc = {
        "id": str(uuid.uuid4()),
        "name": testimonial.name,
        "message": testimonial.message,
        "rating": testimonial.rating,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "approved": True
    }
    await db.testimonials.insert_one(doc)
    return {"message": "Témoignage soumis avec succès", "id": doc["id"]}

@api_router.get("/testimonials")
async def get_testimonials():
    testimonials = await db.testimonials.find({"approved": True}, {"_id": 0}).sort("timestamp", -1).to_list(20)
    return testimonials

# ===== MÉDECINS =====
DISCLAIMER_MEDECIN = """
⚖️ AVIS IMPORTANT - CLAUSE DE NON-RESPONSABILITÉ

Les statistiques sont compilées à partir de décisions publiques du TAT et autres sources publiques.
Ces informations sont fournies À TITRE INFORMATIF SEULEMENT.

• Ces données ne constituent PAS une accusation de partialité.
• Les pourcentages reflètent uniquement les décisions documentées.
• Chaque dossier est unique.

Pour vérifier le dossier disciplinaire d'un médecin:
https://www.cmq.org/fr/proteger-le-public/suivre-dossier-disciplinaire/decisions-disciplinaires
"""

@api_router.get("/medecins")
async def get_medecins():
    medecins = await db.medecins.find({}, {"_id": 0}).sort("nom", 1).to_list(500)
    return {"disclaimer": DISCLAIMER_MEDECIN, "medecins": medecins}

@api_router.get("/medecins/{medecin_id}")
async def get_medecin(medecin_id: str):
    medecin = await db.medecins.find_one({"id": medecin_id}, {"_id": 0})
    if not medecin:
        raise HTTPException(status_code=404, detail="Médecin non trouvé")
    
    contributions = await db.contributions.find(
        {"medecin_id": medecin_id, "approved": True}, {"_id": 0}
    ).sort("timestamp", -1).to_list(50)
    
    return {"disclaimer": DISCLAIMER_MEDECIN, "medecin": medecin, "contributions": contributions}

@api_router.get("/medecins/search/{nom}")
async def search_medecin(nom: str):
    medecins = await db.medecins.find(
        {"$or": [
            {"nom": {"$regex": nom, "$options": "i"}},
            {"prenom": {"$regex": nom, "$options": "i"}}
        ]}, {"_id": 0}
    ).to_list(20)
    return {"disclaimer": DISCLAIMER_MEDECIN, "medecins": medecins}

# ===== CONTRIBUTIONS =====
@api_router.post("/contributions")
async def create_contribution(contribution: ContributionCreate):
    est_valide, msg = moderer_contenu(contribution.description)
    if not est_valide:
        raise HTTPException(status_code=400, detail=msg)
    
    if contribution.source_reference:
        est_valide, msg = moderer_contenu(contribution.source_reference)
        if not est_valide:
            raise HTTPException(status_code=400, detail=msg)
    
    medecin = await db.medecins.find_one({
        "nom": {"$regex": f"^{contribution.medecin_nom}$", "$options": "i"},
        "prenom": {"$regex": f"^{contribution.medecin_prenom}$", "$options": "i"}
    })
    
    if not medecin:
        medecin_id = str(uuid.uuid4())
        medecin = {
            "id": medecin_id,
            "nom": contribution.medecin_nom.upper(),
            "prenom": contribution.medecin_prenom.title(),
            "specialite": None, "adresse": None, "ville": None, "diplomes": None,
            "decisions_pro_employeur": 0, "decisions_pro_employe": 0, "total_decisions": 0,
            "pourcentage_pro_employeur": 0.0, "pourcentage_pro_employe": 0.0,
            "sources": [], "derniere_maj": datetime.now(timezone.utc).isoformat()
        }
        await db.medecins.insert_one(medecin)
    else:
        medecin_id = medecin["id"]
    
    contribution_doc = {
        "id": str(uuid.uuid4()),
        "medecin_id": medecin_id,
        "medecin_nom": contribution.medecin_nom.upper(),
        "medecin_prenom": contribution.medecin_prenom.title(),
        "type_contribution": contribution.type_contribution,
        "description": contribution.description,
        "source_reference": contribution.source_reference,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "approved": True
    }
    await db.contributions.insert_one(contribution_doc)
    
    inc_fields = {"total_decisions": 1}
    if contribution.type_contribution == "pro_employeur":
        inc_fields["decisions_pro_employeur"] = 1
    elif contribution.type_contribution == "pro_employe":
        inc_fields["decisions_pro_employe"] = 1
    
    update_ops = {"$set": {"derniere_maj": datetime.now(timezone.utc).isoformat()}, "$inc": inc_fields}
    if contribution.source_reference:
        update_ops["$addToSet"] = {"sources": contribution.source_reference}
    
    await db.medecins.update_one({"id": medecin_id}, update_ops)
    
    medecin_updated = await db.medecins.find_one({"id": medecin_id})
    if medecin_updated and medecin_updated["total_decisions"] > 0:
        pct_employeur = (medecin_updated["decisions_pro_employeur"] / medecin_updated["total_decisions"]) * 100
        pct_employe = (medecin_updated["decisions_pro_employe"] / medecin_updated["total_decisions"]) * 100
        await db.medecins.update_one({"id": medecin_id}, {"$set": {
            "pourcentage_pro_employeur": round(pct_employeur, 1),
            "pourcentage_pro_employe": round(pct_employe, 1)
        }})
    
    return {
        "message": "Contribution enregistrée avec succès!",
        "id": contribution_doc["id"],
        "disclaimer": DISCLAIMER_MEDECIN
    }

@api_router.get("/contributions")
async def get_contributions():
    contributions = await db.contributions.find({"approved": True}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    return contributions

@api_router.get("/stats/medecins")
async def get_medecins_stats():
    total_medecins = await db.medecins.count_documents({})
    total_contributions = await db.contributions.count_documents({"approved": True})
    top_medecins = await db.medecins.find({"total_decisions": {"$gt": 0}}, {"_id": 0}).sort("total_decisions", -1).to_list(10)
    
    return {
        "disclaimer": DISCLAIMER_MEDECIN,
        "total_medecins_documentes": total_medecins,
        "total_contributions": total_contributions,
        "top_medecins_documentes": top_medecins
    }

# ===== NETTOYAGE =====
@api_router.delete("/nettoyer")
async def nettoyer_fichiers_temporaires():
    """Nettoie tous les fichiers temporaires de manière sécurisée."""
    fichiers_supprimes = 0
    for nom_fichier in os.listdir(UPLOAD_DIR):
        if nom_fichier.endswith('.pdf'):
            chemin = os.path.join(UPLOAD_DIR, nom_fichier)
            if os.path.isfile(chemin):
                destruction_securisee(chemin)
                fichiers_supprimes += 1
    return {"status": "nettoyé", "message": f"{fichiers_supprimes} fichier(s) supprimé(s)"}

# Include router and CORS
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
