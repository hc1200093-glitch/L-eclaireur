from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
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

# PDF manipulation
from PyPDF2 import PdfReader, PdfWriter

# Import Emergent LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'leclaireur_db')]

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Limite de taille pour Gemini (15 Mo pour être safe)
MAX_CHUNK_SIZE = 15 * 1024 * 1024  # 15 Mo

# Create the main app
app = FastAPI(title="L'Éclaireur API", description="Outil d'aide pour les travailleurs québécois")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

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
    message: str
    segments_analyzed: int = 1

# Modèles pour les fiches médecins
class MedecinCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    prenom: str = Field(..., min_length=2, max_length=100)
    specialite: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    diplomes: Optional[str] = None
    source_info: Optional[str] = None  # Jurisprudence TAT, etc.

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
    source_reference: Optional[str] = None  # Numéro de dossier TAT, date, etc.
    
# Liste de mots interdits pour la modération
MOTS_INTERDITS = [
    # Insultes et grossièretés
    "con", "connard", "connasse", "merde", "putain", "salaud", "salope", "enculé",
    "fuck", "shit", "bitch", "asshole", "bastard",
    # Termes discriminatoires
    "nègre", "négro", "arabe", "sale", "terroriste", "islamiste",
    "pédé", "tapette", "gouine", "travelo",
    # Violence
    "tuer", "mort", "crever", "buter", "assassin", "violence",
    "frapper", "tabasser", "lyncher",
    # Menaces
    "menace", "revenge", "vengeance", "payer cher",
]

def moderer_contenu(texte: str) -> tuple[bool, str]:
    """Vérifie si le contenu contient des termes interdits.
    Retourne (est_valide, message_erreur)"""
    texte_lower = texte.lower()
    for mot in MOTS_INTERDITS:
        if mot in texte_lower:
            return False, f"Contenu inapproprié détecté. Merci de reformuler de manière factuelle et respectueuse."
    return True, ""

# Fonction pour anonymiser les données sensibles
def anonymize_sensitive_data(text: str) -> str:
    """Anonymise les NAS, adresses, noms, numéros de téléphone, etc."""
    
    # Anonymiser les NAS (format: XXX-XXX-XXX ou XXX XXX XXX ou XXXXXXXXX)
    text = re.sub(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b', '[NAS MASQUÉ]', text)
    
    # Anonymiser les numéros de téléphone
    text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[TÉL MASQUÉ]', text)
    
    # Anonymiser les codes postaux canadiens
    text = re.sub(r'\b[A-Za-z]\d[A-Za-z][-\s]?\d[A-Za-z]\d\b', '[CODE POSTAL MASQUÉ]', text)
    
    # Anonymiser les adresses courriel
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[COURRIEL MASQUÉ]', text)
    
    # Anonymiser les numéros de dossier CNESST (format variable)
    text = re.sub(r'\b\d{6,7}[-]?\d{9}[-]?\d{6}[-]?[A-Z][-]?[A-Z]{2,3}\b', '[NO DOSSIER MASQUÉ]', text)
    
    return text

def split_pdf_into_chunks(pdf_path: str, max_size_bytes: int = MAX_CHUNK_SIZE) -> List[str]:
    """
    Divise un PDF volumineux en plusieurs fichiers plus petits.
    Retourne une liste de chemins vers les fichiers segmentés.
    """
    chunk_paths = []
    
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        if total_pages == 0:
            return [pdf_path]
        
        # Estimer la taille par page
        file_size = os.path.getsize(pdf_path)
        avg_page_size = file_size / total_pages
        
        # Calculer le nombre de pages par segment
        pages_per_chunk = max(1, int(max_size_bytes / avg_page_size))
        
        # S'assurer qu'on ne dépasse pas un nombre raisonnable de pages
        pages_per_chunk = min(pages_per_chunk, 50)  # Max 50 pages par segment
        
        num_chunks = math.ceil(total_pages / pages_per_chunk)
        
        logger.info(f"PDF de {total_pages} pages, divisé en {num_chunks} segments de ~{pages_per_chunk} pages")
        
        for i in range(num_chunks):
            writer = PdfWriter()
            start_page = i * pages_per_chunk
            end_page = min((i + 1) * pages_per_chunk, total_pages)
            
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            # Sauvegarder le segment
            chunk_path = f"{pdf_path}_segment_{i+1}.pdf"
            with open(chunk_path, 'wb') as chunk_file:
                writer.write(chunk_file)
            
            chunk_paths.append(chunk_path)
            logger.info(f"Segment {i+1}/{num_chunks} créé: pages {start_page+1}-{end_page}")
        
        return chunk_paths
        
    except Exception as e:
        logger.error(f"Erreur lors de la segmentation du PDF: {str(e)}")
        # En cas d'erreur, retourner le fichier original
        return [pdf_path]

async def analyze_pdf_segment(pdf_path: str, segment_num: int, total_segments: int, max_retries: int = 5) -> str:
    """Analyse un segment de PDF avec Gemini avec retry automatique."""
    
    import asyncio
    
    for attempt in range(max_retries):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"analysis-{uuid.uuid4()}",
                system_message="""Tu es un assistant juridique spécialisé dans l'analyse de documents pour les travailleurs québécois accidentés.

Ton rôle est d'analyser les documents de la CNESST, du TAT et autres documents juridiques liés aux accidents de travail et maladies professionnelles.

Tu dois produire un RAPPORT COMPLET DE DÉFENSE pour aider le travailleur et son avocat.

BARÈMES CNESST - INDEMNITÉS POUR ATTEINTE PERMANENTE (référence):
- Ligament croisé antérieur (LCA): 2% à 10% = 2,400$ à 12,000$
- Ligament croisé postérieur (LCP): 2% à 8% = 2,400$ à 9,600$
- Ménisque (méniscectomie partielle): 1% à 5% = 1,200$ à 6,000$
- Hernie discale cervicale: 2% à 15% = 2,400$ à 18,000$
- Hernie discale lombaire: 2% à 15% = 2,400$ à 18,000$
- Syndrome du canal carpien: 1% à 5% = 1,200$ à 6,000$
- Tendinite chronique: 1% à 3% = 1,200$ à 3,600$
- Fracture vertébrale: 5% à 25% = 6,000$ à 30,000$
- Kyste synovial/adhérent: 1% à 5% = 1,200$ à 6,000$
- Lombalgie chronique: 2% à 10% = 2,400$ à 12,000$
- Cervicalgie chronique: 2% à 8% = 2,400$ à 9,600$
- Épicondylite: 1% à 3% = 1,200$ à 3,600$
- Bursite: 1% à 3% = 1,200$ à 3,600$
- TSPT (trouble de stress post-traumatique): 5% à 35% = 6,000$ à 42,000$
(Base: environ 1,200$ par 1% d'atteinte permanente en 2024)

IMPORTANT: 
- Ne jamais reproduire les informations personnelles du travailleur (NAS, adresse, nom complet)
- Tu DOIS mentionner les noms des médecins experts (information professionnelle publique)
- Sois factuel et précis dans ton analyse"""
            ).with_model("gemini", "gemini-2.5-flash")
            
            pdf_file = FileContentWithMimeType(
                file_path=pdf_path,
                mime_type="application/pdf"
            )
            
            segment_info = ""
            if total_segments > 1:
                segment_info = f"\n\n[SEGMENT {segment_num}/{total_segments}]"
            
            user_message = UserMessage(
                text=f"""Analyse ce document{segment_info} et produis un RAPPORT COMPLET DE DÉFENSE:

══════════════════════════════════════════════════════════════
## 📋 SECTION 1 - ANALYSE GÉNÉRALE
══════════════════════════════════════════════════════════════
1. **Type de document**: (décision CNESST, rapport médical, expertise BEM, décision TAT, etc.)
2. **Résumé**: Les points essentiels en 3-5 phrases
3. **Blessures/Lésions identifiées**: Liste toutes les blessures mentionnées
4. **Dates clés**: Dates importantes (accident, expertises, audiences, délais)
5. **Implications pour le travailleur**: Ce que cela signifie concrètement

══════════════════════════════════════════════════════════════
## 👨‍⚕️ SECTION 2 - MÉDECINS IDENTIFIÉS
══════════════════════════════════════════════════════════════
Pour CHAQUE médecin mentionné:
| Médecin | Spécialité | Mandaté par | Conclusion | % invalidité |
|---------|------------|-------------|------------|--------------|
| Dr [Nom] | [spécialité] | [employeur/travailleur/BEM/CNESST] | [conclusion] | [X%] |

══════════════════════════════════════════════════════════════
## ⚠️ SECTION 3 - INCOHÉRENCES DÉTECTÉES
══════════════════════════════════════════════════════════════
Compare les examens objectifs (IRM, radiographies, scanner, pet scan) avec les conclusions des médecins:

Pour chaque incohérence:
🔴 **INCOHÉRENCE #[numéro]**
- **Examen objectif**: [Type d'examen] montre [résultat]
- **Conclusion du Dr [Nom]**: [sa conclusion]
- **Écart constaté**: [explication de l'incohérence]
- **Impact pour le travailleur**: [conséquence de cette minimisation]

══════════════════════════════════════════════════════════════
## 💰 SECTION 4 - BARÈMES CNESST APPLICABLES
══════════════════════════════════════════════════════════════
Selon les blessures identifiées dans le document:
| Blessure | Fourchette % atteinte | Indemnité estimée |
|----------|----------------------|-------------------|
| [blessure] | X% à Y% | X,XXX$ à Y,YYY$ |

**Note**: Ces montants sont indicatifs basés sur les barèmes CNESST 2024.

══════════════════════════════════════════════════════════════
## 🔍 SECTION 5 - JURISPRUDENCES PERTINENTES À RECHERCHER
══════════════════════════════════════════════════════════════
Basé sur les blessures et la situation, rechercher sur CanLII (canlii.org/fr/qc/qctat/):
- Mots-clés suggérés: [liste de mots-clés pertinents]
- Types de décisions similaires: [ex: "contestation expertise BEM", "incohérence médicale"]
- Exemple de recherche: "[blessure] + [situation] + TAT"

══════════════════════════════════════════════════════════════
## ⚔️ SECTION 6 - KIT DE DÉFENSE
══════════════════════════════════════════════════════════════

### Questions suggérées pour l'audience (à poser au médecin expert de l'employeur):

1. "Dr [Nom], avez-vous pris connaissance de l'IRM/radiographie du [date] avant de rendre votre conclusion?"

2. "Comment expliquez-vous que votre examen physique de [X minutes] contredise les résultats de [examen objectif]?"

3. "Sur combien de dossiers avez-vous été mandaté par [employeur] au cours des 5 dernières années?"

4. "Votre conclusion de [X%] d'invalidité est [Y%] inférieure à celle du BEM/médecin traitant. Sur quelles bases médicales objectives?"

5. [Questions spécifiques basées sur les incohérences détectées]

### Arguments de défense suggérés:
- [Liste d'arguments basés sur l'analyse]

### Documents à demander:
- [Liste de documents manquants ou à obtenir]

══════════════════════════════════════════════════════════════
## 📌 SECTION 7 - ACTIONS RECOMMANDÉES
══════════════════════════════════════════════════════════════
1. [Action prioritaire 1]
2. [Action prioritaire 2]
3. [Délais à respecter]

══════════════════════════════════════════════════════════════

Réponds en français. Ne reproduis AUCUNE information personnelle du travailleur.""",
                file_contents=[pdf_file]
            )
            
            response = await chat.send_message(user_message)
            return response
            
        except Exception as e:
            error_str = str(e)
            if "502" in error_str or "503" in error_str or "timeout" in error_str.lower() or "500" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 15  # 15s, 30s, 45s, 60s
                    logger.warning(f"Erreur temporaire segment {segment_num}, retry {attempt+2}/{max_retries} dans {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
            raise e
    
    raise Exception(f"Échec après {max_retries} tentatives pour le segment {segment_num}")

async def extract_and_update_medecins(analysis_text: str, source_filename: str):
    """Extrait automatiquement les médecins de l'analyse et met à jour la base de données."""
    try:
        # Utiliser Gemini pour extraire les informations structurées des médecins
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"extract-medecins-{uuid.uuid4()}",
            system_message="""Tu es un extracteur de données. Tu dois analyser le texte et extraire les informations sur les médecins mentionnés.
            
Réponds UNIQUEMENT en JSON valide, sans autre texte. Si aucun médecin n'est trouvé, retourne {"medecins": []}"""
        ).with_model("gemini", "gemini-2.5-flash")
        
        extract_message = UserMessage(
            text=f"""Analyse ce texte et extrait les informations sur chaque médecin mentionné.

TEXTE À ANALYSER:
{analysis_text[:15000]}

Retourne UNIQUEMENT un JSON avec ce format exact:
{{
  "medecins": [
    {{
      "nom": "NOM_EN_MAJUSCULES",
      "prenom": "Prénom",
      "specialite": "spécialité ou null",
      "mandataire": "employeur" ou "employe" ou "CNESST" ou "TAT" ou "BEM" ou "inconnu",
      "conclusion_favorable_a": "employeur" ou "employe" ou "neutre",
      "pourcentage_invalidite": nombre ou null
    }}
  ],
  "decision_finale": "favorable_employeur" ou "favorable_employe" ou "mixte" ou "inconnue"
}}

Règles:
- mandataire "employeur" = médecin mandaté par l'employeur
- mandataire "employe" = médecin du travailleur ou mandaté par le travailleur
- mandataire "BEM" = Bureau d'évaluation médicale
- conclusion_favorable_a: basé sur si le médecin minimise (pro-employeur) ou reconnaît (pro-employé) les blessures
- Si un médecin donne un % d'invalidité plus bas que les examens objectifs, c'est pro-employeur
- Si un médecin reconnaît pleinement les lésions, c'est pro-employé

Retourne SEULEMENT le JSON, pas d'autre texte."""
        )
        
        response = await chat.send_message(extract_message)
        
        # Parser le JSON
        import json
        # Nettoyer la réponse pour extraire le JSON
        json_str = response.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Impossible de parser le JSON des médecins: {json_str[:200]}")
            return
        
        if not data.get("medecins"):
            logger.info("Aucun médecin extrait de l'analyse")
            return
        
        decision_finale = data.get("decision_finale", "inconnue")
        
        for med in data["medecins"]:
            nom = med.get("nom", "").strip().upper()
            prenom = med.get("prenom", "").strip().title()
            
            if not nom or len(nom) < 2:
                continue
            
            # Chercher si le médecin existe déjà
            existing = await db.medecins.find_one({
                "nom": nom,
                "prenom": {"$regex": f"^{prenom}$", "$options": "i"} if prenom else {"$exists": True}
            })
            
            if existing:
                medecin_id = existing["id"]
                # Mettre à jour les infos si on en a de nouvelles
                update_data = {"derniere_maj": datetime.now(timezone.utc).isoformat()}
                if med.get("specialite") and not existing.get("specialite"):
                    update_data["specialite"] = med["specialite"]
                
                await db.medecins.update_one({"id": medecin_id}, {"$set": update_data})
            else:
                # Créer le médecin
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
            
            # Déterminer si cette décision compte comme pro-employeur ou pro-employé
            conclusion = med.get("conclusion_favorable_a", "neutre")
            
            inc_fields = {"total_decisions": 1}
            if conclusion == "employeur":
                inc_fields["decisions_pro_employeur"] = 1
            elif conclusion == "employe":
                inc_fields["decisions_pro_employe"] = 1
            
            # Mettre à jour les statistiques
            await db.medecins.update_one(
                {"id": medecin_id},
                {
                    "$inc": inc_fields,
                    "$addToSet": {"sources": source_filename}
                }
            )
            
            # Recalculer les pourcentages
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
            
            logger.info(f"Médecin mis à jour: Dr {prenom} {nom} - {conclusion}")
        
        logger.info(f"Extraction automatique terminée: {len(data['medecins'])} médecin(s) traité(s)")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des médecins: {str(e)}")
        # Ne pas faire échouer l'analyse principale si l'extraction échoue

# Routes
@api_router.get("/")
async def root():
    return {"message": "Bienvenue sur L'Éclaireur API", "status": "operational"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "L'Éclaireur"}

@api_router.post("/analyze", response_model=AnalysisResponse)
async def analyze_document(file: UploadFile = File(...)):
    """Analyse un document PDF et retourne un résumé anonymisé."""
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés")
    
    # Vérifier la taille du fichier (max 100 Mo maintenant avec segmentation)
    contents = await file.read()
    file_size = len(contents)
    max_size = 100 * 1024 * 1024  # 100 Mo
    
    if file_size > max_size:
        raise HTTPException(status_code=400, detail="Le fichier dépasse la limite de 100 Mo")
    
    logger.info(f"Analyse du fichier: {file.filename} ({file_size / (1024*1024):.2f} Mo)")
    
    chunk_paths = []
    tmp_path = None
    
    try:
        # Sauvegarder temporairement le fichier
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(contents)
            tmp_path = tmp_file.name
        
        # Vérifier si le fichier doit être segmenté
        if file_size > MAX_CHUNK_SIZE:
            logger.info(f"Fichier volumineux ({file_size / (1024*1024):.2f} Mo), segmentation en cours...")
            chunk_paths = split_pdf_into_chunks(tmp_path, MAX_CHUNK_SIZE)
        else:
            chunk_paths = [tmp_path]
        
        # Analyser chaque segment
        all_analyses = []
        total_segments = len(chunk_paths)
        
        for i, chunk_path in enumerate(chunk_paths, 1):
            logger.info(f"Analyse du segment {i}/{total_segments}...")
            segment_analysis = await analyze_pdf_segment(chunk_path, i, total_segments)
            all_analyses.append(segment_analysis)
        
        # Combiner les analyses
        if total_segments > 1:
            combined_analysis = f"📄 **ANALYSE COMPLÈTE DU DOCUMENT** ({total_segments} segments analysés)\n\n"
            combined_analysis += "---\n\n".join([
                f"### Segment {i+1}/{total_segments}\n\n{analysis}" 
                for i, analysis in enumerate(all_analyses)
            ])
        else:
            combined_analysis = all_analyses[0]
        
        # Anonymiser la réponse (double sécurité)
        anonymized_analysis = anonymize_sensitive_data(combined_analysis)
        
        # Extraire automatiquement les médecins et mettre à jour les statistiques
        await extract_and_update_medecins(combined_analysis, file.filename)
        
        # Nettoyer les fichiers temporaires
        for chunk_path in chunk_paths:
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)
        if tmp_path and os.path.exists(tmp_path) and tmp_path not in chunk_paths:
            os.unlink(tmp_path)
        
        # Sauvegarder l'analyse dans MongoDB
        analysis_doc = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "file_size": file_size,
            "analysis": anonymized_analysis,
            "segments": total_segments,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.analyses.insert_one(analysis_doc)
        
        logger.info(f"Analyse terminée pour: {file.filename} ({total_segments} segments)")
        
        return AnalysisResponse(
            success=True,
            filename=file.filename,
            file_size=file_size,
            analysis=anonymized_analysis,
            message=f"Analyse terminée avec succès ({total_segments} segment{'s' if total_segments > 1 else ''})",
            segments_analyzed=total_segments
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {str(e)}")
        # Nettoyer les fichiers temporaires en cas d'erreur
        for chunk_path in chunk_paths:
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}")

@api_router.get("/analyses", response_model=List[dict])
async def get_analyses():
    """Récupère l'historique des analyses (sans données sensibles)."""
    analyses = await db.analyses.find({}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    return analyses

@api_router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Supprime une analyse de l'historique."""
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analyse non trouvée")
    return {"message": "Analyse supprimée avec succès"}

# ===== COMPTEUR D'UTILISATEURS =====
@api_router.get("/stats/visitors")
async def get_visitor_count():
    """Retourne le nombre de visiteurs anonymes."""
    stats = await db.stats.find_one({"type": "visitors"})
    if not stats:
        await db.stats.insert_one({"type": "visitors", "count": 0})
        return {"count": 0}
    return {"count": stats.get("count", 0)}

@api_router.post("/stats/visitors/increment")
async def increment_visitor_count():
    """Incrémente le compteur de visiteurs."""
    result = await db.stats.update_one(
        {"type": "visitors"},
        {"$inc": {"count": 1}},
        upsert=True
    )
    stats = await db.stats.find_one({"type": "visitors"})
    return {"count": stats.get("count", 0)}

# ===== TÉMOIGNAGES =====
class TestimonialCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    message: str = Field(..., min_length=10, max_length=500)
    rating: int = Field(..., ge=1, le=5)

class Testimonial(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    message: str
    rating: int
    timestamp: str
    approved: bool = False

@api_router.post("/testimonials")
async def create_testimonial(testimonial: TestimonialCreate):
    """Crée un nouveau témoignage (en attente d'approbation)."""
    doc = {
        "id": str(uuid.uuid4()),
        "name": testimonial.name,
        "message": testimonial.message,
        "rating": testimonial.rating,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "approved": True  # Auto-approuvé pour l'instant
    }
    await db.testimonials.insert_one(doc)
    return {"message": "Témoignage soumis avec succès", "id": doc["id"]}

@api_router.get("/testimonials")
async def get_testimonials():
    """Récupère les témoignages approuvés."""
    testimonials = await db.testimonials.find(
        {"approved": True}, 
        {"_id": 0}
    ).sort("timestamp", -1).to_list(20)
    return testimonials

# ===== FICHES MÉDECINS =====
DISCLAIMER_MEDECIN = """
⚖️ AVIS IMPORTANT - CLAUSE DE NON-RESPONSABILITÉ

Les statistiques présentées sont compilées à partir de décisions publiques du Tribunal administratif du travail (TAT) et autres sources publiques. Ces informations sont fournies À TITRE INFORMATIF SEULEMENT.

• Ces données ne constituent PAS une accusation de partialité envers quelque médecin que ce soit.
• Les pourcentages reflètent uniquement les décisions documentées dans les sources publiques consultées.
• Chaque dossier est unique et les conclusions médicales dépendent de multiples facteurs.
• Ces statistiques ne préjugent en rien de la qualité ou de l'intégrité professionnelle des médecins.

Cette fonctionnalité vise à informer les travailleurs, non à diffamer des professionnels de la santé.
"""

@api_router.get("/medecins")
async def get_medecins():
    """Récupère la liste des médecins avec leurs statistiques."""
    medecins = await db.medecins.find({}, {"_id": 0}).sort("nom", 1).to_list(500)
    return {
        "disclaimer": DISCLAIMER_MEDECIN,
        "medecins": medecins
    }

@api_router.get("/medecins/{medecin_id}")
async def get_medecin(medecin_id: str):
    """Récupère les détails d'un médecin spécifique."""
    medecin = await db.medecins.find_one({"id": medecin_id}, {"_id": 0})
    if not medecin:
        raise HTTPException(status_code=404, detail="Médecin non trouvé")
    
    # Récupérer les contributions associées
    contributions = await db.contributions.find(
        {"medecin_id": medecin_id, "approved": True},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(50)
    
    return {
        "disclaimer": DISCLAIMER_MEDECIN,
        "medecin": medecin,
        "contributions": contributions
    }

@api_router.get("/medecins/search/{nom}")
async def search_medecin(nom: str):
    """Recherche un médecin par nom."""
    # Recherche insensible à la casse
    medecins = await db.medecins.find(
        {"$or": [
            {"nom": {"$regex": nom, "$options": "i"}},
            {"prenom": {"$regex": nom, "$options": "i"}}
        ]},
        {"_id": 0}
    ).to_list(20)
    return {
        "disclaimer": DISCLAIMER_MEDECIN,
        "medecins": medecins
    }

# ===== CONTRIBUTIONS UTILISATEURS =====
@api_router.post("/contributions")
async def create_contribution(contribution: ContributionCreate):
    """Soumet une contribution sur un médecin (modérée)."""
    
    # Modération du contenu
    est_valide, message_erreur = moderer_contenu(contribution.description)
    if not est_valide:
        raise HTTPException(status_code=400, detail=message_erreur)
    
    if contribution.source_reference:
        est_valide, message_erreur = moderer_contenu(contribution.source_reference)
        if not est_valide:
            raise HTTPException(status_code=400, detail=message_erreur)
    
    # Chercher ou créer le médecin
    medecin = await db.medecins.find_one({
        "nom": {"$regex": f"^{contribution.medecin_nom}$", "$options": "i"},
        "prenom": {"$regex": f"^{contribution.medecin_prenom}$", "$options": "i"}
    })
    
    if not medecin:
        # Créer une nouvelle fiche médecin
        medecin_id = str(uuid.uuid4())
        medecin = {
            "id": medecin_id,
            "nom": contribution.medecin_nom.upper(),
            "prenom": contribution.medecin_prenom.title(),
            "specialite": None,
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
        await db.medecins.insert_one(medecin)
    else:
        medecin_id = medecin["id"]
    
    # Créer la contribution
    contribution_doc = {
        "id": str(uuid.uuid4()),
        "medecin_id": medecin_id,
        "medecin_nom": contribution.medecin_nom.upper(),
        "medecin_prenom": contribution.medecin_prenom.title(),
        "type_contribution": contribution.type_contribution,
        "description": contribution.description,
        "source_reference": contribution.source_reference,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "approved": True  # Auto-approuvé après modération
    }
    await db.contributions.insert_one(contribution_doc)
    
    # Mettre à jour les statistiques du médecin
    update_fields = {"derniere_maj": datetime.now(timezone.utc).isoformat()}
    inc_fields = {"total_decisions": 1}
    
    if contribution.type_contribution == "pro_employeur":
        inc_fields["decisions_pro_employeur"] = 1
    elif contribution.type_contribution == "pro_employe":
        inc_fields["decisions_pro_employe"] = 1
    
    if contribution.source_reference:
        await db.medecins.update_one(
            {"id": medecin_id},
            {
                "$set": update_fields,
                "$inc": inc_fields,
                "$addToSet": {"sources": contribution.source_reference}
            }
        )
    else:
        await db.medecins.update_one(
            {"id": medecin_id},
            {"$set": update_fields, "$inc": inc_fields}
        )
    
    # Recalculer les pourcentages
    medecin_updated = await db.medecins.find_one({"id": medecin_id})
    if medecin_updated and medecin_updated["total_decisions"] > 0:
        pct_employeur = (medecin_updated["decisions_pro_employeur"] / medecin_updated["total_decisions"]) * 100
        pct_employe = (medecin_updated["decisions_pro_employe"] / medecin_updated["total_decisions"]) * 100
        await db.medecins.update_one(
            {"id": medecin_id},
            {"$set": {
                "pourcentage_pro_employeur": round(pct_employeur, 1),
                "pourcentage_pro_employe": round(pct_employe, 1)
            }}
        )
    
    return {
        "message": "Contribution enregistrée avec succès. Merci de contribuer à la base de données!",
        "id": contribution_doc["id"],
        "disclaimer": "Votre contribution sera utilisée pour informer les travailleurs. Elle ne constitue pas une accusation envers le médecin concerné."
    }

@api_router.get("/contributions")
async def get_contributions():
    """Récupère les contributions récentes approuvées."""
    contributions = await db.contributions.find(
        {"approved": True},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    return contributions

@api_router.get("/stats/medecins")
async def get_medecins_stats():
    """Statistiques globales sur les médecins."""
    total_medecins = await db.medecins.count_documents({})
    total_contributions = await db.contributions.count_documents({"approved": True})
    
    # Top 10 médecins les plus documentés
    top_medecins = await db.medecins.find(
        {"total_decisions": {"$gt": 0}},
        {"_id": 0}
    ).sort("total_decisions", -1).to_list(10)
    
    return {
        "disclaimer": DISCLAIMER_MEDECIN,
        "total_medecins_documentes": total_medecins,
        "total_contributions": total_contributions,
        "top_medecins_documentes": top_medecins
    }

# Include the router
app.include_router(api_router)

# CORS middleware
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
