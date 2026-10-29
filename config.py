# Réglages du projet. Un autre groupe change les modèles ici, pas dans le reste du code.

# Clé lue dans .env. Le fichier .env n'est pas versionné.
ENV_KEY = "GROQ_KEY"
CONTEXT_PATH = "context.txt"

# gpt-oss lit le texte. Le plus petit sert aux réponses vocales. qwen3.8 lit aussi les images.
TEXT_MODEL = "openai/gpt-oss-120b"
FAST_MODEL = "openai/gpt-oss-20b"
VISION_MODEL = "qwen/qwen3.8-27b"
WHISPER_MODEL = "whisper-large-v3-turbo"

# Orpheus remplace PlayAI. 200 caractères maximum par requête, voix anglaise.
TTS_MODEL = "canopylabs/orpheus-v1-english"
TTS_VOICE = "troy"
TTS_MAX_CHARS = 200
FRENCH_VOICE = "Thomas"

LANGUAGE_INSTRUCTION = (
    "Tu réponds toujours en français. "
    "Tu n'écris jamais en anglais, même pour refuser."
)
VOICE_INSTRUCTION = (
    "L'utilisateur t'écoute et ne te lit pas. "
    "Chaque réplique fait entre 150 et 300 caractères, environ 2 à 4 phrases courtes. "
    "Cette longueur prime sur les autres consignes de longueur, y compris quand tu refuses. "
    "Si tu refuses, reste dans ton rôle, dis pourquoi, et propose autre chose. "
    "Pas de liste, pas de markdown, pas d'emoji."
)
VOICE_RETRY = (
    "Ta réponse était trop courte ou en anglais. "
    "Réécris-la en français, entre 150 et 300 caractères. "
    "Si tu dois refuser, refuse dans ton rôle et change de sujet, "
    "sans expliquer comment nuire."
)

# Groq accepte au plus 3 images par requête, et 20 Mo pour toute la requête.
MAX_IMAGES = 3
MAX_SIDE = 1280
MAX_JPEG_BYTES = 4 * 1024 * 1024

# Délai d'un appel, en secondes. Au-delà, l'interface dit que le délai est dépassé.
REQUEST_TIMEOUT = 60
MAX_RETRIES = 1

PAGE_TITLE = "Jarvis"
APP_TITLE = "Barbe-Quasar"
CHAT_PLACEHOLDER = "Quel sujet voulez-vous publier ?"
IMAGE_ONLY_QUESTION = "Que vois-tu sur cette image ?"

# Base de données
# Le dossier data/ est créé au premier compte. Le fichier .db n'est pas versionné.
DB_PATH = "data/jarvis.db"

#flux RSS
# Un site lent ne bloque pas les autres au-delà de ce délai, en secondes.
RSS_TIMEOUT = 15
RSS_USER_AGENT = "BarbeQuasarVeille/1.0"
# Articles gardés par flux à chaque rafraîchissement, puis nombre envoyé au modèle.
RSS_ITEMS_PER_FEED = 5
RSS_ITEMS_IN_PROMPT = 12
RSS_SUMMARY_CHARS = 400

#flux_rss_email
# IMAP Gmail. Le mot de passe d'application reste dans la base locale, pas dans git.
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
MAIL_SUBJECT = "newsletter"
MAIL_MAX = 30
MAIL_ITEMS_IN_PROMPT = 8
MAIL_TIMEOUT = 60

#romain2
X_TOKEN_KEY = "X_BEARER_TOKEN"
# France. L'API X ne connaît pas le persona, seulement un lieu.
WOEID_FRANCE = 23424819
TRENDS_TIMEOUT = 8
MAX_TRENDS = 10
MAX_TOPICS = 5

#romain4
# Le bouton Inspirer affiche trois sujets, pas la liste entière.
INSPIRE_COUNT = 3
# Un appui trop court ou sans voix ne part pas à l'agent.
AUDIO_MIN_SECONDS = 0.45
AUDIO_MIN_PEAK = 0.02
AUDIO_RETRY = "Refaites l'audio"

#romain6
# Une slide toutes les 10 secondes. 2 min 30 font 15 slides, pas plus.
# La clé est celle du propriétaire, dans .env. Tous les comptes l'utilisent.
GAMMA_KEY = "GAMMA_API_KEY"
GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
SLIDE_SECONDS = 10
VIDEO_MAX_SECONDS = 150
GAMMA_TIMEOUT = 60
GAMMA_POLL_SECONDS = 5
GAMMA_POLL_TRIES = 6
#romain7
# L'export PNG est une archive, une image par slide. Trois minutes d'attente.
EXPORT_POLL_TRIES = 36
VIDEO_DOWNLOAD_TIMEOUT = 120
DEFAULT_SLIDE_LANGUAGE = "fr"
DEFAULT_SUBTITLE_LANGUAGE = "fr"
# Codes acceptés par textOptions.language. La vidéo parle cette langue.
GAMMA_LANGUAGES = {
    "fr": "Français",
    "en": "Anglais",
    "en-gb": "Anglais (Royaume-Uni)",
    "es": "Espagnol",
    "de": "Allemand",
    "it": "Italien",
    "pt-br": "Portugais (Brésil)",
    "nl": "Néerlandais",
    "pl": "Polonais",
    "ar": "Arabe",
    "zh-cn": "Chinois simplifié",
    "ja": "Japonais",
    "ko": "Coréen",
    "ru": "Russe",
    "tr": "Turc",
    "hi": "Hindi",
    "vi": "Vietnamien",
}

#avatar
# La clé reste dans .env. Le script ne la recopie nulle part.
NVIDIA_KEY = "NVIDIA_API_KEY"
A2F_TARGET = "grpc.nvcf.nvidia.com:443"
# Modèle Claire publié sur build.nvidia.com, avec la langue.
A2F_FUNCTION_ID = "0961a6da-fb9e-4f2e-8491-247e5fd7bf8d"

#romain3
# 150 mots par minute à l'oral. 280 à 480 mots font environ 2 à 3 minutes.
POST_WORDS_PER_MINUTE = 150
POST_MIN_WORDS = 280
POST_MAX_WORDS = 480

#flux_rss_email
# Mots sans accent. La newsletter est retenue si l'un d'eux est un mot du sujet ou du résumé.
PERSONA_MAIL_KEYWORDS = {
    "veille_tech": (
        "intelligence artificielle", "ia", "ai", "llm", "nvidia", "gpu",
        "logiciel", "software", "developpeur", "developer", "programmation",
        "python", "javascript", "android", "iphone", "smartphone",
        "startup", "open source", "github", "cloud", "cybersecurite",
        "puce", "semiconducteur", "robot", "algorithme", "devops",
        "framework", "silicon", "chip",
    ),
    "veille_finance": (
        "bourse", "finance", "economie", "inflation", "investissement",
        "invest", "trading", "bitcoin", "crypto", "cryptomonnaie",
        "nasdaq", "cac", "dividende", "banque", "taux", "marche",
        "wall street", "fed", "bce", "pib", "fiscalite", "epargne",
        "patrimoine", "obligation", "fintech", "cotation", "fonds",
    ),
}

VEILLE_INSTRUCTION = (
    "Une veille récente est collée sous cette consigne. "
    "Quand tu t'en sers, cite le titre et le lien de l'article. "
    "Si la veille ne contient pas la réponse, dis-le, puis réponds avec ce que tu sais. "
    "Tu n'inventes pas un article, un chiffre ou une citation."
)

#persona
# context et avatar restent ceux du Capitaine.
# Deux Jarvis plus tard : un fichier de rôle et une image par persona.
PERSONAS = {
    "veille_tech": {
        "label": "Veille technologique",
        "context": CONTEXT_PATH,
        "avatar": None,
    },
    "veille_finance": {
        "label": "Veille financière et économique",
        "context": CONTEXT_PATH,
        "avatar": None,
    },
}

#flux RSS
#persona
# (nom affiché, site d'origine, url du flux XML)
PERSONA_FEEDS = {
    "veille_tech": [
        ("Journal du Net", "https://journaldunet.com", "https://www.journaldunet.com/intelligence-artificielle/rss/"),
        ("TechCrunch", "https://techcrunch.com", "https://techcrunch.com/feed/"),
        ("The Verge", "https://theverge.com", "https://www.theverge.com/rss/index.xml"),
        ("Frandroid", "https://frandroid.com", "https://www.frandroid.com/feed"),
        ("MIT Technology Review", "https://technologyreview.com", "https://www.technologyreview.com/feed/"),
        ("Y Combinator", "https://ycombinator.com", "https://www.ycombinator.com/blog/feed/"),
        ("InfoQ", "https://infoq.com", "https://feed.infoq.com/"),
        ("DEV", "https://dev.to", "https://dev.to/feed"),
    ],
    "veille_finance": [
        ("Investing.com", "https://investing.com", "https://www.investing.com/rss/news.rss"),
        ("Business Insider", "https://businessinsider.com", "https://feeds.businessinsider.com/custom/all"),
        ("EasyBourse", "https://easybourse.com", "https://www.easybourse.com/feeds/media/"),
        ("BNP Paribas Eco Week", "https://economic-research.bnpparibas.com/RSS/fr-FR", "https://economic-research.bnpparibas.com/RSS/fr-FR/Eco-Week"),
        ("economie.gouv.fr", "https://economie.gouv.fr", "https://www.economie.gouv.fr/rss/toutesactualites"),
        ("Financial Times", "https://ft.com", "https://www.ft.com/rss/home/international"),
        ("Cointelegraph", "https://cointelegraph.com", "https://cointelegraph.com/rss"),
        ("Cryptoast", "https://cryptoast.com", "https://cryptoast.fr/feed/"),
    ],
}
