Copilote de prospection (M&A / Transaction Services / Transaction Tax) orienté LinkedIn & réseaux sociaux, basé sur AutoGen (AgentChat) + DeepSeek, avec une approche **compliance-by-design**.

## Ce que fait le projet
- Ingestion manuelle de leads (CSV) : URL LinkedIn, nom, poste, entreprise, localisation, track (MA/TS/TT).
- Scoring déterministe + priorisation (A/B/C).
- Génération de messages LinkedIn prêts à envoyer :
  - Personae : DECIDER / RELAY / PEER
  - Langues : FR / EN
  - Variantes : ULTRA / STANDARD / WARM
- Gestion de pipeline : statuts, dates, relances J+3/J+7/J+14, journal d’événements.
- Tableaux “Next Actions” + Scorecard hebdo.

## Conformité (important)
- **Aucun scraping** automatisé.
- **Aucun envoi automatique** sur LinkedIn/RS.
- Human-in-the-loop : Maeva envoie manuellement.
- Aucune “invention” de données : les messages utilisent uniquement les champs du CSV.

## Prérequis
- Python 3.12+
- uv
- Une clé DeepSeek (API compatible OpenAI)

## Installation
```bash
uv init
uv venv
uv add "autogen-agentchat==0.5.1" "autogen-ext[openai]==0.5.1" python-dotenv pandas pydantic rich