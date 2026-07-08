# Plain Law

> Legislation in plain English — powered by a local AI model.

Plain Law monitors federal, state, county, and municipal legislation and rewrites it in language any adult can understand. Summaries are generated locally using [Gemma](https://ollama.com/library/gemma3) via Ollama and published to GitHub Pages.

No corporate API. No subscription. Your hardware, your model, your words.

---

## How It Works

1. The pipeline reads `sources/` to find enabled data sources
2. New bills are fetched from APIs, RSS feeds, or scraped pages
3. Each bill is summarized by a local Gemma model in plain English
4. Summaries are pushed to the `gh-pages` branch as static Markdown/HTML

## Adding a Locale

Want to add your state, county, or city? See [CONTRIBUTING.md](CONTRIBUTING.md). It's just a YAML file — no code required.

## Setup

```bash
git clone <your-gitea-url>/plain-law
cd plain-law
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
# Edit pipeline/config.yaml with your Ollama host
python pipeline/main.py --dry-run
```

## Running the Pipeline

```bash
# Dry run (print summaries, don't publish)
python pipeline/main.py --dry-run

# Full run (summarize + push to GitHub Pages)
python pipeline/main.py
```

## Configuration

- `pipeline/config.yaml` — model, output, schedule settings
- `sources/` — locale source files (see CONTRIBUTING.md)

## Project Structure

```
plain-law/
├── sources/
│   ├── _schema.yaml          # Source file schema reference
│   ├── federal/
│   │   └── congress.yaml
│   ├── states/
│   │   └── nj.yaml
│   ├── counties/
│   │   └── nj-camden.yaml
│   └── municipalities/
├── pipeline/
│   ├── config.yaml           # Pipeline config
│   ├── main.py               # Entry point
│   ├── summarizer.py         # Ollama/Gemma interface
│   ├── publisher.py          # GitHub Pages output
│   ├── dedup.py              # Skip already-processed bills
│   ├── fetchers/             # API, RSS, scrape fetchers
│   └── prompts/
│       └── summarize.txt     # Prompt template
├── output/                   # Generated summaries (gitignored)
├── requirements.txt
└── .env.example
```

## License

MIT
