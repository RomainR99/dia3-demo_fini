import base64
import io
#romain7
import os
import time
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from config import (
	APP_TITLE,
	CHAT_PLACEHOLDER,
	IMAGE_ONLY_QUESTION,
	MAX_IMAGES,
	PAGE_TITLE,
	PERSONAS,
	#romain2
	MAIL_ITEMS_IN_PROMPT,
	RSS_ITEMS_IN_PROMPT,
	#romain4
	AUDIO_MIN_PEAK,
	AUDIO_MIN_SECONDS,
	AUDIO_RETRY,
	INSPIRE_COUNT,
	#romain6
	GAMMA_LANGUAGES,
)
# Base de données
from db import (
	add_message,
	authenticate,
	create_user,
	disconnect_mailbox,
	get_mailbox_address,
	init_db,
	list_feeds,
	load_messages,
	recent_articles,
	set_feed_active,
	#romain6
	gamma_view,
	save_gamma_languages,
)
from llm_agent import (
	AgentError,
	ask_llm,
	combine_speech,
	first_spoken_sentence,
	prepare_image,
	reset_conversation_history,
	speak,
	split_for_speech,
	text_for_speech,
	transcribe,
	update_conversation_history,
	wav_seconds,
)
#romain2
from sujet import SujetError, propose_topics
#romain3
from post import (
	PostError,
	clear_post,
	draft_post,
	post_intent,
	save_post_edit,
	spoken_minutes,
)
#romain4
from hold_talk import hold_to_talk
#flux RSS
from rss_watcher import digest_for, refresh_user
#flux_rss_email
from mail_watcher import MailError, connect_mailbox, matches_theme
#romain6
from gamma_client import GammaError, owner_key, refresh_generation, send_approved
#romain7
from video import VideoError, build_video

# Départ du chrono : le script repart quand l'enregistrement vient d'être envoyé.
run_started = time.perf_counter()

st.set_page_config(page_title=PAGE_TITLE)
st.title(APP_TITLE)
st.toggle("Réponse vocale", key="speak")


# Base de données
#persona
def require_user():
	init_db()
	if st.session_state.get("user_id"):
		if st.session_state.get("loaded_for") != st.session_state.user_id:
			st.session_state.messages = load_messages(st.session_state.user_id)
			st.session_state.loaded_for = st.session_state.user_id
		#romain1
		reset_conversation_history(st.session_state.messages)
		return

	st.subheader("Qui monte à bord ?")
	mode = st.radio("Compte", ["Connexion", "Créer un compte"], horizontal=True)
	username = st.text_input("Nom")
	password = st.text_input("Mot de passe", type="password")
	persona = "veille_tech"
	if mode == "Créer un compte":
		persona = st.selectbox(
			"Veille",
			list(PERSONAS),
			format_func=lambda key: PERSONAS[key]["label"],
		)
	if st.button("Entrer"):
		if mode == "Créer un compte":
			user_id, error = create_user(username, password, persona)
			if error:
				st.warning(error)
			else:
				st.session_state.user_id = user_id
				st.session_state.persona = persona
				st.session_state.username = username.strip()
				st.rerun()
		else:
			user = authenticate(username, password)
			if user is None:
				st.warning("Nom ou mot de passe refusé.")
			else:
				st.session_state.user_id = user["id"]
				st.session_state.persona = user["persona"]
				st.session_state.username = user["username"]
				st.rerun()
	st.stop()


#persona
def open_message(role):
	avatar = None
	if role == "assistant":
		avatar = PERSONAS[st.session_state.persona]["avatar"]
	if avatar:
		return st.chat_message(role, avatar=avatar)
	return st.chat_message(role)


#flux RSS
# Base de données
def show_veille():
	user_id = st.session_state.user_id
	label = PERSONAS[st.session_state.persona]["label"]
	st.sidebar.header(st.session_state.username)
	st.sidebar.caption(label)
	#flux_rss_email
	if st.sidebar.button("Rafraîchir la veille"):
		with st.spinner("Lecture des flux et de Gmail…"):
			errors = refresh_user(user_id)
		for error in errors:
			st.sidebar.warning(error)
		if not errors:
			st.sidebar.success("Veille à jour.")
	if st.sidebar.button("Quitter le bord"):
		st.session_state.user_id = None
		st.session_state.persona = None
		st.session_state.username = None
		st.session_state.messages = []
		st.session_state.loaded_for = None
		#romain1
		reset_conversation_history([])
		#romain2
		st.session_state.topics = []
		#romain3
		st.session_state.chosen_topic = None
		st.session_state.post_for = None
		st.session_state.post_text = ""
		st.session_state.validated_post = ""
		clear_post()
		#romain5
		st.session_state.offered_topic = None
		st.session_state.video_source = ""
		#romain6
		st.session_state.pop("gamma_slide_language", None)
		st.session_state.pop("gamma_subtitle_language", None)
		st.rerun()

	st.sidebar.subheader("Flux")
	for feed in list_feeds(user_id):
		key = f"feed-{feed['id']}"
		if key not in st.session_state:
			st.session_state[key] = bool(feed["active"])
		checked = st.sidebar.checkbox(feed["name"], key=key)
		if checked != bool(feed["active"]):
			set_feed_active(feed["id"], user_id, checked)
			st.rerun()
		if feed["last_error"]:
			st.sidebar.caption(feed["last_error"])

	st.sidebar.subheader("Derniers articles")
	for article in recent_articles(user_id, 8, kind="rss"):
		title = article["title"]
		link = article["link"]
		if link:
			st.sidebar.markdown(f"[{title}]({link})")
		else:
			st.sidebar.write(title)
		st.sidebar.caption(article["source"])

	#flux_rss_email
	_show_gmail(user_id)
	#romain6
	_show_gamma(user_id)


#flux_rss_email
def _show_gmail(user_id):
	st.sidebar.subheader("Gmail")
	saved = get_mailbox_address(user_id)
	if saved:
		st.sidebar.caption(f"Connecté : {saved}")
	address = st.sidebar.text_input("Adresse Gmail", key="gmail_address")
	secret = st.sidebar.text_input(
		"Mot de passe d'application",
		type="password",
		key="gmail_app_password",
	)
	if st.sidebar.button("Connecter Gmail"):
		try:
			connect_mailbox(user_id, address, secret)
		except MailError as error:
			st.sidebar.warning(str(error))
		else:
			st.sidebar.success("Gmail connecté. Rafraîchis la veille pour lire les newsletters.")
	if saved and st.sidebar.button("Déconnecter Gmail"):
		disconnect_mailbox(user_id)
		st.rerun()
	#flux_rss_email
	label = PERSONAS[st.session_state.persona]["label"]
	st.sidebar.caption(f"Newsletters du mois dernier retenues pour : {label}")
	kept = [
		article for article in recent_articles(user_id, 8, kind="email")
		if matches_theme(st.session_state.persona, article["title"], article["summary"])
	]
	for article in kept:
		title = article["title"]
		link = article["link"]
		if link:
			st.sidebar.markdown(f"[{title}]({link})")
		else:
			st.sidebar.write(title)


#romain6
def _show_gamma(user_id):
	"""Réglages Gamma : langue des slides et langue des sous-titres.

	La clé est celle du projet, dans .env. Tous les comptes créent les
	slides avec elle. La langue des slides est aussi celle de la vidéo.
	Les sous-titres ont leur propre langue, français par défaut.
	"""
	st.sidebar.subheader("Réglages")
	view = gamma_view(user_id)
	if owner_key():
		st.sidebar.caption("Les slides sont créées avec la clé Gamma du projet.")
	else:
		st.sidebar.warning("Mets GAMMA_API_KEY dans le fichier .env.")
	if "gamma_slide_language" not in st.session_state:
		st.session_state.gamma_slide_language = view["slide_language"]
	if "gamma_subtitle_language" not in st.session_state:
		st.session_state.gamma_subtitle_language = view["subtitle_language"]
	codes = list(GAMMA_LANGUAGES)
	slide = st.sidebar.selectbox(
		"Langue des slides et de la vidéo",
		codes,
		format_func=lambda code: GAMMA_LANGUAGES[code],
		key="gamma_slide_language",
	)
	subtitles = st.sidebar.selectbox(
		"Langue des sous-titres",
		codes,
		format_func=lambda code: GAMMA_LANGUAGES[code],
		key="gamma_subtitle_language",
	)
	if slide != view["slide_language"] or subtitles != view["subtitle_language"]:
		save_gamma_languages(user_id, slide, subtitles)
	if view.get("job_status") == "pending" and st.sidebar.button("Vérifier les slides"):
		try:
			refresh_generation(user_id)
		except GammaError as error:
			st.sidebar.warning(str(error))
		else:
			st.rerun()


#romain5
def _choose_topic(topic):
	"""Retient le sujet et force une nouvelle rédaction.

	`post_for` vide fait rappeler `draft_post` dans `_show_post`.
	L'ancienne source vidéo est oubliée : elle ne correspond plus à ce sujet.
	"""
	st.session_state.chosen_topic = topic
	st.session_state.post_for = None
	st.session_state.video_source = ""


#romain5
def _start_video_flow(text):
	"""Garde le texte modifié comme source du futur flux vidéo.

	Le texte édité est enregistré. Aucune vidéo ni aucun visuel n'est produit :
	ce bouton est seulement l'entrée de cette étape, à brancher plus tard.
	"""
	saved = save_post_edit(text)
	st.session_state.validated_post = saved
	st.session_state.video_source = saved
	return saved


#romain5
def _remember_turn(question, reply):
	"""Garde l'accord de l'utilisateur sans appeler l'agent.

	La phrase dite et la réponse courte restent dans l'historique.
	"""
	st.session_state.messages.append({"role": "user", "content": question})
	st.session_state.messages.append({"role": "assistant", "content": reply})
	update_conversation_history("user", question)
	update_conversation_history("assistant", reply)
	add_message(st.session_state.user_id, "user", question, [])
	add_message(st.session_state.user_id, "assistant", reply)


#romain5
def _show_topics(user_id):
	"""Affiche Inspirer, puis trois titres, puis le post, sous le micro.

	Un clic sur Inspirer interroge la veille. Un clic sur un des trois
	titres choisit ce sujet. `_show_post` rédige juste en dessous, dans
	le même passage, un texte que l'utilisateur peut modifier.
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
		#romain5
		if st.button(topic["title"], key=f"inspire-{index}"):
			_choose_topic(topic)
	#romain5
	_show_post(user_id)


#romain3
def _post_articles(user_id):
	"""Reprend les flux et les newsletters du persona, comme pour les sujets.

	`kind` vaut `rss` ou `email`. `draft_post` s'en sert pour ne pas inventer une source.
	"""
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
	return rss + mail


#romain3
def _show_post(user_id):
	"""Affiche le brouillon du sujet choisi et enregistre la version validée.

	Le brouillon est régénéré quand le sujet change. La zone de texte garde
	les modifications. « Créer le post » enregistre ce texte comme source
	de la vidéo. « Envoyer à Gamma » crée les slides et les sous-titres.
	« Créer la vidéo » assemble images, voix du post et sous-titres.
	"""
	topic = st.session_state.get("chosen_topic")
	if not topic:
		return
	topic_key = topic.get("title") or ""
	if st.session_state.get("post_for") != topic_key:
		try:
			with st.spinner("Rédaction du post…"):
				text = draft_post(
					st.session_state.persona,
					topic,
					_post_articles(user_id),
				)
		except PostError as error:
			st.warning(str(error))
			#romain3
			st.session_state.post_for = topic_key
			st.session_state.post_text = ""
			return
		st.session_state.post_text = text
		st.session_state.post_for = topic_key
		st.session_state.validated_post = ""
	st.subheader("Post")
	st.caption(topic_key)
	st.text_area(
		"Post LinkedIn, 2 à 3 minutes à l'oral. Vous pouvez le modifier.",
		key="post_text",
		height=320,
	)
	minutes = spoken_minutes(st.session_state.post_text)
	st.caption(f"Environ {minutes:.1f} min à l'oral.".replace(".", ","))
	if st.button("Enregistrer la version validée"):
		try:
			saved = save_post_edit(st.session_state.post_text)
		except PostError as error:
			st.warning(str(error))
		else:
			st.session_state.validated_post = saved
	#romain5
	if st.button("Créer le post", key="create_post"):
		try:
			_start_video_flow(st.session_state.post_text)
		except PostError as error:
			st.warning(str(error))
	if st.session_state.get("video_source"):
		#romain7
		st.success("Texte enregistré. Envoie-le à Gamma, puis crée la vidéo.")
		#romain6
		if st.button("Envoyer à Gamma", key="send_gamma"):
			try:
				with st.spinner("Gamma prépare les slides…"):
					send_approved(
						st.session_state.user_id,
						st.session_state.video_source,
					)
			except GammaError as error:
				st.warning(str(error))
			else:
				st.rerun()
		sent = gamma_view(st.session_state.user_id)
		if sent.get("gamma_url"):
			st.markdown(f"[Ouvrir les slides Gamma]({sent['gamma_url']})")
			st.caption(
				f"{sent['slide_count']} slides, une toutes les 10 secondes. "
				"La vidéo parlera la langue des slides. "
				f"Sous-titres : {GAMMA_LANGUAGES.get(sent['subtitle_language'], 'Français')}."
			)
		elif sent.get("job_status") == "pending":
			st.info("Gamma prépare encore les slides. Vérifie-les dans les réglages.")
		#romain7
		if sent.get("gamma_url") and st.button("Créer la vidéo", key="build_video"):
			try:
				with st.spinner("Montage de la vidéo…"):
					build_video(
						st.session_state.user_id,
						st.session_state.video_source,
					)
			except VideoError as error:
				st.warning(str(error))
			else:
				st.rerun()
		video_path = sent.get("video_path") or ""
		if video_path and os.path.isfile(video_path):
			st.video(video_path)
	elif st.session_state.get("validated_post"):
		st.success("Version validée enregistrée. C'est elle qui partira en vidéo.")


def format_delay(seconds):
	return f"{seconds:.1f}".replace(".", ",") + " s"


def latency_line(first_s, transcript_s, total_s):
	return (
		f"Premiers mots {format_delay(first_s)} après réception de l'audio"
		f" · transcription {format_delay(transcript_s)}"
		f" · réponse complète {format_delay(total_s)}"
	)


def voice_line(stt_s, llm_s, tts_s, audio_s=None):
	def part(label, value):
		if value is None:
			return f"{label} —"
		return f"{label} {format_delay(value)}"

	line = " · ".join((
		part("STT", stt_s),
		part("LLM", llm_s),
		part("TTS", tts_s),
	))
	if audio_s is not None:
		line += f" · début de l'audio {format_delay(audio_s)}"
	return line


def show_message(message, autoplay=False):
	"""Affiche un tour. `autoplay` relance la voix après un rafraîchissement."""
	for data_url in message.get("images") or []:
		encoded = data_url.split(",", 1)[1]
		st.image(base64.b64decode(encoded))
	if message.get("content"):
		st.markdown(message["content"])
	if message.get("llm_s") is not None:
		st.caption(voice_line(
			message.get("stt_s"),
			message.get("llm_s"),
			message.get("tts_s"),
			message.get("audio_s"),
		))
	elif message.get("first_s") is not None:
		st.caption(latency_line(
			message["first_s"],
			message["transcript_s"],
			message["total_s"],
		))
	if message.get("speech"):
		#romain5
		st.audio(message["speech"], format="audio/wav", autoplay=autoplay)


def play_chained(wav, speech_chunks, ready_at):
	# Un nouveau lecteur coupe le précédent : on attend que le morceau en cours soit fini.
	if not wav:
		return ready_at, None
	now = time.perf_counter()
	if ready_at and now < ready_at:
		time.sleep(ready_at - now)
	speech_chunks.append(wav)
	#romain5
	# Le rafraîchissement qui affiche « Créer le post » rejoue la voix une fois.
	st.audio(
		wav,
		format="audio/wav",
		autoplay=not st.session_state.get("refresh_composer"),
	)
	started = time.perf_counter()
	return started + wav_seconds(wav), started - run_started


#flux RSS
#persona
def stream_voice_answer(question, images, stt_s, veille, context_path):
	# La synthèse de la première phrase part en parallèle : le modèle continue le texte.
	placeholder = st.empty()
	timing = st.empty()
	timing.caption(voice_line(stt_s, None, None))
	buffer = ""
	played = False
	llm_s = None
	tts_s = None
	audio_s = None
	speech_chunks = []
	sentence = None
	future = None
	ready_at = None
	llm_started = time.perf_counter()
	tts_started = None

	with ThreadPoolExecutor(max_workers=1) as pool:
		for fragment in ask_llm(
			question,
			history=st.session_state.messages,
			images=images,
			voice=True,
			veille=veille,
			context_path=context_path,
		):
			buffer += fragment
			placeholder.markdown(buffer)
			if future is None:
				sentence = first_spoken_sentence(buffer)
				if sentence:
					llm_s = time.perf_counter() - llm_started
					tts_started = time.perf_counter()
					future = pool.submit(speak, sentence)
			if future is not None and not played and future.done():
				played = True
				tts_s = time.perf_counter() - tts_started
				try:
					ready_at, audio_s = play_chained(future.result(), speech_chunks, None)
				except Exception as error:
					st.warning(f"La lecture vocale a échoué : {error}")
				timing.caption(voice_line(stt_s, llm_s, tts_s, audio_s))

		if future is None and buffer.strip():
			llm_s = time.perf_counter() - llm_started
			sentence = None
			tts_started = time.perf_counter()
			future = pool.submit(speak, buffer)
		if future is not None and not played:
			tts_s = time.perf_counter() - tts_started
			try:
				ready_at, audio_s = play_chained(future.result(), speech_chunks, None)
			except Exception as error:
				st.warning(f"La lecture vocale a échoué : {error}")
			timing.caption(voice_line(stt_s, llm_s, tts_s, audio_s))

	if sentence:
		index = buffer.find(sentence)
		rest = buffer[index + len(sentence):].strip() if index >= 0 else ""
		for piece in split_for_speech(text_for_speech(rest)):
			try:
				piece_wav = speak(piece)
			except Exception as error:
				piece_wav = None
				st.warning(f"La suite vocale a échoué : {error}")
				break
			ready_at, _started = play_chained(piece_wav, speech_chunks, ready_at)

	placeholder.markdown(buffer)
	return buffer, combine_speech(speech_chunks), {
		"stt_s": stt_s,
		"llm_s": llm_s,
		"tts_s": tts_s,
		"audio_s": audio_s,
	}


# Base de données
#persona
require_user()
#flux RSS
show_veille()

#persona
#romain5
play_last = st.session_state.pop("play_last_speech", False)
history = st.session_state.messages
last = len(history) - 1
for index, message in enumerate(history):
	with open_message(message["role"]):
		show_message(
			message,
			autoplay=play_last and index == last and message["role"] == "assistant",
		)

#romain4
def _show_composer():
	"""Remplace la barre de chat par un clavier et un micro à maintenir.

	Le clavier ouvre une zone de texte. Le micro enregistre tant que le bouton
	est enfoncé et envoie l'audio au relâchement. Un appui trop court ou sans
	voix affiche `AUDIO_RETRY` et n'appelle pas l'agent. Sous le micro :
	Inspirer, jusqu'à trois titres, puis le post modifiable.
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
		#romain5
		_show_topics(st.session_state.user_id)
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
				st.session_state.pop("refresh_composer", None)
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
	else:
		#romain5
		if st.session_state.pop("refresh_composer", False):
			st.rerun()


def _handle_turn(text="", audio=None, files=None):
	"""Envoie un texte ou un audio à l'agent.

	`text` vient du clavier. `audio` est un WAV déjà jugé assez long.
	Une transcription vide affiche le même message qu'un appui raté.
	« oui », « vas-y » ou une autre indication rédige le sujet déjà donné.
	Une demande explicite (« rédige un post sur… ») rédige tout de suite.
	"""
	parts = []
	typed = (text or "").strip()
	if typed:
		parts.append(typed)
	# L'audio n'entre pas dans l'historique : seule la transcription, comme un texte tapé.
	had_audio = audio is not None
	transcript_s = None
	stt_s = None
	if had_audio:
		stt_started = time.perf_counter()
		spoken = transcribe(audio)
		stt_s = time.perf_counter() - stt_started
		transcript_s = time.perf_counter() - run_started
		#romain4
		if not spoken:
			st.warning(AUDIO_RETRY)
			return
		parts.append(spoken)
	question = "\n".join(parts)
	uploads = list(files or [])
	if len(uploads) > MAX_IMAGES:
		st.warning(f"Seules les {MAX_IMAGES} premières images sont envoyées.")
	images = [prepare_image(uploaded.getvalue()) for uploaded in uploads[:MAX_IMAGES]]

	#romain5
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

	if question or images:
		if not question:
			question = IMAGE_ONLY_QUESTION

		user_message = {"role": "user", "content": question, "images": images}
		#persona
		with open_message("user"):
			show_message(user_message)

		#flux RSS
		#persona
		veille = digest_for(st.session_state.user_id)
		context_path = PERSONAS[st.session_state.persona]["context"]

		# Un message seulement dicté répond à voix haute, sans passer par le clavier.
		voice_reply = (had_audio and not typed) or bool(st.session_state.speak)
		latency = None
		voice_timings = None
		#persona
		with open_message("assistant"):
			speech = None
			if voice_reply:
				response, speech, voice_timings = stream_voice_answer(
					question,
					images,
					stt_s,
					veille,
					context_path,
				)
			else:
				timing = st.empty() if had_audio else None
				if timing is not None:
					timing.caption(f"Transcription {format_delay(transcript_s)}…")
				# Dictionnaire : une fonction imbriquée dans le script ne peut pas utiliser nonlocal.
				seen = {"first_s": None}

				def answer_stream():
					# L'historique déjà affiché part avec la question. ask_llm ajoute la question courante.
					for fragment in ask_llm(
						question,
						history=st.session_state.messages,
						images=images,
						veille=veille,
						context_path=context_path,
					):
						if had_audio and seen["first_s"] is None:
							seen["first_s"] = time.perf_counter() - run_started
							timing.caption(
								f"Premiers mots {format_delay(seen['first_s'])} après réception de l'audio"
								f" · transcription {format_delay(transcript_s)}"
							)
						yield fragment

				# write_stream affiche chaque fragment. Il renvoie le texte recollé.
				response = st.write_stream(answer_stream())
				if had_audio:
					total_s = time.perf_counter() - run_started
					first_s = seen["first_s"] if seen["first_s"] is not None else total_s
					timing.caption(latency_line(first_s, transcript_s, total_s))
					latency = {
						"first_s": first_s,
						"transcript_s": transcript_s,
						"total_s": total_s,
					}

		st.session_state.messages.append(user_message)
		assistant_message = {"role": "assistant", "content": response}
		if latency:
			assistant_message.update(latency)
		if voice_timings:
			assistant_message.update(voice_timings)
		if speech:
			assistant_message["speech"] = speech
			#romain5
			if st.session_state.get("refresh_composer"):
				st.session_state.play_last_speech = True
		st.session_state.messages.append(assistant_message)
		#romain1
		update_conversation_history("user", question, images or None)
		update_conversation_history("assistant", response)
		# Base de données
		add_message(st.session_state.user_id, "user", question, images)
		add_message(st.session_state.user_id, "assistant", response)


#romain4
_show_composer()
