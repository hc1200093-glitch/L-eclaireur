import React, { useState, useCallback, useEffect, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { jsPDF } from "jspdf";
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ===== COMPOSANT POPUP MENTIONS LÉGALES =====
const LegalPopup = ({ onAccept }) => {
  const [consent1, setConsent1] = useState(false);
  const [consent2, setConsent2] = useState(false);

  const canProceed = consent1;

  return (
    <div className="legal-popup-overlay" data-testid="legal-popup">
      <div className="legal-popup">
        <div className="legal-popup-header">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <h2>Mentions légales et consentement</h2>
        </div>

        <div className="legal-popup-content">
          <div className="legal-section">
            <h3>Nature du service</h3>
            <p>
              L'Éclaireur est un <strong>outil d'aide à la compréhension</strong> utilisant l'intelligence artificielle 
              pour analyser et synthétiser des documents juridiques et médicaux liés aux accidents de travail au Québec.
            </p>
            <p className="legal-warning">
              <strong>Ce rapport NE CONSTITUE PAS un avis juridique ou médical professionnel.</strong> 
              Il ne remplace en aucun cas la consultation d'un avocat, d'un médecin ou de tout autre professionnel qualifié.
            </p>
          </div>

          <div className="legal-section">
            <h3>Confidentialité et sécurité</h3>
            <ul>
              <li><strong>Aucune copie n'est conservée</strong> par Henri Albert Pertzing ni sur ce site.</li>
              <li>Tous les documents sont <strong>détruits de manière sécurisée</strong> selon la norme DOD 5220.22-M après l'analyse.</li>
              <li>Les données ultra-sensibles (NAS, RAMQ, permis de conduire, coordonnées bancaires) sont <strong>automatiquement masquées</strong> dans le rapport.</li>
            </ul>
          </div>

          <div className="legal-section">
            <h3>Utilisation du rapport</h3>
            <p>
              Ce rapport est destiné <strong>UNIQUEMENT</strong> à être utilisé dans le cadre juridique de votre dossier:
            </p>
            <ul>
              <li>Tribunal administratif du travail (TAT)</li>
              <li>CNESST</li>
              <li>Votre avocat ou représentant syndical</li>
              <li>Vous-même pour mieux comprendre votre situation</li>
            </ul>
            <p className="legal-warning">
              Ce rapport <strong>NE DOIT PAS</strong> être partagé avec des amis, famille ou toute personne 
              en dehors du cadre juridique de votre dossier.
            </p>
            <p>
              Il peut être déposé en « combiné défense » avant l'audience TAT pour en faire copie 
              pour toutes les parties en présence, selon les règles du TAT.
            </p>
          </div>

          <div className="legal-section">
            <h3>Ressources professionnelles</h3>
            <p>Consultez toujours un professionnel qualifié:</p>
            <div className="legal-links">
              <a href="https://www.justice.gouv.qc.ca/aide-juridique/" target="_blank" rel="noopener noreferrer">Aide juridique Québec</a>
              <a href="https://www.barreau.qc.ca/fr/trouver-avocat/" target="_blank" rel="noopener noreferrer">Trouver un avocat</a>
              <a href="https://www.tat.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">TAT</a>
              <a href="https://www.cnesst.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">CNESST</a>
            </div>
          </div>

          <div className="consent-checkboxes">
            <label className="consent-checkbox">
              <input
                type="checkbox"
                checked={consent1}
                onChange={(e) => setConsent1(e.target.checked)}
                data-testid="consent-checkbox-1"
              />
              <span>
                <strong>Je comprends</strong> que ce rapport est un outil d'aide généré par IA et 
                qu'il ne remplace pas l'avis d'un professionnel qualifié (avocat, médecin).
              </span>
            </label>

            <label className="consent-checkbox">
              <input
                type="checkbox"
                checked={consent2}
                onChange={(e) => setConsent2(e.target.checked)}
                data-testid="consent-checkbox-2"
              />
              <span>
                <strong>Je consens</strong> à ce que mon dossier soit utilisé de manière 
                <strong> totalement anonymisée</strong> (sans aucune donnée personnelle identifiable) 
                pour améliorer l'apprentissage des IA. <em>(Optionnel)</em>
              </span>
            </label>
          </div>
        </div>

        <div className="legal-popup-footer">
          <button
            className="btn btn-legal-accept"
            onClick={() => onAccept(consent2)}
            disabled={!canProceed}
            data-testid="accept-legal-btn"
          >
            J'accepte les conditions et je continue
          </button>
        </div>
      </div>
    </div>
  );
};

// ===== POPUP DESTRUCTION CONFIRMÉE =====
const DestructionPopup = ({ onClose }) => (
  <div className="destruction-popup-overlay" data-testid="destruction-popup">
    <div className="destruction-popup">
      <div className="destruction-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      </div>
      <h3>Documents détruits de manière sécurisée</h3>
      <p>
        Vos documents ont été <strong>définitivement détruits</strong> selon la norme militaire 
        <strong> DOD 5220.22-M</strong> (3 passes d'écrasement).
      </p>
      <p className="destruction-note">
        Pour effectuer une nouvelle analyse, vous devrez déposer à nouveau vos documents.
      </p>
      <button className="btn btn-primary" onClick={onClose} data-testid="close-destruction-btn">
        Compris
      </button>
    </div>
  </div>
);

// ===== COMPOSANT PHARE ANIMÉ =====
const Lighthouse = () => (
  <div className="lighthouse-container">
    <svg viewBox="0 0 200 300" className="lighthouse">
      <defs>
        <linearGradient id="lightBeam" x1="0%" y1="50%" x2="100%" y2="50%">
          <stop offset="0%" stopColor="#f4c430" stopOpacity="0.9" />
          <stop offset="40%" stopColor="#f4c430" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#f4c430" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g className="light-beam-svg">
        <path d="M115 70 L350 20 L350 120 Z" fill="url(#lightBeam)" opacity="0.7"/>
      </g>
      <path d="M60 280 L80 180 L120 180 L140 280 Z" fill="#1a3a4a" />
      <rect x="75" y="180" width="50" height="20" fill="#2a5a6a" />
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
      <rect x="82" y="55" width="36" height="30" fill="#2a5a6a" />
      <rect x="85" y="58" width="30" height="24" fill="#f4c430" opacity="0.95" />
      <polygon points="100,30 75,55 125,55" fill="#c0392b" />
      <rect x="95" y="20" width="10" height="15" fill="#1a3a4a" />
      <rect x="78" y="52" width="44" height="3" fill="#1a3a4a" />
    </svg>
  </div>
);

// ===== COMPOSANT MAINS UNIES =====
const UnityHands = () => (
  <div className="unity-hands-container">
    <img 
      src="https://images.unsplash.com/photo-1630068846062-3ffe78aa5049?w=600&q=80" 
      alt="Mains multiethniques unies ensemble" 
      className="unity-hands-image"
    />
  </div>
);

// ===== COMPTEUR DE VISITEURS =====
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

// ===== COMPTEUR DE TÉMOIGNAGES =====
const TestimonialCounter = ({ count, averageRating }) => (
  <div className="testimonial-counter">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
    <span>
      <strong>{count}</strong> témoignage{count > 1 ? 's' : ''} positif{count > 1 ? 's' : ''}
      {averageRating > 0 && (
        <span className="average-rating">
          <span className="star-small">★</span> {averageRating.toFixed(1)}/5
        </span>
      )}
    </span>
  </div>
);

// ===== PETITS BOUTONS DE SUPPORT (Ko-fi, PayPal, Stripe à venir) =====
const SupportIconsSmall = () => (
  <div className="support-icons-small">
    <span className="support-text">Pour améliorer l'appli et tenir le site à jour:</span>
    <div className="support-icons">
      <a 
        href="https://ko-fi.com/leclaireur" 
        target="_blank" 
        rel="noopener noreferrer" 
        className="support-icon-btn kofi"
        title="Soutenir sur Ko-fi"
        data-testid="kofi-small-btn"
      >
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/>
        </svg>
      </a>
      <span className="coming-soon-icons">
        <span className="icon-placeholder" title="PayPal (à venir)">
          <svg viewBox="0 0 24 24" fill="currentColor" opacity="0.4">
            <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106z"/>
          </svg>
        </span>
        <span className="icon-placeholder" title="Stripe (à venir)">
          <svg viewBox="0 0 24 24" fill="currentColor" opacity="0.4">
            <path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-6.99-2.109l-.9 5.555C5.175 22.99 8.385 24 11.714 24c2.641 0 4.843-.624 6.328-1.813 1.664-1.305 2.525-3.236 2.525-5.732 0-4.128-2.524-5.851-6.591-7.305z"/>
          </svg>
        </span>
      </span>
    </div>
  </div>
);

// ===== BOUTONS DE PARTAGE =====
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
        <button onClick={() => {navigator.clipboard.writeText(window.location.href); alert('Lien copié!');}} className="share-btn copy" title="Copier le lien">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
      </div>
    </div>
  );
};

// ===== BOUTON KO-FI GRAND =====
const KofiButton = () => (
  <div className="kofi-section">
    <h4>Soutenir L'Éclaireur</h4>
    <p>Aidez-nous à maintenir cet outil gratuit pour tous les travailleurs</p>
    <a href="https://ko-fi.com/leclaireur?amount=5" target="_blank" rel="noopener noreferrer" className="kofi-button" data-testid="kofi-btn">
      <svg viewBox="0 0 24 24" fill="currentColor" className="kofi-icon">
        <path d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/>
      </svg>
      Offrir un café (5$)
    </a>
  </div>
);

// ===== FLÈCHES DE NAVIGATION =====
const NavigationArrows = ({ testimonialsRef }) => {
  const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });
  const scrollToBottom = () => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  const scrollToTestimonials = () => testimonialsRef.current?.scrollIntoView({ behavior: 'smooth' });

  return (
    <div className="navigation-arrows" data-testid="nav-arrows">
      <button onClick={scrollToTop} className="nav-arrow-btn" title="Haut de page">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="18 15 12 9 6 15"/>
        </svg>
      </button>
      <button onClick={scrollToTestimonials} className="nav-arrow-btn testimonials-btn" title="Voir les témoignages">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </button>
      <button onClick={scrollToBottom} className="nav-arrow-btn" title="Bas de page">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
    </div>
  );
};

// ===== SECTION TÉMOIGNAGES =====
const TestimonialsSection = React.forwardRef(({ testimonials, onSubmit }, ref) => {
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
    setName(''); setMessage(''); setRating(5);
  };

  return (
    <section className="testimonials-section" ref={ref} id="testimonials">
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

      {submitted && <div className="testimonial-success">Merci pour votre témoignage!</div>}

      {!showForm ? (
        <button className="btn btn-testimonial" onClick={() => setShowForm(true)}>Laisser un témoignage</button>
      ) : (
        <form className="testimonial-form" onSubmit={handleSubmit}>
          <input type="text" placeholder="Votre prénom" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={50}/>
          <textarea placeholder="Votre témoignage..." value={message} onChange={(e) => setMessage(e.target.value)} required minLength={10} maxLength={500}/>
          <div className="rating-input">
            <span>Note:</span>
            {[1,2,3,4,5].map(n => (
              <button type="button" key={n} className={rating >= n ? 'star-btn filled' : 'star-btn'} onClick={() => setRating(n)}>★</button>
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
});

// ===== SECTION MÉDECINS =====
const MedecinsSection = () => {
  const [medecins, setMedecins] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showContribForm, setShowContribForm] = useState(false);
  const [contribData, setContribData] = useState({ nom: '', prenom: '', type: 'pro_employeur', description: '', source: '' });
  const [submitMessage, setSubmitMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const searchMedecin = async () => {
    if (!searchTerm.trim()) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API}/medecins/search/${encodeURIComponent(searchTerm)}`);
      setMedecins(res.data.medecins);
    } catch (e) { setMedecins([]); }
    setLoading(false);
  };

  useEffect(() => {
    const loadAllMedecins = async () => {
      try {
        const res = await axios.get(`${API}/medecins`);
        if (res.data.medecins?.length > 0) setMedecins(res.data.medecins);
      } catch (e) {}
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
      if (searchTerm) searchMedecin();
    } catch (e) {
      setSubmitMessage(e.response?.data?.detail || 'Erreur lors de la soumission');
    }
  };

  return (
    <section className="medecins-section">
      <h3>Base de données des médecins experts</h3>
      
      <div className="disclaimer-box">
        <strong>AVIS IMPORTANT</strong>
        <p>Les statistiques sont compilées à partir de décisions publiques du TAT. Ces informations sont fournies <strong>À TITRE INFORMATIF SEULEMENT</strong>.</p>
      </div>

      <div className="tat-link-box">
        <p>Consultez les décisions publiques et dossiers disciplinaires:</p>
        <a href="https://www.canlii.org/fr/qc/qctat/" target="_blank" rel="noopener noreferrer" className="tat-link">Jurisprudences TAT (CanLII)</a>
        <a href="https://www.cmq.org/fr/proteger-le-public/suivre-dossier-disciplinaire/decisions-disciplinaires" target="_blank" rel="noopener noreferrer" className="tat-link cmq">Décisions disciplinaires (CMQ)</a>
        <a href="https://www.quebecmedecin.com/" target="_blank" rel="noopener noreferrer" className="tat-link">Québec Médecin (Recherche)</a>
        <a href="https://soquij.qc.ca/" target="_blank" rel="noopener noreferrer" className="tat-link secondary">SOQUIJ</a>
      </div>

      <div className="search-medecin">
        <input type="text" placeholder="Rechercher un médecin (nom ou prénom)..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && searchMedecin()}/>
        <button onClick={searchMedecin} className="btn btn-primary" disabled={loading}>{loading ? 'Recherche...' : 'Rechercher'}</button>
      </div>

      {medecins.length === 0 && !loading && (
        <div className="empty-db-notice">
          <p><strong>La base de données se construit automatiquement</strong></p>
          <p>Chaque document analysé enrichit la base. Vous pouvez aussi contribuer manuellement.</p>
        </div>
      )}

      {medecins.length > 0 && (
        <div className="medecins-grid">
          {medecins.map((m, i) => (
            <div key={i} className="medecin-card">
              <h4>Dr {m.prenom} {m.nom}</h4>
              {m.specialite && <p className="specialite">{m.specialite}</p>}
              {m.ville && <p className="ville">{m.ville}</p>}
              {m.total_decisions > 0 && (
                <div className="stats-medecin">
                  <p className="total-decisions">{m.total_decisions} décision(s) documentée(s)</p>
                  <div className="stats-bars">
                    <div className="stat-bar">
                      <span className="stat-label">Pro-employeur</span>
                      <div className="bar-container"><div className="bar employeur" style={{width: `${m.pourcentage_pro_employeur}%`}}></div></div>
                      <span className="stat-pct">{m.pourcentage_pro_employeur}%</span>
                    </div>
                    <div className="stat-bar">
                      <span className="stat-label">Pro-employé</span>
                      <div className="bar-container"><div className="bar employe" style={{width: `${m.pourcentage_pro_employe}%`}}></div></div>
                      <span className="stat-pct">{m.pourcentage_pro_employe}%</span>
                    </div>
                  </div>
                  <a href={`https://www.cmq.org/fr/proteger-le-public/suivre-dossier-disciplinaire/decisions-disciplinaires`} target="_blank" rel="noopener noreferrer" className="verify-cmq-link">Vérifier au CMQ</a>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {submitMessage && <div className={submitMessage.includes('Erreur') ? 'message-error' : 'message-success'}>{submitMessage}</div>}

      {!showContribForm ? (
        <button className="btn btn-contribute" onClick={() => setShowContribForm(true)}>Contribuer à la base de données</button>
      ) : (
        <form className="contribution-form" onSubmit={submitContribution}>
          <h4>Ajouter une information sur un médecin</h4>
          <p className="form-notice">Seules les contributions factuelles et respectueuses sont acceptées.</p>
          <div className="form-row">
            <input type="text" placeholder="Nom du médecin" value={contribData.nom} onChange={(e) => setContribData({...contribData, nom: e.target.value})} required minLength={2}/>
            <input type="text" placeholder="Prénom du médecin" value={contribData.prenom} onChange={(e) => setContribData({...contribData, prenom: e.target.value})} required minLength={2}/>
          </div>
          <select value={contribData.type} onChange={(e) => setContribData({...contribData, type: e.target.value})} required>
            <option value="pro_employeur">Décision favorable à l'employeur</option>
            <option value="pro_employe">Décision favorable à l'employé</option>
            <option value="info_generale">Information générale</option>
          </select>
          <textarea placeholder="Description factuelle (min. 20 caractères)..." value={contribData.description} onChange={(e) => setContribData({...contribData, description: e.target.value})} required minLength={20} maxLength={2000}/>
          <input type="text" placeholder="Référence (optionnel): N° dossier TAT, date..." value={contribData.source} onChange={(e) => setContribData({...contribData, source: e.target.value})}/>
          <div className="form-buttons">
            <button type="submit" className="btn btn-primary">Soumettre</button>
            <button type="button" className="btn btn-secondary" onClick={() => setShowContribForm(false)}>Annuler</button>
          </div>
        </form>
      )}
    </section>
  );
};

// ===== PAGE D'ACCUEIL =====
const HomePage = ({ onStartAnalysis }) => {
  const [visitorCount, setVisitorCount] = useState(0);
  const [testimonials, setTestimonials] = useState([]);
  const [testimonialStats, setTestimonialStats] = useState({ count: 0, averageRating: 0 });
  const [darkMode, setDarkMode] = useState(false);
  const testimonialsRef = useRef(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        await axios.post(`${API}/stats/visitors/increment`);
        const res = await axios.get(`${API}/stats/visitors`);
        setVisitorCount(res.data.count);
      } catch (e) {}
    };
    const loadTestimonials = async () => {
      try {
        const res = await axios.get(`${API}/testimonials`);
        setTestimonials(res.data);
        // Calculer les stats des témoignages
        if (res.data.length > 0) {
          const positiveTestimonials = res.data.filter(t => t.rating >= 4);
          const totalRating = res.data.reduce((sum, t) => sum + t.rating, 0);
          const avgRating = totalRating / res.data.length;
          setTestimonialStats({
            count: positiveTestimonials.length,
            averageRating: avgRating
          });
        }
      } catch (e) {}
    };
    loadStats();
    loadTestimonials();
  }, []);

  const submitTestimonial = async (data) => {
    try {
      await axios.post(`${API}/testimonials`, data);
      const res = await axios.get(`${API}/testimonials`);
      setTestimonials(res.data);
    } catch (e) {}
  };

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.body.classList.toggle('dark-mode');
  };

  return (
    <div className={`home-page ${darkMode ? 'dark' : ''}`}>
      <button className="dark-mode-toggle" onClick={toggleDarkMode} title={darkMode ? 'Mode clair' : 'Mode sombre'} data-testid="dark-mode-btn">
        {darkMode ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        )}
      </button>

      <NavigationArrows testimonialsRef={testimonialsRef} />

      <header className="home-header">
        <Lighthouse />
        <div className="home-title-section">
          <h1 className="home-title">L'Éclaireur</h1>
          <p className="home-subtitle">Un outil d'aide pour les travailleurs québécois</p>
          <p className="home-credit">
            Créé sur une idée de <strong>Henri Albert Pertzing</strong> (accident le 31/12/2021)<br/>
            avec l'aide de <a href="https://emergent.sh" target="_blank" rel="noopener noreferrer">E1 par Emergent.sh</a>
          </p>
          
          <SupportIconsSmall />
          
          <div className="contact-email">
            <p>Pour toutes idées d'amélioration, laissez des commentaires constructifs:</p>
            <a href="mailto:pertzinghenrialbert@yahoo.ca" data-testid="email-link">pertzinghenrialbert@yahoo.ca</a>
            <p className="no-hate-notice">(La haine et la violence ne seront jamais acceptées)</p>
          </div>
          
          <VisitorCounter count={visitorCount} />
          <TestimonialCounter count={testimonialStats.count} averageRating={testimonialStats.averageRating} />
        </div>
      </header>

      <main className="home-main">
        <section className="hero-section">
          <UnityHands />
          <div className="hero-content">
            <h2>Ensemble, comprendre vos droits</h2>
            <p>L'Éclaireur analyse vos documents CNESST, TAT et autres documents juridiques liés aux accidents de travail.</p>
            <div className="target-users">
              <div className="user-badge worker">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <span>Pour les travailleurs</span>
              </div>
              <div className="user-badge lawyer">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>
                <span>Pour les avocats</span>
              </div>
            </div>
            <p className="lawyer-note">
              <strong>Avocats:</strong> Synthétisez rapidement des dossiers volumineux, identifiez les incohérences médicales et consultez l'historique des médecins experts.
            </p>
            <button className="btn btn-cta" onClick={onStartAnalysis} data-testid="start-analysis-btn">
              Commencer l'analyse
              <svg className="btn-icon-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
          </div>
        </section>

        <section className="features-section">
          <h3>Comment ça marche?</h3>
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
              <h4>1. Téléversez</h4>
              <p>Déposez votre document PDF</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg></div>
              <h4>2. Analyse IA</h4>
              <p>Notre IA analyse et résume les points clés</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
              <h4>3. Anonymisation</h4>
              <p>NAS, RAMQ et coordonnées bancaires masqués</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></div>
              <h4>4. Téléchargez</h4>
              <p>Récupérez votre rapport défense</p>
            </div>
          </div>
        </section>

        <section className="trust-section">
          <div className="trust-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            <span>Sécurité DOD 5220.22-M</span>
          </div>
          <p>Tous les documents sont détruits de manière sécurisée après analyse</p>
        </section>

        <TestimonialsSection ref={testimonialsRef} testimonials={testimonials} onSubmit={submitTestimonial} />

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
          <a href="https://www.justice.gouv.qc.ca/aide-juridique/" target="_blank" rel="noopener noreferrer">Aide juridique</a>
          <a href="https://www.cmq.org/" target="_blank" rel="noopener noreferrer">Collège des médecins</a>
          <a href="https://soquij.qc.ca/" target="_blank" rel="noopener noreferrer">SOQUIJ</a>
        </nav>
        
        <div className="footer-contact">
          <p>Pour toutes idées d'amélioration: <a href="mailto:pertzinghenrialbert@yahoo.ca">pertzinghenrialbert@yahoo.ca</a></p>
          <p className="no-hate-footer">(La haine et la violence ne seront jamais acceptées)</p>
        </div>
        
        <p className="footer-copyright">© 2026 L'Éclaireur - Un outil d'aide pour les travailleurs québécois</p>
        <p className="footer-powered">Propulsé par <a href="https://emergent.sh" target="_blank" rel="noopener noreferrer">E1 by Emergent</a> & Google Gemini</p>
        <p className="footer-disclaimer">Cet outil ne remplace pas les conseils d'un professionnel qualifié.</p>
      </footer>
    </div>
  );
};

// ===== PAGE D'ANALYSE =====
const AnalysisPage = ({ onBackHome, consentAiLearning }) => {
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [downloadFormat, setDownloadFormat] = useState("pdf");
  const [showDestructionPopup, setShowDestructionPopup] = useState(false);
  const [abortController, setAbortController] = useState(null);

  const ACCEPTED_FORMATS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.txt', '.rtf'];

  const isAcceptedFormat = (filename) => {
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return ACCEPTED_FORMATS.includes(ext);
  };

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setError(null);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      const validFiles = droppedFiles.filter(f => isAcceptedFormat(f.name));
      const invalidFiles = droppedFiles.filter(f => !isAcceptedFormat(f.name));
      
      if (invalidFiles.length > 0) {
        setError(`Formats non acceptés: ${invalidFiles.map(f => f.name).join(', ')}`);
      }
      
      if (validFiles.length > 0) {
        setFiles(prev => [...prev, ...validFiles].slice(0, 10)); // Max 10 fichiers
        setResult(null);
      }
    }
  }, []);

  const handleFileSelect = (e) => {
    setError(null);
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      const validFiles = selectedFiles.filter(f => isAcceptedFormat(f.name));
      const invalidFiles = selectedFiles.filter(f => !isAcceptedFormat(f.name));
      
      if (invalidFiles.length > 0) {
        setError(`Formats non acceptés: ${invalidFiles.map(f => f.name).join(', ')}`);
      }
      
      if (validFiles.length > 0) {
        setFiles(prev => [...prev, ...validFiles].slice(0, 10));
        setResult(null);
      }
    }
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleAnalyze = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);
    
    // Créer un AbortController pour permettre l'annulation
    const controller = new AbortController();
    setAbortController(controller);
    
    try {
      const formData = new FormData();
      files.forEach(file => formData.append("files", file));
      
      const endpoint = files.length === 1 ? 
        `${API}/analyze?consent_ai_learning=${consentAiLearning}` :
        `${API}/analyze-multiple?consent_ai_learning=${consentAiLearning}`;
      
      // Pour un seul fichier, utiliser l'ancien endpoint
      if (files.length === 1) {
        formData.delete("files");
        formData.append("file", files[0]);
      }
      
      const response = await axios.post(endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 2700000, // 45 minutes pour les gros documents
        signal: controller.signal,
      });
      
      // Normaliser la réponse
      const analysisText = response.data.analysis || response.data.combined_analysis;
      setResult({ ...response.data, analysis: analysisText });
    } catch (err) {
      if (axios.isCancel(err) || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
        setError("Analyse annulée par l'utilisateur.");
      } else if (err.response?.data?.detail) {
        setError(`Erreur: ${err.response.data.detail}`);
      } else if (err.code === "ECONNABORTED") {
        setError("L'analyse a pris trop de temps. Veuillez réessayer avec moins de documents ou des fichiers plus petits.");
      } else {
        setError("Une erreur est survenue. Veuillez réessayer.");
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  };

  const handleCancel = () => {
    if (abortController) {
      abortController.abort();
    }
    setFiles([]);
    setResult(null);
    setError(null);
    setLoading(false);
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " octets";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " Ko";
    return (bytes / (1024 * 1024)).toFixed(2) + " Mo";
  };

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  const handleDownload = async () => {
    if (!result) return;
    
    const filename = files.length === 1 ? files[0]?.name?.replace(/\.[^/.]+$/, '') : 'rapport_analyse_combine';
    const content = result.analysis;
    const title = files.length === 1 ? 
      `Rapport d'Analyse Défense - ${filename}` : 
      `Rapport d'Analyse Défense Combiné - ${files.length} documents`;
    const date = new Date().toLocaleDateString('fr-CA');
    
    switch (downloadFormat) {
      case 'pdf': downloadAsPDF(content, title, filename, date); break;
      case 'docx': await downloadAsDOCX(content, title, filename, date); break;
      case 'txt': downloadAsTXT(content, title, filename, date); break;
      case 'html': downloadAsHTML(content, title, filename, date); break;
      case 'rtf': downloadAsRTF(content, title, filename, date); break;
      default: downloadAsPDF(content, title, filename, date);
    }
    
    // Afficher le popup de confirmation de destruction
    setShowDestructionPopup(true);
  };

  const handlePrint = () => {
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html><head><title>Rapport L'Éclaireur</title>
      <style>body{font-family:Arial,sans-serif;padding:20px;line-height:1.6;}pre{white-space:pre-wrap;}</style>
      </head><body><h1>Rapport d'Analyse Défense</h1><pre>${result.analysis}</pre></body></html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  const downloadAsPDF = (content, title, filename, date) => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    const maxWidth = pageWidth - 2 * margin;
    
    doc.setFontSize(16);
    doc.setFont("helvetica", "bold");
    doc.text(title, margin, 20);
    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    doc.text(`Généré le: ${date}`, margin, 30);
    doc.setLineWidth(0.5);
    doc.line(margin, 35, pageWidth - margin, 35);
    doc.setFontSize(10);
    const lines = doc.splitTextToSize(content, maxWidth);
    let y = 45;
    lines.forEach((line) => {
      if (y > 280) { doc.addPage(); y = 20; }
      doc.text(line, margin, y);
      y += 5;
    });
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.text(`L'Éclaireur - Page ${i}/${pageCount}`, pageWidth / 2, 290, { align: 'center' });
    }
    doc.save(`${filename}_rapport_defense.pdf`);
  };

  const downloadAsDOCX = async (content, title, filename, date) => {
    const doc = new Document({
      sections: [{
        children: [
          new Paragraph({ text: title, heading: HeadingLevel.HEADING_1 }),
          new Paragraph({ children: [new TextRun({ text: `Généré le: ${date}`, italics: true, size: 20 })] }),
          new Paragraph({ text: "" }),
          ...content.split('\n').map(line => new Paragraph({ children: [new TextRun({ text: line, size: 22 })] })),
        ],
      }],
    });
    const blob = await Packer.toBlob(doc);
    saveAs(blob, `${filename}_rapport_defense.docx`);
  };

  const downloadAsTXT = (content, title, filename, date) => {
    const text = `${title}\nGénéré le: ${date}\n${'='.repeat(50)}\n\n${content}`;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    saveAs(blob, `${filename}_rapport_defense.txt`);
  };

  const downloadAsHTML = (content, title, filename, date) => {
    const html = `<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>${title}</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:40px;line-height:1.6}h1{color:#2a7d7d}pre{background:#f5f5f5;padding:20px;border-radius:8px;white-space:pre-wrap;}</style></head><body><h1>${title}</h1><p><em>Généré le: ${date}</em></p><pre>${content}</pre></body></html>`;
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    saveAs(blob, `${filename}_rapport_defense.html`);
  };

  const downloadAsRTF = (content, title, filename, date) => {
    const encodeRTF = (text) => text.replace(/é/g, "\\'e9").replace(/è/g, "\\'e8").replace(/ê/g, "\\'ea").replace(/à/g, "\\'e0").replace(/ù/g, "\\'f9").replace(/ô/g, "\\'f4").replace(/î/g, "\\'ee").replace(/ç/g, "\\'e7").replace(/\n/g, '\\par ');
    const rtf = `{\\rtf1\\ansi{\\b\\fs32 ${encodeRTF(title)}}\\par{\\i ${date}}\\par\\par{\\fs22 ${encodeRTF(content)}}}`;
    const blob = new Blob([rtf], { type: 'application/rtf' });
    saveAs(blob, `${filename}_rapport_defense.rtf`);
  };

  return (
    <div className="app-container">
      {showDestructionPopup && <DestructionPopup onClose={() => setShowDestructionPopup(false)} />}
      
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <svg viewBox="0 0 100 100" className="sun-icon">
              <circle cx="50" cy="50" r="20" fill="#f4c430"/>
              {[...Array(12)].map((_, i) => (<line key={i} x1="50" y1="15" x2="50" y2="5" stroke="#f4c430" strokeWidth="3" transform={`rotate(${i * 30} 50 50)`}/>))}
            </svg>
          </div>
          <h1 className="title">Analyse de document</h1>
        </div>
        <button onClick={onBackHome} className="back-link">← Retour à l'accueil</button>
      </header>

      <div className="divider"></div>

      <main className="main-content">
        <div className={`upload-zone ${dragActive ? 'drag-active' : ''} ${files.length > 0 ? 'has-file' : ''}`} onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
          {files.length === 0 ? (
            <div className="upload-placeholder">
              <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <p className="upload-text">Glissez-déposez vos documents ici</p>
              <p className="upload-subtext">ou</p>
              <label className="file-select-btn">
                <input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.tiff,.tif,.bmp,.txt,.rtf" onChange={handleFileSelect} hidden multiple data-testid="file-input"/>
                Sélectionner des fichiers
              </label>
              <p className="upload-hint">Formats acceptés: PDF, Word, Images (JPG, PNG, TIFF), TXT, RTF</p>
              <p className="upload-hint">Maximum 10 fichiers, 100 Mo chacun</p>
            </div>
          ) : (
            <div className="files-list">
              <h4>{files.length} fichier{files.length > 1 ? 's' : ''} sélectionné{files.length > 1 ? 's' : ''}</h4>
              <p className="total-size">Taille totale: {formatFileSize(totalSize)}</p>
              <div className="files-grid">
                {files.map((f, idx) => (
                  <div key={idx} className="file-item">
                    <svg className="file-icon-small" viewBox="0 0 24 24" fill="none" stroke="#2a7d7d" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <div className="file-details">
                      <p className="file-name-small">{f.name}</p>
                      <p className="file-size-small">{formatFileSize(f.size)}</p>
                    </div>
                    <button className="remove-file-btn" onClick={() => removeFile(idx)} title="Retirer">×</button>
                  </div>
                ))}
              </div>
              <label className="add-more-btn">
                <input type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.tiff,.tif,.bmp,.txt,.rtf" onChange={handleFileSelect} hidden multiple/>
                + Ajouter d'autres fichiers
              </label>
            </div>
          )}
        </div>

        {files.length > 0 && (
          <div className="action-buttons">
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={loading} data-testid="analyze-btn">
              <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
              {loading ? "Analyse en cours..." : "Analyser le document"}
            </button>
            <button className="btn btn-secondary btn-cancel-active" onClick={handleCancel} data-testid="cancel-btn">
              {loading ? "⛔ Annuler l'analyse" : "Annuler"}
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-container" data-testid="loading-indicator">
            <div className="loading-spinner"></div>
            <p className="loading-text">Analyse du document en cours...</p>
            <p className="loading-subtext">Les gros documents sont segmentés. <strong>Cela peut prendre plusieurs minutes.</strong></p>
          </div>
        )}

        {error && (
          <div className="error-container" data-testid="error-message">
            <p className="error-text">{error}</p>
            <button className="btn btn-retry" onClick={handleAnalyze}>Réessayer</button>
          </div>
        )}

        {result && (
          <div className="result-container" data-testid="analysis-result">
            <div className="result-header">
              <svg className="result-icon" viewBox="0 0 24 24" fill="none" stroke="#2a7d7d" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              <h2>Analyse complétée</h2>
            </div>
            <div className="result-content">
              <pre className="analysis-text">{result.analysis}</pre>
            </div>
            <div className="download-section" data-testid="download-section">
              <h3>Télécharger le rapport de défense</h3>
              <div className="download-controls">
                <select value={downloadFormat} onChange={(e) => setDownloadFormat(e.target.value)} className="format-select" data-testid="format-select">
                  <option value="pdf">PDF (.pdf)</option>
                  <option value="docx">Word (.docx)</option>
                  <option value="txt">Texte (.txt)</option>
                  <option value="html">HTML (.html)</option>
                  <option value="rtf">RTF (.rtf)</option>
                </select>
                <button className="btn btn-download" onClick={handleDownload} data-testid="download-btn">
                  <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  Télécharger
                </button>
                <button className="btn btn-print" onClick={handlePrint} data-testid="print-btn">
                  <svg className="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                  Imprimer
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="security-note">
          <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="#c9a227" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <div>
            <strong>Sécurité garantie:</strong> Tous les documents sont détruits selon la norme DOD 5220.22-M après analyse. 
            Les informations ultra-sensibles (NAS, RAMQ, coordonnées bancaires) sont automatiquement masquées.
          </div>
        </div>
      </main>

      <footer className="footer">
        <nav className="footer-links">
          <a href="https://www.cnesst.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">CNESST</a>
          <a href="https://www.tat.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">TAT</a>
          <a href="https://www.barreau.qc.ca/fr/trouver-avocat/" target="_blank" rel="noopener noreferrer">Trouver un avocat</a>
          <a href="https://www.justice.gouv.qc.ca/aide-juridique/" target="_blank" rel="noopener noreferrer">Aide juridique</a>
        </nav>
        <p className="footer-copyright">© 2026 L'Éclaireur</p>
      </footer>

      <div className="emergent-badge">
        <img src="https://avatars.githubusercontent.com/in/1201222?s=120" alt="Emergent" />
        Made with Emergent
      </div>
    </div>
  );
};

// ===== APP PRINCIPALE =====
function App() {
  const [currentPage, setCurrentPage] = useState("home");
  const [showLegalPopup, setShowLegalPopup] = useState(false);
  const [consentAiLearning, setConsentAiLearning] = useState(false);

  const handleStartAnalysis = () => {
    setShowLegalPopup(true);
  };

  const handleLegalAccept = (aiConsent) => {
    setConsentAiLearning(aiConsent);
    setShowLegalPopup(false);
    setCurrentPage("analysis");
  };

  return (
    <>
      {showLegalPopup && <LegalPopup onAccept={handleLegalAccept} />}
      {currentPage === "home" 
        ? <HomePage onStartAnalysis={handleStartAnalysis} />
        : <AnalysisPage onBackHome={() => setCurrentPage("home")} consentAiLearning={consentAiLearning} />
      }
    </>
  );
}

export default App;
