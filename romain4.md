# Inspirer, clavier, micro à maintenir

**2 fonctions nouvelles** : `hold_to_talk` et `_show_composer`. **Une fonction réécrite** : `_show_topics`. **Une fonction branchée autrement** : `_handle_turn`. La consigne de `propose_topics` demande exactement 3 sujets.

**Environ 6 heures** sans IA, en débutant. Le temps passe dans le bouton micro. Streamlit n'a pas de bouton « maintenir pour parler ». Il faut une page HTML dans un dossier à part.

Ce guide part de zéro pour ce lot seulement. Les sujets, le post et l'agent existent déjà. Chaque changement porte le commentaire `#romain4`. Les docstrings disent le rôle de chaque fonction.

## Ce que l'utilisateur voit

1. **Inspirer** est sous le bouton **Maintenir pour parler**. Un clic affiche jusqu'à 3 boutons, au même endroit. Le texte de chaque bouton est le titre.
2. Un clic sur un de ces titres rédige le post tout de suite, par `draft_post`.
3. Si l'utilisateur donne un sujet dans la conversation, le bouton **Créer le post** apparaît sous ces titres. Un clic rédige ce sujet.
4. Il peut aussi le dire : « oui », « vas-y », ou une autre indication courte. Le post se rédige sans passer par le bouton.
5. « Rédige un post sur… » rédige tout de suite, avec cette phrase comme sujet.
6. La barre de chat n'existe plus. À la place : **Clavier** et **Maintenir pour parler**.
7. **Clavier** ouvre une zone de texte et le bouton **Envoyer**. Les photos sont sous cette zone.
8. On maintient le bouton rouge pour parler. Au relâchement, l'audio part à l'agent.
9. Appui trop court, ou enregistrement sans voix : le message est **Refaites l'audio**. L'agent n'est pas appelé. Si le navigateur bloque le micro, le message dit de l'autoriser.

## Ordre

1. Les quatre constantes dans `config.py`.
2. Le dossier `hold_talk/` : `__init__.py` et `frontend/index.html`.
3. Une phrase dans `propose_topics`.
4. `_show_topics`, puis `_show_composer` à la place de `st.chat_input`.
5. Dans `_handle_turn`, refuser une transcription vide.
6. Les essais en bas.

`app.py` garde ses tabulations. `hold_talk` s'écrit avec 4 espaces.

## Constantes

Dans `config.py`, sous les constantes Twitter :

```python
#romain4
# Le bouton Inspirer affiche trois sujets, pas la liste entière.
INSPIRE_COUNT = 3
# Un appui trop court ou sans voix ne part pas à l'agent.
AUDIO_MIN_SECONDS = 0.45
AUDIO_MIN_PEAK = 0.02
AUDIO_RETRY = "Refaites l'audio"
```

`AUDIO_MIN_PEAK` est une amplitude entre 0 et 1. En dessous, l'enregistrement est traité comme silencieux. `0.45` seconde évite un clic qui ne contient pas de phrase.

## Le micro, côté Python

Créer `hold_talk/__init__.py`. `declare_component` pointe vers le dossier `frontend`, pas vers un fichier. `hold_to_talk` renvoie `None` tant que personne n'a relâché le bouton. Ensuite un dictionnaire :

| Clé | Sens |
| --- | --- |
| `id` | identifiant de cet appui |
| `audio` | WAV en base64, seulement si l'appui est valable |
| `error` | `short`, `silent` ou `denied` |

```python
"""Bouton micro : on maintient pour parler, on relâche pour envoyer."""

import os

import streamlit.components.v1 as components

#romain4
_component = components.declare_component(
    "hold_talk",
    path=os.path.join(os.path.dirname(__file__), "frontend"),
)


#romain4
def hold_to_talk(min_seconds, min_peak, key=None):
    """Affiche le bouton à maintenir.

    Au relâchement, renvoie un dictionnaire avec un `id` unique.
    `audio` est un WAV en base64 si l'enregistrement est assez long et audible.
    `error` vaut `short`, `silent` ou `denied` sinon.
    Avant le premier relâchement, renvoie `None`.
    """
    return _component(
        min_seconds=min_seconds,
        min_peak=min_peak,
        key=key,
        default=None,
    )
```

## Le micro, côté page

Créer `hold_talk/frontend/index.html`. Le bouton écoute `pointerdown` et `pointerup`. Tant que le pointeur est enfoncé, le navigateur enregistre. Au relâchement, la page mesure la durée et le pic du signal.

- Moins de `min_seconds` : `error` vaut `short`.
- Pic sous `min_peak` : `error` vaut `silent`.
- Micro refusé : `error` vaut `denied`. Pas de WAV.
- Sinon : un WAV mono 16 bits, encodé en base64, dans `audio`.

La durée vient du nombre d'échantillons, pas de l'horloge du clic. L'attente de l'autorisation du micro ne compte pas comme de la parole. Si le bouton est déjà relâché quand l'autorisation arrive, c'est `short`.

Streamlit parle à cette page par `postMessage` : `streamlit:componentReady` au démarrage, `streamlit:render` pour recevoir `min_seconds` et `min_peak`, `streamlit:setComponentValue` pour renvoyer le dictionnaire.

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body { margin: 0; padding: 0; background: transparent; font-family: sans-serif; }
    button {
      width: 100%;
      min-height: 64px;
      border: none;
      border-radius: 999px;
      background: #b42318;
      color: white;
      font-size: 16px;
      cursor: pointer;
      touch-action: none;
      user-select: none;
    }
    button.recording { background: #7a271a; }
  </style>
</head>
<body>
  <button id="mic" type="button">Maintenir pour parler</button>
  <script>
    // #romain4 — maintenir pour parler, relâcher pour envoyer le WAV
    const mic = document.getElementById("mic");
    let args = { min_seconds: 0.45, min_peak: 0.02 };
    let recording = false;
    let pointerHeld = false;
    let context = null;
    let source = null;
    let processor = null;
    let stream = null;
    let chunks = [];
    let startedAt = 0;

    function send(type, data) {
      window.parent.postMessage(Object.assign({
        isStreamlitMessage: true,
        type: type,
      }, data), "*");
    }

    function setValue(value) {
      send("streamlit:setComponentValue", { value: value, dataType: "json" });
    }

    function encodeWav(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);
      function writeString(offset, text) {
        for (let i = 0; i < text.length; i++) {
          view.setUint8(offset + i, text.charCodeAt(i));
        }
      }
      writeString(0, "RIFF");
      view.setUint32(4, 36 + samples.length * 2, true);
      writeString(8, "WAVE");
      writeString(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(36, "data");
      view.setUint32(40, samples.length * 2, true);
      let offset = 44;
      for (let i = 0; i < samples.length; i++, offset += 2) {
        const sample = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      }
      return new Uint8Array(buffer);
    }

    function toBase64(bytes) {
      let binary = "";
      const step = 0x8000;
      for (let i = 0; i < bytes.length; i += step) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
      }
      return btoa(binary);
    }

    function peakOf(samples) {
      let peak = 0;
      for (let i = 0; i < samples.length; i++) {
        const value = Math.abs(samples[i]);
        if (value > peak) peak = value;
      }
      return peak;
    }

    async function start(event) {
      if (recording) return;
      event.preventDefault();
      mic.setPointerCapture(event.pointerId);
      pointerHeld = true;
      chunks = [];
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        pointerHeld = false;
        setValue({ id: String(Date.now()), error: "denied" });
        return;
      }
      // #romain4 — relâché pendant l'autorisation du micro : trop court
      if (!pointerHeld) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
        setValue({ id: String(Date.now()), error: "short" });
        return;
      }
      context = new AudioContext();
      source = context.createMediaStreamSource(stream);
      processor = context.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = function (audioEvent) {
        if (!recording) return;
        chunks.push(new Float32Array(audioEvent.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(context.destination);
      recording = true;
      startedAt = performance.now();
      mic.className = "recording";
      mic.textContent = "Relâchez pour envoyer";
    }

    function stop(event) {
      pointerHeld = false;
      if (!recording) return;
      event.preventDefault();
      recording = false;
      mic.className = "";
      mic.textContent = "Maintenir pour parler";
      if (processor) processor.disconnect();
      if (source) source.disconnect();
      if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
      const sampleRate = context ? context.sampleRate : 44100;
      if (context) context.close();
      let length = 0;
      chunks.forEach(function (chunk) { length += chunk.length; });
      const samples = new Float32Array(length);
      let offset = 0;
      chunks.forEach(function (chunk) {
        samples.set(chunk, offset);
        offset += chunk.length;
      });
      const seconds = samples.length / sampleRate;
      const id = String(Date.now());
      if (seconds < args.min_seconds) {
        setValue({ id: id, error: "short" });
        return;
      }
      if (peakOf(samples) < args.min_peak) {
        setValue({ id: id, error: "silent" });
        return;
      }
      setValue({
        id: id,
        audio: toBase64(encodeWav(samples, sampleRate)),
        seconds: seconds,
      });
    }

    mic.addEventListener("pointerdown", start);
    mic.addEventListener("pointerup", stop);
    mic.addEventListener("pointercancel", stop);

    window.addEventListener("message", function (event) {
      const data = event.data;
      if (!data || data.type !== "streamlit:render") return;
      args = data.args || args;
      send("streamlit:setFrameHeight", { height: 76 });
    });

    send("streamlit:componentReady", { apiVersion: 1 });
  </script>
</body>
</html>
```

## Trois sujets, pas une liste

Dans `propose_topics`, la consigne Groq contient cette ligne, avec le commentaire juste au-dessus, dans les parenthèses du texte :

```python
            #romain4
            "Propose exactement 3 sujets.\n"
```

La docstring de `propose_topics` dit : exactement 3 sujets, et la page n'affiche que les trois premiers. S'il y a moins de sources, le modèle peut en proposer moins. On n'invente pas un titre pour remplir.

`_show_topics` s'affiche dans la colonne du micro, juste en dessous. Le code de `app.py` est en tabulations. `_choose_topic` vide `post_for` pour que `_show_post` rappelle `draft_post`.

```python
#romain4
def _choose_topic(topic):
	"""Retient le sujet et force une nouvelle rédaction.

	`post_for` vide fait rappeler `draft_post` dans `_show_post`.
	"""
	st.session_state.chosen_topic = topic
	st.session_state.post_for = None


#romain4
def _show_topics(user_id):
	"""Affiche Inspirer, puis trois titres, sous le micro.

	Un clic sur Inspirer interroge la veille. Un clic sur un des trois
	titres rédige le post tout de suite. Si un sujet a été donné dans
	la conversation, le bouton « Créer le post » fait la même chose.
	"""
	if st.button("Inspirer", key="inspire"):
		persona = st.session_state.persona
		rss = recent_articles(user_id, RSS_ITEMS_IN_PROMPT, kind="rss")
		mail = [
			article for article in recent_articles(user_id, MAIL_ITEMS_IN_PROMPT, kind="email")
			if matches_theme(persona, article["title"], article["summary"])
		]
		for article in rss:
			article["kind"] = "rss"
		for article in mail:
			article["kind"] = "email"
		with st.spinner("Recherche de sujets…"):
			try:
				topics = propose_topics(persona, rss + mail)
			except SujetError as error:
				st.warning(str(error))
				topics = None
		if topics is not None:
			st.session_state.topics = list(topics)[:INSPIRE_COUNT]
			if not st.session_state.topics:
				st.info("Aucun sujet pour l'instant. Rafraîchis la veille.")
	for index, topic in enumerate(st.session_state.get("topics") or []):
		#romain4
		if st.button(topic["title"], key=f"inspire-{index}"):
			_choose_topic(topic)
	offered = st.session_state.get("offered_topic")
	#romain4
	if offered and st.session_state.get("post_for") != offered.get("title"):
		st.caption(offered.get("title") or "")
		if st.button("Créer le post", key="create_post"):
			_choose_topic(offered)
```

L'appel est dans la colonne du micro, après `hold_to_talk` :

```python
		recording = hold_to_talk(
			AUDIO_MIN_SECONDS,
			AUDIO_MIN_PEAK,
			key="hold_mic",
		)
		#romain4
		_show_topics(st.session_state.user_id)
```

`post_for = None` force `_show_post` à rappeler `draft_post` au passage suivant. Le clic sur un bouton relance la page, donc la rédaction a lieu en haut du script, là où `_show_post` est déjà appelé.

## Clavier et micro, à la place de la barre

Imports à ajouter en haut de `app.py` : `import io`, `AUDIO_MIN_PEAK`, `AUDIO_MIN_SECONDS`, `AUDIO_RETRY`, `INSPIRE_COUNT`, et `from hold_talk import hold_to_talk`.

Supprimer `st.chat_input`. Après la boucle qui affiche les messages, appeler `_show_composer()`.

```python
#romain4
def _show_composer():
	"""Remplace la barre de chat par un clavier et un micro à maintenir.

	Le clavier ouvre une zone de texte. Le micro enregistre tant que le bouton
	est enfoncé et envoie l'audio au relâchement. Un appui trop court ou sans
	voix affiche `AUDIO_RETRY` et n'appelle pas l'agent.
	"""
	if st.session_state.pop("clear_keyboard", False):
		st.session_state.keyboard_text = ""
	columns = st.columns([1, 2])
	with columns[0]:
		if st.button("Clavier", key="toggle_keyboard"):
			st.session_state.show_keyboard = not st.session_state.get("show_keyboard")
	with columns[1]:
		recording = hold_to_talk(
			AUDIO_MIN_SECONDS,
			AUDIO_MIN_PEAK,
			key="hold_mic",
		)
	if st.session_state.get("show_keyboard"):
		st.text_area(CHAT_PLACEHOLDER, key="keyboard_text")
		uploads = st.file_uploader(
			"Photos",
			type=["png", "jpg", "jpeg"],
			accept_multiple_files=True,
			key="keyboard_files",
		)
		if st.button("Envoyer", key="send_keyboard"):
			#romain4
			try:
				_handle_turn(
					st.session_state.get("keyboard_text") or "",
					files=uploads,
				)
			except AgentError as error:
				st.error(str(error))
			else:
				st.session_state.clear_keyboard = True
				st.rerun()
	if not recording or recording.get("id") == st.session_state.get("last_audio_id"):
		return
	st.session_state.last_audio_id = recording["id"]
	#romain4
	if recording.get("error") in {"short", "silent"}:
		st.warning(AUDIO_RETRY)
		return
	if recording.get("error"):
		st.warning("Le micro est bloqué. Autorisez-le, puis recommencez.")
		return
	raw = base64.b64decode(recording["audio"])
	try:
		_handle_turn("", audio=io.BytesIO(raw))
	except AgentError as error:
		st.error(str(error))
```

Tout en bas du fichier, après la définition de `_handle_turn` :

```python
#romain4
_show_composer()
```

`_handle_turn` ne reçoit plus l'objet de `st.chat_input`. Sa signature et le refus d'une transcription vide :

```python
def _handle_turn(text="", audio=None, files=None):
	"""Envoie un texte ou un audio à l'agent.

	`text` vient du clavier. `audio` est un WAV déjà jugé assez long.
	Une transcription vide affiche le même message qu'un appui raté.
	"""
	# ... découpe du texte, puis, après transcribe(audio) :
		#romain4
		if not spoken:
			st.warning(AUDIO_RETRY)
			return
```

Le reste du tour (images, réponse, voix, historique, base) ne change que pour trois cas, juste après avoir obtenu `question` et avant l'appel à l'agent :

```python
	#romain4
	if question and not images:
		intent, spoken_topic = post_intent(
			question,
			pending=bool(st.session_state.get("offered_topic")),
		)
		if intent == "confirm" and st.session_state.get("offered_topic"):
			_choose_topic(st.session_state.offered_topic)
			_remember_turn(question, "Je rédige le post.")
			st.session_state.clear_keyboard = True
			st.rerun()
		if intent == "draft" and spoken_topic:
			st.session_state.offered_topic = spoken_topic
			_choose_topic(spoken_topic)
			_remember_turn(question, "Je rédige le post.")
			st.session_state.clear_keyboard = True
			st.rerun()
		if intent == "offer" and spoken_topic:
			st.session_state.offered_topic = spoken_topic
			st.session_state.refresh_composer = True
```

`post_intent` est dans `post.py`, pour que `app.py` n'appelle pas Groq lui-même. À la fin du fichier :

```python
#romain4
def post_intent(text, pending=False):
    """Même rôle que `Post.post_intent`."""
    return post.post_intent(text, pending=pending)
```

## Sujet donné, bouton, accord à l'oral

À ajouter dans `post.py`. Quatre espaces. `post_intent` renvoie un couple.

| Valeur | Quand | Effet sur la page |
| --- | --- | --- |
| `("confirm", None)` | « oui », « vas-y », ou une indication courte alors qu'un sujet est déjà donné | `_choose_topic` sur `offered_topic`, puis rédaction |
| `("draft", sujet)` | « rédige un post sur… » avec un vrai sujet dans la phrase | rédaction immédiate de ce sujet |
| `("offer", sujet)` | une phrase d'au moins deux mots qui donne un sujet | bouton **Créer le post**, la conversation continue |
| `("chat", None)` | bonjour, merci, ou un seul mot qui n'est pas un accord | rien de nouveau |

Les listes et les fonctions à recopier :

```python
import unicodedata

#romain4
_AGREEMENTS = {
    "oui", "ouais", "ouai", "ok", "okay", "daccord", "dac",
    "vas y", "allez", "allez y", "go", "banco", "parfait",
    "cest bon", "c est bon", "ca marche", "top", "nickel",
    "fais le", "fonce", "valide", "on y va", "bien sur",
    "exactement", "tout a fait", "je confirme", "confirme",
    "oui vas y", "absolument", "evidemment", "lets go",
    "je suis partant", "partant", "carrement", "redige",
    "redige le post", "cree le post", "creer le post",
    "ecris le post", "lance", "lance le post",
}
#romain4
_WRITE_NOW = (
    "redige",
    "ecris le post",
    "ecris un post",
    "cree le post",
    "creer le post",
    "fais le post",
    "fais un post",
    "lance le post",
    "je veux un post",
    "je veux le post",
    "fais moi un post",
)
#romain4
_GREETINGS = {
    "bonjour", "salut", "hello", "merci", "au revoir",
    "bonne journee", "coucou", "bonsoir", "ciao",
}
#romain4
_EMPTY_WRITE = {"", "le", "le post", "un post", "moi le post", "moi un post"}


#romain4
def _fold(text):
    """Minuscules, sans accent, apostrophe ni trait d'union."""
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    folded = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    folded = folded.replace("'", " ").replace("’", " ").replace("-", " ")
    return " ".join(folded.split())


#romain4
def _asks_to_write(folded):
    """Vrai si la phrase demande un post et donne déjà le sujet."""
    for cue in _WRITE_NOW:
        if folded == cue or folded.startswith(cue + " "):
            extra = folded[len(cue):].strip()
            return extra not in _EMPTY_WRITE
    return False


#romain4
def _is_agreement(folded):
    """Vrai si toute la phrase est un accord, pas un nouveau sujet."""
    if folded in _AGREEMENTS:
        return True
    words = folded.split()
    if not words or len(words) > 4:
        return False
    if words[0] in {"oui", "ouais", "ok", "okay"}:
        return True
    if folded.startswith("vas y") or folded.startswith("allez"):
        return True
    return False


#romain4
def _topic_from(text):
    """Sujet tiré de la phrase dite ou tapée."""
    return {
        "title": text.strip(),
        "source": "conversation",
        "reason": "Sujet donné dans la conversation.",
    }
```

Méthodes de la classe `Post`, après `clear_post` :

```python
    #romain4
    def post_intent(self, text, pending=False):
        """Classe une phrase avant de rédiger.

        `("confirm", None)` : accord pour le sujet déjà donné
        (oui, vas-y, ou une autre indication courte).
        `("draft", sujet)` : la phrase demande d'écrire maintenant
        et contient le sujet.
        `("offer", sujet)` : la phrase donne un sujet, le bouton
        « Créer le post » peut apparaître.
        `("chat", None)` : le reste de la conversation.

        Une indication courte qui n'est pas dans la liste est demandée
        au modèle, qui répond oui ou non. S'il ne répond pas, la phrase
        reste une conversation.
        """
        folded = _fold(text)
        if not folded or folded in _GREETINGS or folded.startswith("merci"):
            return "chat", None
        if _asks_to_write(folded):
            return "draft", _topic_from(text)
        if _is_agreement(folded):
            return "confirm", None
        words = folded.split()
        if pending and 0 < len(words) <= 8:
            if self._says_yes(text):
                return "confirm", None
        if len(words) >= 2:
            return "offer", _topic_from(text)
        return "chat", None

    #romain4
    def _says_yes(self, text):
        """Demande au modèle si la phrase lance la rédaction.

        Répond False si Groq ne renvoie rien d'utilisable.
        """
        prompt = (
            "Un sujet de post est déjà proposé.\n"
            f"L'utilisateur dit : « {text.strip()} ».\n"
            "Est-ce qu'il demande de rédiger ce post maintenant "
            "(accord, ordre ou encouragement) ?\n"
            "Réponds uniquement par oui ou par non."
        )
        try:
            completion = self._client().chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = completion.choices[0].message.content or ""
        except Exception:
            return False
        return _fold(raw).startswith("oui")
```

Quitter le compte remet aussi `offered_topic` à `None`.

## Essais

| Essai | Résultat |
| --- | --- |
| Inspirer avec de la veille | 1 à 3 boutons. Le texte du bouton est le titre. |
| Clic sur un titre | Le post se rédige dans la page. |
| Dire un sujet, puis **Créer le post** | Le post se rédige sur cette phrase. |
| Dire un sujet, puis « oui » ou « vas-y » | Même rédaction, sans cliquer. |
| « Rédige un post sur les puces » | Le post part tout de suite, sur cette phrase. |
| « Bonjour » | Pas de bouton **Créer le post**. La conversation continue. |
| Inspirer sans article | « Aucun sujet pour l'instant. Rafraîchis la veille. » |
| Clavier, une phrase, Envoyer | La phrase apparaît comme un message. La zone se vide. |
| Maintenir une seconde et parler, relâcher | La transcription part à l'agent. La réponse est lue. |
| Clic très bref sur le micro | **Refaites l'audio**. Pas d'appel Groq. |
| Maintenir en silence | **Refaites l'audio**. |
| Micro refusé par le navigateur | Le message parle du micro bloqué. |

Le micro se vérifie dans le navigateur, pas dans un terminal : il demande l'autorisation du site. Relancer l'application avec `env/bin/python -m streamlit run app.py` après ces fichiers. Un serveur déjà ouvert garde les anciens imports.

## Pièges

`st.chat_input` ne sait pas maintenir un bouton. Le remettre affiche de nouveau la barre et enlève le maintien.

Vider `keyboard_text` dans le même passage que la zone de texte fait une erreur Streamlit. Le drapeau `clear_keyboard` attend le passage suivant, et la clé est vidée avant que la zone existe.

Streamlit renvoie la dernière valeur du composant à chaque rafraîchissement. Sans comparaison de `id` avec `last_audio_id`, le même audio part en boucle.

Un WAV trop court ou silencieux ne doit pas arriver à `transcribe`. Le tri se fait dans la page HTML. La transcription vide est un second filet, au cas où Whisper n'entend rien.

« oui » sans sujet déjà donné ne rédige rien : la phrase part à l'agent comme une conversation. Le bouton **Créer le post** n'existe qu'après une phrase qui a donné un sujet.

Les trois titres ne sont plus dans la barre. Les remettre dans `st.sidebar` les éloigne du micro.
