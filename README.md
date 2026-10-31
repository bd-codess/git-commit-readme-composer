# Git-Commit & Readme Composer

Paste code, a git diff or rough notes and get a ready-to-edit `README.md` plus three Conventional Commit messages, all on one screen. Built with Streamlit and Google Gemini.

## Features

- Generates a README draft (title, features, tech stack, installation, usage, license) and three Conventional Commits 1.0.0 options in parallel
- Language selector (12 options, including Other / Mixed) and a Concise / Detailed output style
- Copy the README, download it as `README.md`, or preview it rendered
- Each commit option sits in its own copy-ready code block
- Prompts forbid invented files, commands or dependencies; unknown details become TODOs
- Reliability: 15 s request timeout, 2 attempts per model on temporary errors (429, 500, 503, 504), automatic fallback to a lighter model, and an in-memory cache for repeat inputs
- Sidebar "Time Saved Calculator" that estimates minutes saved (assumes ~1.5 min per commit message and ~15 min per README)

## Tech Stack

- Python 3.10+
- [Streamlit](https://streamlit.io) for the UI
- [google-genai](https://pypi.org/project/google-genai/) SDK for Gemini
- python-dotenv for local configuration

## Installation

1. Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/).
2. Clone this repository and open a terminal in its folder.
3. (Recommended) create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Create your environment file and add your key:

   ```bash
   cp .env.example .env             # Windows: copy .env.example .env
   ```

   Then edit `.env` and set `GEMINI_API_KEY=your_key_here`.

6. (Optional) apply the plum and gold theme by placing `config.toml` in a `.streamlit` folder:

   ```bash
   mkdir -p .streamlit && cp config.toml .streamlit/config.toml
   ```

## Usage

```bash
streamlit run app.py
```

Open http://localhost:8501, then:

1. Choose a language and an output style.
2. Paste code, a diff or notes (up to 20,000 characters; longer input is truncated).
3. Click **Generate**.
4. Use the **README.md** tab to copy, download or preview the README, and the **Git Commit Logs** tab to copy a commit message.

### Configuration

All settings are optional except the API key.

| Variable | Purpose | Default in `app.py` |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key (required) | none |
| `GEMINI_MODEL` | Primary model | `gemini-3.8-flash` |
| `GEMINI_FALLBACK_MODEL` | Backup model if the primary keeps failing | `gemini-3.5-flash-lite` |
| `GEMINI_THINKING_LEVEL` | `low` is fastest; empty keeps the model default | `low` |

Model names change over time. If a call fails with a "model not found" error, check Google AI Studio for current names and set `GEMINI_MODEL`.

When deploying on Streamlit Community Cloud, add `GEMINI_API_KEY` under **App settings > Secrets** instead of using `.env`.

## Project structure

```
app.py            # the whole app: prompts, Gemini calls, UI
requirements.txt  # Python dependencies
.env.example      # template for your API key
.streamlit/
  config.toml     # optional theme
```

## Design notes

- **Two focused prompts, run in parallel.** One prompt per artifact keeps each format strict, and a thread pool means the wait is roughly the slower call.
- **Built to survive a live demo.** Short timeout, bounded retries, fallback model and a cache.
- **Trustworthy output.** The prompts enforce the Conventional Commits 1.0.0 rules and a fixed README structure.

## Known limitations

- Due to the usage of a free API(The API we are currently using is FROM GEMINI AI , THE MODEL IS "      "), we may face certain issue like delayed and slow output , this can be solved in near future by using an improved and advanced paid API .
- Input is truncated at 20,000 characters.
- The cache is in server memory only and is cleared after 50 entries.
- Requires a Gemini API key and network access.

## Team

TODO: add team name and members.

## License

MIT (placeholder)
