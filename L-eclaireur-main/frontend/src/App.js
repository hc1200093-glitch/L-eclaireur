import React, { useState, useCallback, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import { jsPDF } from "jspdf";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Composant Phare animé avec lumière correctement positionnée
const Lighthouse = () => (
  <div className="lighthouse-container">
    <svg viewBox="0 0 200 300" className="lighthouse">
      {/* Cône de lumière animé - intégré dans le SVG */}
      <defs>
        <linearGradient id="lightBeam" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#f4c430" stopOpacity="0.9" />
          <stop offset="40%" stopColor="#f4c430" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#f4c430" stopOpacity="0" />
        </linearGradient>
      </defs>
      
      {/* Cône de lumière qui part de la lanterne */}
      <g className="light-beam-svg">
        <path d="M115 70 L350 20 L350 120 Z" fill="url(#lightBeam)" opacity="0.7"/>
      </g>
      
      {/* Base du phare */}
      <path d="M60 280 L80 180 L120 180 L140 280 Z" fill="#1a3a4a" />
      <rect x="75" y="180" width="50" height="20" fill="#2a5a6a" />
      
      {/* Corps du phare - étages */}
      <rect x="78" y="140" width="44" height="40" fill="#e8e0d0" />
      <rect x="80" y="145" width="10" height="15" fill="#2a7d7d" opacity="0.7" />
      <rect x="95" y="145" width="10" height="15" fill="#2a7d7d" opacity="0.7" />
      <rect x="110" y="145" width="10" height="15" fill="#2a7d7d" opacity="0.7" />
      
      <rect x="75" y="130" width="50" height="10" fill="#1a3a4a" />
      
      <rect x="80" y="95" width="40" height="35" fill="#e8e0d0" />
      <rect x="85" y="100" width="8" height="12" fill="#2a7d7d" opacity="0.7" />
      <rect x="96" y="100" width="8" height="12" fill="#2a7d7d" opacity="0.7" />
      <rect x="107" y="100" width="8" height="12" fill="#2a7d7d" opacity="0.7" />
      
      <rect x="77" y="85" width="46" height="10" fill="#1a3a4a" />
      
      {/* Lanterne - source de lumière */}
      <rect x="82" y="55" width="36" height="30" fill="#2a5a6a" />
      <rect x="85" y="58" width="30" height="24" fill="#f4c430" opacity="0.95" />
      
      {/* Toit */}
      <polygon points="100,30 75,55 125,55" fill="#c0392b" />
      <rect x="95" y="20" width="10" height="15" fill="#1a3a4a" />
      
      {/* Balustrade */}
      <rect x="78" y="52" width="44" height="3" fill="#1a3a4a" />
    </svg>
  </div>
);

// Composant Mains unies - Image réelle style équipe volleyball
const UnityHands = () => (
  <div className="unity-hands-container">
    <img 
      src="https://images.unsplash.com/photo-1630068846062-3ffe78aa5049?w=600&q=80" 
      alt="Mains multiethniques unies ensemble" 
      className="unity-hands-image"
    />
  </div>
);

// Composant Compteur de visiteurs
const VisitorCounter = ({ count }) => (
  <div className="visitor-counter">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
    <span><strong>{count.toLocaleString()}</strong> travailleurs aidés</span>
  </div>
);

// Composant Boutons de partage
const ShareButtons = () => {
  const shareUrl = encodeURIComponent(window.location.href);
  const shareText = encodeURIComponent("L'Éclaireur - Un outil gratuit pour analyser vos documents CNESST et TAT. Très utile pour les travailleurs québécois!");
  
  return (
    <div className="share-section">
      <h4>Partagez L'Éclaireur</h4>
      <div className="share-buttons">
        <a href={`https://www.facebook.com/sharer/sharer.php?u=${shareUrl}`} target="_blank" rel="noopener noreferrer" className="share-btn facebook" title="Partager sur Facebook">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
        </a>
        <a href={`https://twitter.com/intent/tweet?url=${shareUrl}&text=${shareText}`} target="_blank" rel="noopener noreferrer" className="share-btn twitter" title="Partager sur X/Twitter">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
        </a>
        <a href={`https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`} target="_blank" rel="noopener noreferrer" className="share-btn linkedin" title="Partager sur LinkedIn">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>
        </a>
        <a href={`https://wa.me/?text=${shareText}%20${shareUrl}`} target="_blank" rel="noopener noreferrer" className="share-btn whatsapp" title="Partager sur WhatsApp">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
        </a>
        <button onClick={() => navigator.clipboard.writeText(window.location.href)} className="share-btn copy" title="Copier le lien">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
      </div>
    </div>
  );
};

// Composant Ko-fi
const KofiButton = () => (
  <div className="kofi-section">
    <h4>Soutenir L'Éclaireur</h4>
    <p>Aidez-nous à maintenir cet outil gratuit pour tous les travailleurs</p>
    <a 
      href="https://ko-fi.com/leclaireur?amount=5" 
      target="_blank" 
      rel="noopener noreferrer" 
      className="kofi-button"
      data-testid="kofi-btn"
    >
      <svg viewBox="0 0 24 24" fill="currentColor" className="kofi-icon">
        <path d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/>
      </svg>
      Offrir un café (5$)
    </a>
  </div>
);

// Composant Témoignages
const TestimonialsSection = ({ testimonials, onSubmit }) => {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [rating, setRating] = useState(5);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onSubmit({ name, message, rating });
    setSubmitted(true);
    setShowForm(false);
    setName('');
    setMessage('');
    setRating(5);
  };

  return (
    <section className="testimonials-section">
      <h3>Témoignages</h3>
      
      {testimonials.length > 0 ? (
        <div className="testimonials-grid">
          {testimonials.slice(0, 6).map((t, i) => (
            <div key={i} className="testimonial-card">
              <div className="testimonial-rating">
                {[...Array(5)].map((_, j) => (
                  <span key={j} className={j < t.rating ? 'star filled' : 'star'}>★</span>
                ))}
              </div>
              <p className="testimonial-message">"{t.message}"</p>
              <p className="testimonial-author">— {t.name}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="no-testimonials">Soyez le premier à laisser un témoignage!</p>
      )}

      {submitted && (
        <div className="testimonial-success">Merci pour votre témoignage!</div>
      )}

      {!showForm ? (
        <button className="btn btn-testimonial" onClick={() => setShowForm(true)}>
          Laisser un témoignage
        </button>
      ) : (
        <form className="testimonial-form" onSubmit={handleSubmit}>
          <input 
            type="text" 
            placeholder="Votre prénom" 
            value={name} 
            onChange={(e) => setName(e.target.value)}
            required 
            minLength={2}
            maxLength={50}
          />
          <textarea 
            placeholder="Votre témoignage..." 
            value={message} 
            onChange={(e) => setMessage(e.target.value)}
            required
            minLength={10}
            maxLength={500}
          />
          <div className="rating-input">
            <span>Note:</span>
            {[1,2,3,4,5].map(n => (
              <button 
                type="button" 
                key={n} 
                className={rating >= n ? 'star-btn filled' : 'star-btn'}
                onClick={() => setRating(n)}
              >★</button>
            ))}
          </div>
          <div className="form-buttons">
            <button type="submit" className="btn btn-primary">Envoyer</button>
            <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Annuler</button>
          </div>
        </form>
      )}
    </section>
  );
};

// Composant Section Médecins
const MedecinsSection = () => {
  const [medecins, setMedecins] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showContribForm, setShowContribForm] = useState(false);
  const [contribData, setContribData] = useState({ nom: '', prenom: '', type: 'pro_employeur', description: '', source: '' });
  const [submitMessage, setSubmitMessage] = useState('');
  const [disclaimer, setDisclaimer] = useState('');
  const [loading, setLoading] = useState(false);

  const searchMedecin = async () => {
    if (!searchTerm.trim()) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API}/medecins/search/${encodeURIComponent(searchTerm)}`);
      setMedecins(res.data.medecins);
      setDisclaimer(res.data.disclaimer);
    } catch (e) {
      console.error('Erreur recherche:', e);
      setMedecins([]);
    }
    setLoading(false);
  };

  // Charger tous les médecins au démarrage
  useEffect(() => {
    const loadAllMedecins = async () => {
      try {
        const res = await axios.get(`${API}/medecins`);
        if (res.data.medecins && res.data.medecins.length > 0) {
          setMedecins(res.data.medecins);
          setDisclaimer(res.data.disclaimer);
        }
      } catch (e) {
        console.error('Erreur chargement médecins:', e);
      }
    };
    loadAllMedecins();
  }, []);

  const submitContribution = async (e) => {
    e.preventDefault();
    setSubmitMessage('');
    try {
      const res = await axios.post(`${API}/contributions`, {
        medecin_nom: contribData.nom,
        medecin_prenom: contribData.prenom,
        type_contribution: contribData.type,
        description: contribData.description,
        source_reference: contribData.source || null
      });
      setSubmitMessage(res.data.message);
      setShowContribForm(false);
      setContribData({ nom: '', prenom: '', type: 'pro_employeur', description: '', source: '' });
      // Rafraîchir la recherche si on a un terme
      if (searchTerm) searchMedecin();
    } catch (e) {
      setSubmitMessage(e.response?.data?.detail || 'Erreur lors de la soumission');
    }
  };

  return (
    <section className="medecins-section">
      <h3>📋 Base de données des médecins experts</h3>
      
      <div className="disclaimer-box">
        <strong>⚖️ AVIS IMPORTANT</strong>
        <p>Les statistiques présentées sont compilées à partir de décisions publiques du TAT. Ces informations sont fournies <strong>À TITRE INFORMATIF SEULEMENT</strong> et ne constituent pas une accusation de partialité.</p>
      </div>

      <div className="tat-link-box">
        <p>📚 Consultez les décisions publiques du TAT pour vos recherches :</p>
        <a href="https://www.canlii.org/fr/qc/qctat/" target="_blank" rel="noopener noreferrer" className="tat-link">
          Jurisprudences TAT sur CanLII →
        </a>
        <a href="https://www.tat.gouv.qc.ca/nous-joindre/bureaux-regionaux/" target="_blank" rel="noopener noreferrer" className="tat-link secondary">
          Bureaux régionaux du TAT →
        </a>
      </div>

      <div className="search-medecin">
        <input
          type="text"
          placeholder="Rechercher un médecin (nom ou prénom)..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && searchMedecin()}
        />
        <button onClick={searchMedecin} className="btn btn-primary" disabled={loading}>
          {loading ? 'Recherche...' : 'Rechercher'}
        </button>
      </div>

      {medecins.length === 0 && !loading && (
        <div className="empty-db-notice">
          <p>🔍 <strong>La base de données se construit automatiquement</strong></p>
          <p>Chaque fois qu'un document est analysé, les médecins mentionnés sont automatiquement ajoutés avec leurs statistiques.</p>
          <p>Vous pouvez aussi contribuer manuellement en ajoutant des informations ci-dessous.</p>
        </div>
      )}

      {medecins.length > 0 && (
        <div className="medecins-grid">
          {medecins.map((m, i) => (
            <div key={i} className="medecin-card">
              <h4>Dr {m.prenom} {m.nom}</h4>
              {m.specialite && <p className="specialite">{m.specialite}</p>}
              {m.ville && <p className="ville">📍 {m.ville}</p>}
              {m.diplomes && <p className="diplomes">🎓 {m.diplomes}</p>}
              
              {m.total_decisions > 0 && (
                <div className="stats-medecin">
                  <p className="total-decisions">{m.total_decisions} décision(s) documentée(s)</p>
                  <div className="stats-bars">
                    <div className="stat-bar">
                      <span className="stat-label">Pro-employeur</span>
                      <div className="bar-container">
                        <div className="bar employeur" style={{width: `${m.pourcentage_pro_employeur}%`}}></div>
                      </div>
                      <span className="stat-pct">{m.pourcentage_pro_employeur}%</span>
                    </div>
                    <div className="stat-bar">
                      <span className="stat-label">Pro-employé</span>
                      <div className="bar-container">
                        <div className="bar employe" style={{width: `${m.pourcentage_pro_employe}%`}}></div>
                      </div>
                      <span className="stat-pct">{m.pourcentage_pro_employe}%</span>
                    </div>
                  </div>
                </div>
              )}
              
              {m.sources && m.sources.length > 0 && (
                <p className="sources">Sources: {m.sources.slice(0, 3).join(', ')}{m.sources.length > 3 ? '...' : ''}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {searchTerm && medecins.length === 0 && !loading && (
        <p className="no-results">Aucun médecin trouvé. Vous pouvez contribuer à enrichir la base de données.</p>
      )}

      {submitMessage && (
        <div className={submitMessage.includes('Erreur') ? 'message-error' : 'message-success'}>
          {submitMessage}
        </div>
      )}

      {!showContribForm ? (
        <button className="btn btn-contribute" onClick={() => setShowContribForm(true)}>
          ➕ Contribuer à la base de données
        </button>
      ) : (
        <form className="contribution-form" onSubmit={submitContribution}>
          <h4>Ajouter une information sur un médecin</h4>
          <p className="form-notice">⚠️ Seules les contributions factuelles et respectueuses sont acceptées. Tout contenu inapproprié sera rejeté.</p>
          
          <div className="form-row">
            <input
              type="text"
              placeholder="Nom du médecin"
              value={contribData.nom}
              onChange={(e) => setContribData({...contribData, nom: e.target.value})}
              required
              minLength={2}
            />
            <input
              type="text"
              placeholder="Prénom du médecin"
              value={contribData.prenom}
              onChange={(e) => setContribData({...contribData, prenom: e.target.value})}
              required
              minLength={2}
            />
          </div>
          
          <select
            value={contribData.type}
            onChange={(e) => setContribData({...contribData, type: e.target.value})}
            required
          >
            <option value="pro_employeur">Décision favorable à l'employeur</option>
            <option value="pro_employe">Décision favorable à l'employé</option>
            <option value="info_generale">Information générale</option>
          </select>
          
          <textarea
            placeholder="Description factuelle de la décision ou information (min. 20 caractères)..."
            value={contribData.description}
            onChange={(e) => setContribData({...contribData, description: e.target.value})}
            required
            minLength={20}
            maxLength={2000}
          />
          
          <input
            type="text"
            placeholder="Référence (optionnel): N° dossier TAT, date de décision..."
            value={contribData.source}
            onChange={(e) => setContribData({...contribData, source: e.target.value})}
          />
          
          <div className="form-buttons">
            <button type="submit" className="btn btn-primary">Soumettre</button>
            <button type="button" className="btn btn-secondary" onClick={() => setShowContribForm(false)}>Annuler</button>
          </div>
        </form>
      )}
    </section>
  );
};

// Page d'accueil
const HomePage = ({ onStartAnalysis }) => {
  const [visitorCount, setVisitorCount] = useState(0);
  const [testimonials, setTestimonials] = useState([]);

  useEffect(() => {
    // Charger le compteur et incrémenter
    const loadStats = async () => {
      try {
        await axios.post(`${API}/stats/visitors/increment`);
        const res = await axios.get(`${API}/stats/visitors`);
        setVisitorCount(res.data.count);
      } catch (e) {
        console.error('Erreur stats:', e);
      }
    };
    
    // Charger les témoignages
    const loadTestimonials = async () => {
      try {
        const res = await axios.get(`${API}/testimonials`);
        setTestimonials(res.data);
      } catch (e) {
        console.error('Erreur témoignages:', e);
      }
    };

    loadStats();
    loadTestimonials();
  }, []);

  const submitTestimonial = async (data) => {
    try {
      await axios.post(`${API}/testimonials`, data);
      const res = await axios.get(`${API}/testimonials`);
      setTestimonials(res.data);
    } catch (e) {
      console.error('Erreur soumission:', e);
    }
  };

  return (
  <div className="home-page">
    <header className="home-header">
      <Lighthouse />
      <div className="home-title-section">
        <h1 className="home-title">L'Éclaireur</h1>
        <p className="home-subtitle">Un outil d'aide pour les travailleurs québécois</p>
        <p className="home-credit">
          Créé sur une idée de <strong>Henri Albert Pertzing</strong> (accident le 31/12/2021)<br/>
          avec l'aide de <a href="https://emergent.sh" target="_blank" rel="noopener noreferrer">E1 par Emergent.sh</a>
        </p>
        <a href="mailto:pertzinghenrialbert@yahoo.ca" className="contact-btn" data-testid="contact-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
          Me contacter
        </a>
        <VisitorCounter count={visitorCount} />
      </div>
    </header>

    <main className="home-main">
      <section className="hero-section">
        <UnityHands />
        <div className="hero-content">
          <h2>Ensemble, comprendre vos droits</h2>
          <p>
            L'Éclaireur analyse vos documents CNESST, TAT et autres documents juridiques 
            liés aux accidents de travail et maladies professionnelles.
          </p>
          <div className="target-users">
            <div className="user-badge worker">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <span>Pour les travailleurs</span>
            </div>
            <div className="user-badge lawyer">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
                <path d="M9 12l2 2 4-4"/>
              </svg>
              <span>Pour les avocats</span>
            </div>
          </div>
          <p className="lawyer-note">
            <strong>Avocats :</strong> Cet outil vous permet de synthétiser rapidement des dossiers volumineux, 
            d'identifier les incohérences médicales et de consulter l'historique des médecins experts pour mieux défendre vos clients.
          </p>
          <button 
            className="btn btn-cta" 
            onClick={onStartAnalysis}
            data-testid="start-analysis-btn"
          >
            Commencer l'analyse
            <svg className="btn-icon-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </button>
        </div>
      </section>

      <section className="features-section">
        <h3>Comment ça marche ?</h3>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <h4>1. Téléversez</h4>
            <p>Déposez votre document PDF (décision, rapport médical, formulaire...)</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <h4>2. Analyse IA</h4>
            <p>Notre intelligence artificielle analyse et résume les points clés</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <h4>3. Anonymisation</h4>
            <p>Vos données sensibles (NAS, adresses, noms) sont automatiquement masquées</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </div>
            <h4>4. Téléchargez</h4>
            <p>Récupérez votre rapport en PDF, Word, TXT, HTML ou RTF</p>
          </div>
        </div>
      </section>

      <section className="trust-section">
        <div className="trust-badge">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <span>Sécurité DOD 5220.22-M</span>
        </div>
        <p>Tous les documents sont automatiquement détruits après analyse</p>
      </section>

      <TestimonialsSection testimonials={testimonials} onSubmit={submitTestimonial} />

      <MedecinsSection />

      <div className="support-section">
        <ShareButtons />
        <KofiButton />
      </div>
    </main>

    <footer className="footer">
      <nav className="footer-links">
        <a href="https://www.cnesst.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">CNESST</a>
        <a href="https://www.tat.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">TAT</a>
        <a href="https://www.barreau.qc.ca/fr/trouver-avocat/" target="_blank" rel="noopener noreferrer">Trouver un avocat</a>
        <a href="https://www.cmq.org/" target="_blank" rel="noopener noreferrer">Collège des médecins</a>
      </nav>
      <p className="footer-copyright">© 2026 L'Éclaireur - Un outil d'aide pour les travailleurs québécois</p>
      <p className="footer-powered">
        Propulsé par <a href="https://emergent.sh" target="_blank" rel="noopener noreferrer">E1 by Emergent</a> & Google Gemini
      </p>
      <p className="footer-disclaimer">Cet outil ne remplace pas les conseils d'un professionnel qualifié.</p>
    </footer>
  </div>
  );
};

// Page d'analyse
const AnalysisPage = ({ onBackHome }) => {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [downloadFormat, setDownloadFormat] = useState("pdf");

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setError(null);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
        setResult(null);
      } else {
        setError("Seuls les fichiers PDF sont acceptés");
      }
    }
  }, []);

  const handleFileSelect = (e) => {
    setError(null);
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type === "application/pdf") {
        setFile(selectedFile);
        setResult(null);
      } else {
        setError("Seuls les fichiers PDF sont acceptés");
      }
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/analyze`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 1800000,
      });
      
      setResult(response.data);
    } catch (err) {
      console.error("Erreur:", err);
      if (err.response?.data?.detail) {
        setError(`Erreur lors de l'analyse: ${err.response.data.detail}`);
      } else if (err.code === "ECONNABORTED") {
        setError("L'analyse a pris trop de temps. Veuillez réessayer.");
      } else {
        setError("Une erreur est survenue. Veuillez réessayer.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " octets";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " Ko";
    return (bytes / (1024 * 1024)).toFixed(2) + " Mo";
  };

  const handleDownload = async () => {
    if (!result) return;
    
    const filename = file?.name?.replace('.pdf', '') || 'rapport_analyse';
    const content = result.analysis;
    const title = `Rapport d'Analyse - ${filename}`;
    const date = new Date().toLocaleDateString('fr-CA');
    
    switch (downloadFormat) {
      case 'pdf': downloadAsPDF(content, title, filename, date); break;
      case 'docx': await downloadAsDOCX(content, title, filename, date); break;
      case 'txt': downloadAsTXT(content, title, filename, date); break;
      case 'html': downloadAsHTML(content, title, filename, date); break;
      case 'rtf': downloadAsRTF(content, title, filename, date); break;
      default: downloadAsPDF(content, title, filename, date);
    }
  };

  const downloadAsPDF = (content, title, filename, date) => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    const maxWidth = pageWidth - 2 * margin;
    
    doc.setFontSize(18);
    doc.setFont("helvetica", "bold");
    doc.text(title, margin, 20);
    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    doc.text(`Généré le: ${date}`, margin, 30);
    doc.setLineWidth(0.5);
    doc.line(margin, 35, pageWidth - margin, 35);
    doc.setFontSize(11);
    const lines = doc.splitTextToSize(content, maxWidth);
    let y = 45;
    lines.forEach((line) => {
      if (y > 280) { doc.addPage(); y = 20; }
      doc.text(line, margin, y);
      y += 6;
    });
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.text(`L'Éclaireur - Page ${i}/${pageCount}`, pageWidth / 2, 290, { align: 'center' });
    }
    doc.save(`${filename}_rapport.pdf`);
  };

  const downloadAsDOCX = async (content, title, filename, date) => {
    const doc = new Document({
      sections: [{
        properties: {},
        children: [
          new Paragraph({ text: title, heading: HeadingLevel.HEADING_1 }),
          new Paragraph({ children: [new TextRun({ text: `Généré le: ${date}`, italics: true, size: 20 })] }),
          new Paragraph({ text: "" }),
          ...content.split('\n').map(line => new Paragraph({ children: [new TextRun({ text: line, size: 22 })] })),
          new Paragraph({ text: "" }),
          new Paragraph({ children: [new TextRun({ text: "— Généré par L'Éclaireur", italics: true, size: 18 })] }),
        ],
      }],
    });
    const blob = await Packer.toBlob(doc);
    saveAs(blob, `${filename}_rapport.docx`);
  };

  const downloadAsTXT = (content, title, filename, date) => {
    const text = `${title}\nGénéré le: ${date}\n${'='.repeat(50)}\n\n${content}\n\n${'='.repeat(50)}\nGénéré par L'Éclaireur`;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    saveAs(blob, `${filename}_rapport.txt`);
  };

  const downloadAsHTML = (content, title, filename, date) => {
    const html = `<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>${title}</title><style>body{font-family:'Segoe UI',Arial,sans-serif;max-width:800px;margin:0 auto;padding:40px 20px;line-height:1.6;color:#333}h1{color:#2a7d7d;border-bottom:3px solid #c9a227;padding-bottom:10px}.date{color:#666;font-style:italic}.content{background:#f5f5f5;padding:20px;border-radius:8px;white-space:pre-wrap}.footer{margin-top:30px;text-align:center;color:#888}</style></head><body><h1>${title}</h1><p class="date">Généré le: ${date}</p><div class="content">${content.replace(/\n/g, '<br>')}</div><p class="footer">Généré par L'Éclaireur</p></body></html>`;
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    saveAs(blob, `${filename}_rapport.html`);
  };

  const downloadAsRTF = (content, title, filename, date) => {
    // Convertir les accents français en codes RTF
    const encodeRTF = (text) => {
      return text
        .replace(/é/g, "\\'e9")
        .replace(/è/g, "\\'e8")
        .replace(/ê/g, "\\'ea")
        .replace(/ë/g, "\\'eb")
        .replace(/à/g, "\\'e0")
        .replace(/â/g, "\\'e2")
        .replace(/ù/g, "\\'f9")
        .replace(/û/g, "\\'fb")
        .replace(/ô/g, "\\'f4")
        .replace(/î/g, "\\'ee")
        .replace(/ï/g, "\\'ef")
        .replace(/ç/g, "\\'e7")
        .replace(/É/g, "\\'c9")
        .replace(/È/g, "\\'c8")
        .replace(/Ê/g, "\\'ca")
        .replace(/À/g, "\\'c0")
        .replace(/Ç/g, "\\'c7")
        .replace(/\n/g, '\\par ');
    };
    const rtfContent = encodeRTF(content);
    const rtfTitle = encodeRTF(title);
    const rtf = `{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0 Arial;}}{\\b\\fs36 ${rtfTitle}}\\par{\\i\\fs20 G\\'e9n\\'e9r\\'e9 le: ${date}}\\par\\par{\\fs22 ${rtfContent}}\\par\\par{\\i\\fs18 — G\\'e9n\\'e9r\\'e9 par L\\'\\'c9claireur}}`;
    const blob = new Blob([rtf], { type: 'application/rtf' });
    saveAs(blob, `${filename}_rapport.rtf`);
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <svg viewBox="0 0 100 100" className="sun-icon">
              <circle cx="50" cy="50" r="20" fill="#f4c430"/>
              {[...Array(12)].map((_, i) => (
                <line key={i} x1="50" y1="15" x2="50" y2="5" stroke="#f4c430" strokeWidth="3" transform={`rotate(${i * 30} 50 50)`}/>
              ))}
            </svg>
          </div>
          <h1 className="title">Analyse de document</h1>
        </div>
        <button onClick={onBackHome} className="back-link">← Retour à l'accueil</button>
      </header>

      <div className="divider"></div>

      <main className="main-content">
        <div 
          className={`upload-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          {!file ? (
            <div className="upload-placeholder">
              <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              <p className="upload-text">Glissez-déposez votre PDF ici</p>
              <p className="upload-subtext">ou</p>
              <label className="file-select-btn">
                <input type="file" accept=".pdf,application/pdf" onChange={handleFileSelect} hidden data-testid="file-input"/>
                Sélectionner un fichier
              </label>
              <p className="upload-hint">Formats acceptés: PDF (max 100 Mo)</p>
            </div>
          ) : (
            <div className="file-info">
              <svg className="file-icon" viewBox="0 0 24 24" fill="none" stroke="#2a7d7d" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              <p className="file-name" data-testid="file-name">{file.name}</p>
              <p className="file-size">{formatFileSize(file.size)}</p>
            </div>
          )}
        </div>

        {file && (
          <div className="action-buttons">
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading} data-testid="analyze-btn">
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              {loading ? "Analyse en cours..." : "Analyser le document"}
            </button>
            <button className="btn btn-secondary" onClick={handleCancel} disabled={loading} data-testid="cancel-btn">
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
              Annuler
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-container" data-testid="loading-indicator">
            <div className="loading-spinner"></div>
            <p className="loading-text">Analyse du document en cours...</p>
            <p className="loading-subtext">Votre document de {(file?.size / (1024*1024)).toFixed(1)} Mo est en cours de traitement.<br/>Les gros documents sont segmentés et analysés partie par partie.<br/><strong>Cela peut prendre plusieurs minutes, merci de patienter.</strong></p>
          </div>
        )}

        {error && (
          <div className="error-container" data-testid="error-message">
            <svg className="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <p className="error-text">{error}</p>
            <button className="btn btn-retry" onClick={handleAnalyze} data-testid="retry-btn">Réessayer</button>
          </div>
        )}

        {result && (
          <div className="result-container" data-testid="analysis-result">
            <div className="result-header">
              <svg className="result-icon" viewBox="0 0 24 24" fill="none" stroke="#2a7d7d" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <h2>Analyse complétée</h2>
            </div>
            <div className="result-content">
              <pre className="analysis-text">{result.analysis}</pre>
            </div>
            <div className="download-section" data-testid="download-section">
              <h3>Télécharger le rapport</h3>
              <div className="download-controls">
                <select value={downloadFormat} onChange={(e) => setDownloadFormat(e.target.value)} className="format-select" data-testid="format-select">
                  <option value="pdf">PDF (.pdf)</option>
                  <option value="docx">Word (.docx)</option>
                  <option value="txt">Texte (.txt)</option>
                  <option value="html">HTML (.html)</option>
                  <option value="rtf">RTF (.rtf)</option>
                </select>
                <button className="btn btn-download" onClick={handleDownload} data-testid="download-btn">
                  <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Télécharger
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="security-note">
          <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="#c9a227" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <div>
            <strong>Sécurité garantie :</strong> Tous les documents téléversés sont automatiquement détruits selon les normes DOD 5220.22-M après l'analyse. <strong>Toutes les informations sensibles sont automatiquement anonymisées.</strong>
          </div>
        </div>
      </main>

      <footer className="footer">
        <nav className="footer-links">
          <a href="https://www.cnesst.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">CNESST</a>
          <a href="https://www.tat.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">TAT</a>
          <a href="https://www.barreau.qc.ca/fr/trouver-avocat/" target="_blank" rel="noopener noreferrer">Trouver un avocat</a>
          <a href="https://www.cmq.org/" target="_blank" rel="noopener noreferrer">Collège des médecins</a>
        </nav>
        <p className="footer-copyright">© 2026 L'Éclaireur - Un outil d'aide pour les travailleurs québécois</p>
        <p className="footer-powered">Propulsé par <a href="https://emergent.sh" target="_blank" rel="noopener noreferrer">E1 by Emergent</a> & Google Gemini</p>
        <p className="footer-disclaimer">Cet outil ne remplace pas les conseils d'un professionnel qualifié.</p>
      </footer>

      <div className="emergent-badge">
        <img src="https://avatars.githubusercontent.com/in/1201222?s=120" alt="Emergent" />
        Made with Emergent
      </div>
    </div>
  );
};

// App principale
function App() {
  const [currentPage, setCurrentPage] = useState("home");

  return currentPage === "home" 
    ? <HomePage onStartAnalysis={() => setCurrentPage("analysis")} />
    : <AnalysisPage onBackHome={() => setCurrentPage("home")} />;
}

export default App;
