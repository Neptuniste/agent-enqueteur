// Les Dossiers de l'Inspecteur : interface de jeu.
// Exécuté par gr.HTML (js_on_load) : « element » est la racine du composant, « server » donne accès aux
// fonctions Python du moteur (src/jeu/moteur.py). La constante CSS est ajoutée devant ce code par Python.
(function () {
  if (!document.getElementById('jx-style')) {
    const style = document.createElement('style');
    style.id = 'jx-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  const CLE = 'dossiers-inspecteur';
  const LIBELLES = { coupable: "Désignent l'assassin", mobile: 'Le mobile', moyen: 'Le moyen', opportunite: "L'occasion" };
  const etat = {
    catalogue: null, session: null, affaire: null, perso: null, historiques: {}, pieces: [],
    nouvelles: new Set(), carnet: [], recits: [], progression: null, attente: false, saut: false,
  };
  const vue = {};

  // --- Outils ------------------------------------------------------------------------------------
  function el(tag, attrs, ...enfants) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'html') n.innerHTML = v;
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const e of enfants.flat(3)) {
      if (e === null || e === undefined || e === false) continue;
      n.append(e instanceof Node ? e : document.createTextNode(String(e)));
    }
    return n;
  }
  const pause = (ms) => new Promise((r) => setTimeout(r, ms));
  function echapper(t) {
    return String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function enHtml(texte) { // *(didascalie)* et *italique*
    return echapper(texte).replace(/\*([^*]+)\*/g, '<em class="jx-didascalie">$1</em>');
  }
  function segments(texte) {
    const res = [];
    const re = /\*([^*]+)\*/g;
    let i = 0, m;
    while ((m = re.exec(texte))) {
      if (m.index > i) res.push({ em: false, t: texte.slice(i, m.index) });
      res.push({ em: true, t: m[1] });
      i = re.lastIndex;
    }
    if (i < texte.length) res.push({ em: false, t: texte.slice(i) });
    return res;
  }
  async function taper(noeud, texte, vitesse) {
    etat.saut = false;
    for (const s of segments(texte)) {
      const cible = s.em ? noeud.appendChild(el('em', { class: 'jx-didascalie' })) : noeud;
      const t = document.createTextNode('');
      cible.appendChild(t);
      for (const c of s.t) {
        t.data += c;
        if (!etat.saut) {
          await pause(vitesse);
          if (vue.dialogue) vue.dialogue.scrollTop = vue.dialogue.scrollHeight;
        }
      }
    }
  }
  function lire(cle) { try { return JSON.parse(localStorage.getItem(cle) || 'null'); } catch (e) { return null; } }
  function ecrire(cle, valeur) { try { localStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) { /* stockage indisponible */ } }
  function oublier() { try { localStorage.removeItem(CLE); } catch (e) { /* rien */ } }

  async function appeler(fonction, donnees) {
    let r;
    try {
      r = await server[fonction](donnees || {});
    } catch (erreur) {
      annoncer('Le serveur ne répond pas : ' + (erreur && erreur.message ? erreur.message : erreur));
      return null;
    }
    if (r && r.erreur) { annoncer(r.erreur); return null; }
    return r;
  }

  // --- Squelette -----------------------------------------------------------------------------------
  const racine = element.querySelector('.jx-racine') || element;
  racine.innerHTML = '';
  const app = el('div', { class: 'jx-app' });
  const zoneEcran = el('div');
  const zoneAnnonces = el('div', { class: 'jx-annonces' });
  app.append(zoneEcran, zoneAnnonces);
  racine.appendChild(app);

  // Chaque écran commence par oublier les éléments de l'écran précédent (viderVue), puis s'affiche (ecran).
  function viderVue() {
    for (const k of Object.keys(vue)) delete vue[k];
    zoneAnnonces.replaceChildren();
  }
  function ecran(classe, ...contenu) {
    zoneEcran.innerHTML = '';
    const n = el('div', { class: 'jx-ecran ' + classe }, ...contenu);
    zoneEcran.appendChild(n);
    return n;
  }
  function annoncer(texte, rouge) {
    const n = el('div', { class: 'jx-annonce' + (rouge ? ' jx-rouge' : '') }, texte);
    zoneAnnonces.appendChild(n);
    while (zoneAnnonces.children.length > 3) zoneAnnonces.firstChild.remove();
    setTimeout(() => n.remove(), 3800);
  }
  function fenetre(titre, corps, onglets) {
    const fermer = () => { voile.remove(); document.removeEventListener('keydown', echap); };
    const echap = (e) => { if (e.key === 'Escape') fermer(); };
    const zone = el('div', { class: 'jx-corps' }, corps);
    const voile = el('div', { class: 'jx-voile', onclick: (e) => { if (e.target === voile) fermer(); } },
      el('div', { class: 'jx-fenetre', role: 'dialog' },
        el('header', {}, el('h2', {}, titre), el('button', { class: 'jx-fermer', title: 'Fermer', onclick: fermer }, '×')),
        onglets || null, zone));
    document.addEventListener('keydown', echap);
    app.appendChild(voile);
    return zone;
  }

  // --- Accueil : le lanceur ------------------------------------------------------------------------
  async function accueil() {
    viderVue();
    if (!etat.catalogue) etat.catalogue = await appeler('catalogue');
    if (!etat.catalogue) return;
    const sauvegarde = lire(CLE);
    const cartes = etat.catalogue.affaires.map((a) => el('div', { class: 'jx-affiche jx-cadre' },
      el('div', { class: 'jx-lieu' }, a.lieu),
      el('h2', {}, a.titre),
      el('div', { class: 'jx-date' }, a.date),
      el('p', {}, a.accroche),
      el('div', { class: 'jx-chiffres' },
        el('span', {}, el('b', {}, a.personnages), 'suspects'),
        el('span', {}, el('b', {}, a.pieces), 'pièces'),
        el('span', {}, el('b', {}, a.pieces_depart), 'au dossier')),
      el('button', { class: 'jx-bouton', onclick: () => ouvrirAffaire(a.id) }, "Ouvrir l'affaire")));
    const mode = etat.catalogue.mode === 'demo'
      ? 'Mode démo : les personnages répondent avec leur fiche, sans modèle de langage'
      : 'Personnages joués par ' + (etat.catalogue.modele || 'un modèle de langage');
    ecran('jx-accueil',
      el('div', { class: 'jx-filet' }, '✦'),
      el('h1', { class: 'jx-titre-jeu' }, "Les Dossiers de l'Inspecteur"),
      el('div', { class: 'jx-sous-titre' }, 'Enquêtes criminelles, Paris, années folles'),
      sauvegarde && sauvegarde.session
        ? el('button', { class: 'jx-bouton jx-reprendre', onclick: () => reprendre(sauvegarde.session) }, "Reprendre l'enquête en cours")
        : null,
      el('div', { class: 'jx-affaires' }, cartes),
      el('div', { class: 'jx-mode' }, el('span', {}, mode), ' ',
        el('button', { class: 'jx-lien', onclick: regles }, 'Comment jouer ?')));
  }

  function regles() {
    fenetre('Comment jouer', el('div', { class: 'jx-document' },
      el('ul', { class: 'jx-regles' },
        el('li', {}, "Vous êtes l'inspecteur. Lisez le dossier, puis interrogez les personnes retenues : choisissez-en une à gauche et posez vos questions librement."),
        el('li', {}, 'Chaque personnage ne connaît que ce qui le concerne, et il peut mentir pour protéger ses secrets.'),
        el('li', {}, "Pour le confondre, montrez-lui une pièce du dossier : glissez-la sur la salle d'interrogatoire, ou cliquez sur « Montrer ». La bonne pièce provoque un aveu, et parfois de nouvelles pièces."),
        el('li', {}, 'Le carnet garde la trace des aveux obtenus ; vous pouvez y prendre des notes.'),
        el('li', {}, "Quand vous êtes sûr de vous, accusez, en appuyant l'accusation sur les pièces qui prouvent le mobile, le moyen et l'occasion. Le coupable trouvé vaut 40 points, chaque preuve juste 8 ; les preuves décisives que vous aurez débloquées valent jusqu'à 26 points, et les aveux obtenus jusqu'à 10."))));
  }

  // --- Ouverture, reprise --------------------------------------------------------------------------
  function charger(r) {
    etat.affaire = r.affaire;
    etat.pieces = r.pieces;
    etat.historiques = r.historiques || {};
    etat.carnet = r.carnet || [];
    etat.recits = r.recits || [];
    etat.progression = r.progression;
    etat.nouvelles = new Set();
    etat.perso = null;
  }
  async function ouvrirAffaire(id) {
    const r = await appeler('ouvrir', { affaire: id });
    if (!r) return;
    etat.session = r.session;
    ecrire(CLE, { session: r.session });
    charger(r);
    briefing();
  }
  async function reprendre(session) {
    const r = await appeler('reprendre', { session });
    if (!r) { oublier(); return accueil(); }
    etat.session = session;
    charger(r);
    if (r.verdict && (r.verdict.juste || r.verdict.solution)) verdict(r.verdict); else enquete();
  }

  // --- Briefing : la une du journal ----------------------------------------------------------------
  function briefing() {
    viderVue();
    const a = etat.affaire;
    // La une d'abord, puis le dossier : l'affaire ne se prend qu'une fois le dossier ouvert.
    const prendre = el('button', { class: 'jx-bouton', onclick: enquete, disabled: true,
      title: "Lisez d'abord le dossier" }, "Prendre l'affaire");
    const lire = el('button', { class: 'jx-bouton', onclick: () => {
      fenetreDossier(0);
      prendre.disabled = false;
      prendre.removeAttribute('title');
      lire.textContent = 'Relire le dossier';
    } }, 'Lire le dossier');
    ecran('jx-briefing', el('div', { class: 'jx-journal' },
      el('div', { class: 'jx-nom-journal' }, "L'Écho du Soir"),
      el('div', { class: 'jx-edition' }, el('span', {}, 'Édition spéciale'), el('span', {}, a.date), el('span', {}, '25 centimes')),
      el('h2', {}, a.titre),
      el('div', { class: 'jx-article' },
        el('p', {}, a.contexte),
        el('div', { class: 'jx-encadre' }, el('b', {}, 'La victime : '), a.victime.nom + ', ' + a.victime.identite + '.'),
        el('div', { class: 'jx-encadre' }, el('b', {}, 'Les personnes retenues : '),
          a.personnages.map((p) => p.nom).join(', ') + '.')),
      el('div', { class: 'jx-actions' },
        lire,
        prendre,
        el('button', { class: 'jx-bouton', onclick: accueil }, 'Retour'))));
  }

  // --- Enquête ---------------------------------------------------------------------------------------
  function personnage(id) { return etat.affaire.personnages.find((p) => p.id === id); }

  function enquete() {
    viderVue();
    const a = etat.affaire;
    if (!etat.perso) etat.perso = a.personnages[0].id;
    vue.jauges = el('div', { class: 'jx-jauges' });
    vue.suspects = el('aside', { class: 'jx-colonne jx-suspects' });
    vue.entete = el('div', { class: 'jx-entete' });
    vue.dialogue = el('div', { class: 'jx-dialogue', onclick: () => { etat.saut = true; } });
    vue.question = el('input', { type: 'text', placeholder: 'Votre question…', maxlength: '500',
      onkeydown: (e) => { if (e.key === 'Enter') { e.preventDefault(); envoyer(vue.question.value); } } });
    vue.envoyer = el('button', { class: 'jx-bouton', onclick: () => envoyer(vue.question.value) }, 'Interroger');
    vue.suggestions = el('div', { class: 'jx-suggestions' });
    vue.pieces = el('aside', { class: 'jx-colonne jx-pieces' });
    const salle = el('main', { class: 'jx-interrogatoire',
      ondragover: (e) => { e.preventDefault(); salle.classList.add('jx-cible'); },
      ondragleave: () => salle.classList.remove('jx-cible'),
      ondrop: (e) => { e.preventDefault(); salle.classList.remove('jx-cible'); const id = e.dataTransfer.getData('text/plain'); if (id) montrer(id); },
    }, vue.entete, vue.dialogue, vue.suggestions, el('div', { class: 'jx-saisie' }, vue.question, vue.envoyer));
    ecran('jx-enquete',
      el('header', { class: 'jx-barre' },
        el('h1', {}, a.titre), vue.jauges,
        el('div', { class: 'jx-actions-barre' },
          el('button', { class: 'jx-bouton jx-petit', onclick: () => fenetreDossier(0) }, 'Dossier'),
          el('button', { class: 'jx-bouton jx-petit', onclick: () => fenetreDossier(a.documents.findIndex((d) => d.plan)) }, 'Plan'),
          el('button', { class: 'jx-bouton jx-petit', onclick: fenetreCarnet }, 'Carnet'),
          el('button', { class: 'jx-bouton jx-petit jx-rouge', onclick: accusation }, 'Accuser'),
          el('button', { class: 'jx-bouton jx-petit', onclick: accueil }, 'Menu'))),
      el('div', { class: 'jx-plateau' }, vue.suspects, salle, vue.pieces));
    rendreTout();
  }

  function rendreTout() { rendreJauges(); rendreSuspects(); rendreEntete(); rendreDialogue(); rendreSuggestions(); rendrePieces(); }

  function rendreJauges() {
    const p = etat.progression;
    vue.jauges.replaceChildren(
      el('span', { class: 'jx-jauge' }, 'Pièces ', el('b', {}, p.pieces), '/' + p.pieces_total),
      el('span', { class: 'jx-jauge' }, 'Aveux ', el('b', {}, p.aveux), '/' + p.aveux_total),
      el('span', { class: 'jx-jauge' }, 'Questions ', el('b', {}, p.questions)));
  }

  function rendreSuspects() {
    const aveux = etat.progression.aveux_par_personnage || {};
    vue.suspects.replaceChildren(el('h3', {}, 'Les personnes retenues'),
      ...etat.affaire.personnages.map((p) => el('button', {
        class: 'jx-suspect' + (p.id === etat.perso ? ' jx-actif' : ''), title: p.identite,
        onclick: () => { if (!etat.attente) { etat.perso = p.id; rendreSuspects(); rendreEntete(); rendreDialogue(); } },
      }, el('img', { src: p.portrait, alt: '' }), el('span', {}, p.nom, el('small', {}, p.identite.split(',')[0])),
      aveux[p.id] ? el('span', { class: 'jx-sceau', title: 'aveux obtenus' }, aveux[p.id]) : null)));
  }

  function rendreEntete() {
    const p = personnage(etat.perso);
    vue.entete.replaceChildren(el('img', { src: p.portrait, alt: '' }),
      el('div', { style: 'flex:1' }, el('h2', {}, p.nom), el('div', { class: 'jx-identite' }, p.identite + '.'),
        el('div', { class: 'jx-attitude' }, p.attitude)),
      el('button', { class: 'jx-bouton jx-petit', title: "Efface l'interrogatoire ; les aveux restent acquis", onclick: effacer }, 'Effacer'));
  }

  function ligne(role, texte, aveu) {
    const p = personnage(etat.perso);
    return el('div', { class: 'jx-replique ' + (role === 'user' ? 'jx-joueur' : 'jx-perso') + (aveu ? ' jx-aveu' : '') },
      el('span', { class: 'jx-qui' }, role === 'user' ? "L'inspecteur" : p.nom),
      el('div', { class: 'jx-texte', html: enHtml(texte) }));
  }

  // Comment une pièce débloquée arrive au dossier (fouille, déposition…), raconté après la réplique.
  function recit(texte) { return el('div', { class: 'jx-recit' }, texte); }
  function recitsApres(perso, position) {
    return etat.recits.filter((x) => x.perso === perso && x.apres === position).map((x) => recit(x.texte));
  }

  function rendreDialogue() {
    const h = etat.historiques[etat.perso] || [];
    if (!h.length) {
      vue.dialogue.replaceChildren(el('div', { class: 'jx-vide' },
        personnage(etat.perso).nom + " attend vos questions. Glissez une pièce du dossier ici pour la lui montrer."));
      return;
    }
    vue.dialogue.replaceChildren(...h.flatMap((m, i) => [ligne(m.role, m.content), ...recitsApres(etat.perso, i + 1)]));
    vue.dialogue.scrollTop = vue.dialogue.scrollHeight;
  }

  function rendreSuggestions() {
    const victime = etat.affaire.victime.nom;
    const idees = ['Racontez-moi votre soirée.', 'Où étiez-vous au moment du drame ?', 'Que pensez-vous de ' + victime + ' ?',
      "Avez-vous remarqué quelque chose d'inhabituel ?", 'Qui pouvait lui en vouloir ?'];
    vue.suggestions.replaceChildren(...idees.map((q) => el('button', { class: 'jx-suggestion', onclick: () => envoyer(q) }, q)));
  }

  function rendrePieces() {
    vue.pieces.replaceChildren(el('h3', {}, 'Pièces à conviction'),
      el('div', { class: 'jx-aide-pieces' }, "Glissez une pièce sur l'interrogatoire pour la montrer"),
      ...etat.pieces.map((p) => el('div', {
        class: 'jx-piece' + (etat.nouvelles.has(p.id) ? ' jx-nouvelle' : ''), draggable: 'true',
        ondragstart: (e) => { e.dataTransfer.setData('text/plain', p.id); },
      }, el('h4', {}, p.nom), el('p', {}, p.description.length > 120 ? p.description.slice(0, 117) + '…' : p.description),
      el('div', { class: 'jx-boutons' },
        el('button', { class: 'jx-bouton jx-petit', onclick: () => fenetrePiece(p) }, 'Lire'),
        el('button', { class: 'jx-bouton jx-petit', onclick: () => montrer(p.id) }, 'Montrer')))));
  }

  function bloquer(oui) {
    etat.attente = oui;
    if (vue.question) vue.question.disabled = oui;
    if (vue.envoyer) vue.envoyer.disabled = oui;
  }

  async function envoyer(question, piece) {
    question = (question || '').trim();
    if (etat.attente || (!question && !piece)) return;
    const perso = etat.perso;
    const nomPiece = piece ? etat.pieces.find((p) => p.id === piece).nom : null;
    const provisoire = piece
      ? '*(Vous montrez ' + nomPiece.charAt(0).toLowerCase() + nomPiece.slice(1) + '.)* ' + question
      : question;
    if (vue.dialogue.querySelector('.jx-vide')) vue.dialogue.replaceChildren();
    const lignePosee = ligne('user', provisoire);
    const attente = el('div', { class: 'jx-replique jx-perso' }, el('span', { class: 'jx-qui' }, personnage(perso).nom),
      el('div', { class: 'jx-texte jx-reflexion' }, 'Réfléchit'));
    vue.dialogue.append(lignePosee, attente);
    vue.dialogue.scrollTop = vue.dialogue.scrollHeight;
    vue.question.value = '';
    bloquer(true);
    const r = await appeler('interroger', { session: etat.session, perso, question, piece: piece || null });
    if (!r) { attente.remove(); lignePosee.remove(); bloquer(false); return; }
    (etat.historiques[perso] = etat.historiques[perso] || []).push(
      { role: 'user', content: r.question }, { role: 'assistant', content: r.reponse });
    etat.progression = r.progression;
    lignePosee.querySelector('.jx-texte').innerHTML = enHtml(r.question);
    const texte = attente.querySelector('.jx-texte');
    texte.classList.remove('jx-reflexion');
    texte.textContent = '';
    if (r.aveu) attente.classList.add('jx-aveu');
    if (r.aveu) annoncer('Aveu !', true);
    if (r.carnet) etat.carnet.push(r.carnet);
    for (const p of r.nouvelles_pieces) {
      etat.pieces.push(p);
      etat.nouvelles.add(p.id);
      annoncer('Nouvelle pièce au dossier : ' + p.nom);
    }
    if (vue.jauges) { rendreJauges(); rendreSuspects(); rendrePieces(); }
    await taper(texte, r.reponse, 16);
    let dernier = attente;
    for (const x of r.recits || []) {
      etat.recits.push(x);
      if (etat.perso === perso) { const n = recit(x.texte); dernier.after(n); dernier = n; }
    }
    if (r.recits && r.recits.length && etat.perso === perso) vue.dialogue.scrollTop = vue.dialogue.scrollHeight;
    bloquer(false);
    if (vue.question) vue.question.focus();
  }

  function montrer(piece) { envoyer(vue.question ? vue.question.value : '', piece); }

  async function effacer() {
    if (etat.attente) return;
    const r = await appeler('reinitialiser', { session: etat.session, perso: etat.perso });
    if (!r) return;
    delete etat.historiques[etat.perso];
    etat.recits = etat.recits.filter((x) => x.perso !== etat.perso);
    etat.progression = r.progression;
    rendreDialogue();
    annoncer('Interrogatoire effacé ; les aveux restent acquis');
  }

  // --- Fenêtres : dossier, pièce, carnet ------------------------------------------------------------
  function fenetreDossier(index) {
    const docs = etat.affaire.documents;
    const contenu = el('div', { class: 'jx-document' });
    const onglets = el('div', { class: 'jx-onglets' });
    const montrerDoc = (i) => {
      contenu.innerHTML = docs[i].html;
      onglets.querySelectorAll('.jx-onglet').forEach((o, j) => o.classList.toggle('jx-actif', i === j));
    };
    docs.forEach((d, i) => onglets.appendChild(el('button', { class: 'jx-onglet', onclick: () => montrerDoc(i) }, d.titre)));
    fenetre('Le dossier', contenu, onglets);
    montrerDoc(Math.max(0, index || 0));
  }

  function fenetrePiece(p) {
    etat.nouvelles.delete(p.id);
    fenetre(p.nom, el('div', { class: 'jx-document', html: p.document }));
    if (vue.pieces) rendrePieces();
  }

  function fenetreCarnet() {
    const cleNotes = CLE + '-notes-' + etat.session;
    const notes = el('textarea', { class: 'jx-notes', placeholder: 'Vos notes…',
      oninput: () => ecrire(cleNotes, notes.value) });
    notes.value = lire(cleNotes) || '';
    const aveux = etat.carnet.length
      ? etat.carnet.map((c) => el('div', { class: 'jx-carnet-entree' },
        el('h4', {}, 'N° ' + c.numero + ' : ' + c.nom + (c.piece ? ', devant ' + c.piece : '')),
        el('div', { html: enHtml(c.texte) })))
      : [el('p', { class: 'jx-didascalie' }, "Aucun aveu pour l'instant. Montrez les bonnes pièces aux bonnes personnes.")];
    fenetre("Le carnet de l'inspecteur", el('div', {}, el('h3', {}, 'Aveux obtenus'), aveux, el('h3', {}, 'Notes'), notes));
  }

  // --- Accusation et verdict --------------------------------------------------------------------------
  function accusation() {
    if (etat.attente) return;
    viderVue();
    const a = etat.affaire;
    let choisi = null;
    const accuser = el('button', { class: 'jx-bouton jx-rouge', disabled: true }, "J'accuse !");
    const galerie = el('div', { class: 'jx-galerie' });
    a.personnages.forEach((p) => {
      const b = el('button', { class: 'jx-choix', onclick: () => {
        choisi = p.id;
        galerie.querySelectorAll('.jx-choix').forEach((x) => x.classList.toggle('jx-actif', x === b));
        accuser.disabled = false;
      } }, el('img', { src: p.portrait, alt: '' }), p.nom);
      galerie.appendChild(b);
    });
    const selects = {};
    const preuves = el('div', { class: 'jx-preuves' }, ['mobile', 'moyen', 'opportunite'].map((cle) => {
      selects[cle] = el('select', {}, el('option', { value: '' }, '(aucune pièce)'),
        etat.pieces.map((p) => el('option', { value: p.id }, p.nom)));
      return el('div', {}, el('label', {}, LIBELLES[cle]), selects[cle]);
    }));
    accuser.addEventListener('click', async () => {
      accuser.disabled = true;
      const r = await appeler('accuser', { session: etat.session, perso: choisi,
        preuves: { mobile: selects.mobile.value, moyen: selects.moyen.value, opportunite: selects.opportunite.value } });
      if (r) verdict(r); else accuser.disabled = false;
    });
    ecran('jx-accusation',
      el('div', { class: 'jx-filet' }, '⚖'),
      el('h2', {}, "L'accusation"),
      el('p', {}, "Désignez l'assassin, puis appuyez votre accusation sur les pièces du dossier."),
      galerie, preuves,
      el('div', { class: 'jx-ligne-boutons' }, accuser, el('button', { class: 'jx-bouton', onclick: enquete }, "Retour à l'enquête")));
  }

  function verdict(r) {
    viderVue();
    const tampon = r.juste ? el('div', { class: 'jx-tampon jx-ok' }, 'Affaire résolue')
      : r.solution ? el('div', { class: 'jx-tampon jx-classe' }, 'Affaire classée')
        : el('div', { class: 'jx-tampon jx-ko' }, 'Erreur judiciaire');
    const intro = el('p', {}, r.juste ? r.accuse + " est bien l'assassin." : r.accuse + " n'a pas commis ce crime.");
    const detail = el('ul', { class: 'jx-detail' }, r.detail.map((d) => el('li', {},
      (d.juste ? '✔ ' : '✘ ') + LIBELLES[d.categorie] + ' : ' + (d.piece || 'aucune pièce'))));
    const solution = r.solution ? [
      el('div', { class: 'jx-aveu-final', html: enHtml(r.aveu_final) }),
      el('div', { class: 'jx-solution' },
        el('h3', {}, 'La solution'), el('p', {}, r.solution),
        el('h3', {}, 'Le mobile'), el('p', {}, r.mobile),
        el('h3', {}, 'Le moyen'), el('p', {}, r.moyen),
        el('h3', {}, "L'occasion"), el('p', {}, r.opportunite),
        el('h3', {}, 'Les preuves'),
        el('ul', {}, Object.entries(r.preuves).map(([k, v]) => el('li', {}, LIBELLES[k] + ' : ' + v.join(', ')))))] : [];
    const boutons = r.solution
      ? [el('button', { class: 'jx-bouton', onclick: () => ouvrirAffaire(etat.affaire.id) }, 'Rejouer cette affaire'),
        el('button', { class: 'jx-bouton', onclick: () => { oublier(); accueil(); } }, 'Autres affaires')]
      : [el('button', { class: 'jx-bouton', onclick: enquete }, "Reprendre l'enquête"),
        el('button', { class: 'jx-bouton jx-rouge', onclick: async () => {
          const s = await appeler('reveler', { session: etat.session });
          if (s) verdict(s);
        } }, 'Révéler la solution')];
    ecran('jx-verdict', tampon, intro,
      el('div', { class: 'jx-score' }, 'Score ', el('b', {}, r.score), ' / 100'),
      el('div', { class: 'jx-grade' }, r.grade),
      detail, solution, el('div', { class: 'jx-ligne-boutons' }, boutons));
  }

  accueil();
})();
