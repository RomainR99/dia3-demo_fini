# Tests à faire

26 tests à faire. 21 déjà faits. 47 au total.

✅ essai déjà exécuté. ☐ pas encore fait.

Les essais cochés ont été lancés à la main, le 22 octobre 2026, pas par une suite automatique.

## Comptes et séparation

| | Test |
| --- | --- |
| ✅ | Créer un compte veille technologique enregistre ses 8 flux, pas ceux de la finance. |
| ✅ | Créer un compte veille financière enregistre Investing, EasyBourse, BNP, economie.gouv.fr, FT, Cointelegraph, Cryptoast. |
| ✅ | Un deuxième compte avec le même nom est refusé. |
| ✅ | Un nom de moins de 3 caractères ou un mot de passe de moins de 4 est refusé. |
| ✅ | Un mauvais mot de passe ne connecte pas. |
| ✅ | Le même nom avec une autre casse retrouve le bon persona. |
| ✅ | L'historique du premier compte n'apparaît pas dans le second. |
| ☐ | Dans l'interface, Quitter le bord puis ouvrir le compte B : pas d'adresse Gmail du compte A, pas de ses newsletters. |
| ☐ | L'agent du compte B ne cite pas un objet de newsletter du compte A. |
| ☐ | La requête SQL du ticket `jira.md` montre chaque newsletter à côté d'un seul nom de compte. |

## Flux RSS

| | Test |
| --- | --- |
| ✅ | `fetch_entries` lit le flux Frandroid et sort des titres. |
| ✅ | Le rafraîchissement des 8 flux techno se termine sans erreur. |
| ✅ | Le rafraîchissement des 8 flux finance se termine sans erreur. |
| ✅ | L'extrait envoyé au modèle contient des titres et des liens de ces flux. |
| ☐ | Décocher un flux, rafraîchir : ses articles ne sont plus dans l'extrait. |
| ☐ | Un site injoignable affiche une erreur dans la barre, les autres flux restent lisibles. |
| ☐ | Après fermeture de la page, le même compte retrouve ses messages. |

## Gmail et thème

| | Test |
| --- | --- |
| ✅ | Le mois précédent d'octobre 2026 est le 1er septembre inclus, le 1er octobre exclu. |
| ✅ | Les dates IMAP sont `01-Sep-2026` et `01-Oct-2026`. |
| ✅ | Un e-mail HTML sans partie texte donne un sujet, une date et un résumé. |
| ✅ | Une adresse ou un mot de passe vide est refusé avant l'appel réseau. |
| ✅ | Un faux mot de passe d'application produit la phrase « Gmail a refusé la connexion ». |
| ✅ | NVIDIA et « AI » passent pour la veille techno, pas pour la finance. |
| ✅ | Une newsletter inflation et marchés passe pour la finance, pas pour la techno. |
| ✅ | La Minute Transilien ne passe pour aucun des deux thèmes. |
| ✅ | « Newsletter IA » passe pour la techno. |
| ✅ | La boîte connectée du compte techno a été relue : 1 newsletter hors thème laissée de côté, 2 retenues. |
| ☐ | La barre affiche « retenues pour : Veille technologique » et n'y met pas Transilien. |
| ☐ | Reposer la question des newsletters : l'agent cite un objet retenu, pas un filtre Gmail inventé. |
| ☐ | Un compte finance connecté à une autre boîte ne reçoit pas les newsletters techno. |
| ☐ | Déconnecter Gmail efface les newsletters de ce compte et laisse les flux RSS. |

## Dialogue

| | Test |
| --- | --- |
| ☐ | Une question hors veille reçoit une réponse, et l'agent dit que la veille ne contient pas le sujet. |
| ☐ | Une question sur un article RSS cite son titre et son lien. |
| ☐ | Une photo jointe part encore au modèle vision. |
| ☐ | Une réponse vocale reste en français et cite la veille sans lire les douze articles en entier. |
| ☐ | Une clé Groq absente ou fausse s'affiche comme un message, pas comme une trace Python. |

## Cible, rien de ceci n'est codé

| | Test |
| --- | --- |
| ☐ | L'agent propose des sujets techno au compte techno, et des sujets économie au compte finance. |
| ☐ | Un sujet s'appuie sur un flux RSS, une newsletter retenue, ou une tendance Twitter du thème. |
| ☐ | Twitter indisponible n'empêche pas les sujets tirés du RSS et des newsletters. |
| ☐ | Le sujet choisi produit un texte parlable de 2 à 3 minutes. |
| ☐ | L'utilisateur modifie le texte, et la version validée est celle qui part en vidéo. |
| ☐ | La vidéo a du son et des sous-titres alignés sur le texte validé. |
| ☐ | Sans Canva, la vidéo part quand même sur le serveur Discord du compte. |
| ☐ | Avec Canva, le message Discord contient la vidéo et le lien d'édition. |
| ☐ | Après une modification des slides, « Reprendre mon Canva » reconstruit la vidéo avec les nouvelles images, la même voix et les sous-titres. |
| ☐ | Un lien Canva collé à la main, sans identifiant de design, est refusé avec une phrase claire. |
| ☐ | Une vidéo trop lourde pour Discord part comme un lien, pas comme un fichier rejeté. |
