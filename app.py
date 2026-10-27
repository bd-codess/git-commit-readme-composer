"""Git-Commit & Readme Composer (Google Gemini edition)
Single-screen Streamlit utility: paste code or changes -> get a README.md draft
and Conventional Commit message options.

Run:  streamlit run app.py
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

# ---------------------------------------------------------------- config ----
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # check AI Studio for current names
MAX_INPUT_CHARS = 20_000
MAX_OUTPUT_TOKENS = 4096  # Gemini 2.5 counts internal thinking tokens too

LANGUAGES = [
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go",
    "Rust", "PHP", "Ruby", "HTML/CSS", "Other / Mixed",
]

# --------------------------------------------------------------- prompts ----
CORE_PROMPT = (
    "You are an expert technical documentation engine and version control "
    "systems engineer. Your sole task is to process raw code dumps and return "
    "highly accurate software artifacts. You must output only the requested "
    "artifact, with no conversational filler, no pleasantries, no preamble and "
    "no closing summary. Focus exclusively on extracting dependencies, usage "
    "structures, and clean developer notes. Never invent features, files, "
    "commands or dependencies that are not supported by the input; if "
    "something is unknown, write a short TODO placeholder instead."
)

README_PROMPT = CORE_PROMPT + """

TASK: Write a README.md for the provided code.
Output raw markdown only (do not wrap the whole answer in a code fence).
Use exactly these sections, in this order, skipping none:

# <Project Title>
<one-sentence description>

## Features
- bullet list

## Tech Stack
- languages, frameworks, libraries detected in the code

## Installation
numbered steps with fenced shell commands

## Usage
fenced example showing how to run or use the code

## Project Structure
short list of the files/functions visible in the input

## Contributing
2-3 lines

## License
MIT (placeholder)
"""

COMMIT_PROMPT = CORE_PROMPT + """

TASK: Write git commit messages for the provided code changes, following the
Conventional Commits standard. Allowed types: feat, fix, docs, style,
refactor, perf, test, build, ci, chore.

Output exactly three options, formatted like this and nothing else:

### Option 1 (recommended)
`type(scope): imperative summary under 72 characters`

Optional body: 1-3 lines explaining what and why.

### Option 2
...

### Option 3
...

Rules: imperative mood, lowercase type, no trailing period in the summary,
each option must differ meaningfully (e.g. different type, scope or detail
level). Add `BREAKING CHANGE:` in the body only if the input clearly breaks
an existing interface.
"""

TONE_SUFFIX = {
    "Concise": "\n\nStyle: keep everything as short as possible.",
    "Detailed": "\n\nStyle: be thorough and include helpful extra detail.",
}


# ---------------------------------------------------------------- helpers ---
def get_api_key() -> str | None:
    """Read the key from Streamlit secrets (deployed) or env/.env (local)."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # no secrets.toml locally
    return os.getenv("GEMINI_API_KEY")


def generate(system_prompt: str, code: str, language: str) -> str:
    """Call the model once and return the text. Raises on failure."""
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Language: {language}\n\n<code>\n{code}\n</code>",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )
    return (response.text or "").strip()


def run_pipeline(code: str, language: str, tone: str) -> None:
    """Generate both artifacts and store them in session state."""
    suffix = TONE_SUFFIX.get(tone, "")
    try:
        with st.spinner("Generating README and commit messages..."):
            st.session_state.readme = generate(README_PROMPT + suffix, code, language)
            st.session_state.commits = generate(COMMIT_PROMPT + suffix, code, language)
    except errors.APIError as e:
        if e.code in (401, 403):
            st.error("Invalid or missing API key. Check your .env file or Streamlit secrets.")
        elif e.code == 429:
            st.warning("Rate limit reached. Please wait a minute and try again.")
        else:
            st.error(f"API error ({e.code}): {e.message}")
    except Exception as e:  # keep the demo alive no matter what
        st.error(f"Unexpected error: {e}")


# --------------------------------------------------------------------- UI ---
st.set_page_config(page_title="Git-Commit & Readme Composer", page_icon="📝", layout="wide")

st.markdown(
    """
    <style>
    textarea { border: 1.5px solid #cbd5e1 !important; border-radius: 8px !important; }
    textarea:focus { border-color: #6366f1 !important; box-shadow: 0 0 0 2px #c7d2fe !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📝 Git-Commit & Readme Composer")
st.caption("Paste your code or changes. Get a clean README and semantic commit messages in seconds.")

left, right = st.columns(2, gap="large")

with left:
    st.subheader("Input")
    language = st.selectbox("Language", LANGUAGES)
    tone = st.radio("Output style", ["Concise", "Detailed"], horizontal=True)
    code = st.text_area(
        "Code, diff or notes",
        height=380,
        placeholder="Paste modified code, a git diff, or rough notes here...",
    )
    st.caption(f"{len(code):,} / {MAX_INPUT_CHARS:,} characters")
    run = st.button("✨ Generate", type="primary", use_container_width=True)

if run:
    if not code.strip():
        left.warning("Please paste some code or notes first.")
    elif not get_api_key():
        left.error("No API key found. Add GEMINI_API_KEY to .env or Streamlit secrets.")
    else:
        if len(code) > MAX_INPUT_CHARS:
            left.info(f"Input truncated to the first {MAX_INPUT_CHARS:,} characters.")
            code = code[:MAX_INPUT_CHARS]
        run_pipeline(code, language, tone)

with right:
    st.subheader("Output")
    tab_readme, tab_commits = st.tabs(["README.md", "Git Commit Logs"])

    with tab_readme:
        if "readme" in st.session_state:
            st.caption("Use the copy icon at the top-right of the block.")
            st.code(st.session_state.readme, language="markdown")
            st.download_button(
                "⬇ Download README.md",
                st.session_state.readme,
                file_name="README.md",
                mime="text/markdown",
            )
            with st.expander("Preview rendered README"):
                st.markdown(st.session_state.readme)
        else:
            st.info("Your README will appear here.")

    with tab_commits:
        if "commits" in st.session_state:
            st.caption("Use the copy icon at the top-right of the block.")
            st.code(st.session_state.commits, language="markdown")
        else:
            st.info("Your commit message options will appear here.")

# Impact calculator for the judges' "quantifiable impact" slide
with st.sidebar:
    st.header("⏱ Time Saved Calculator")
    devs = st.number_input("Developers on team", 1, 100, 4)
    commits = st.number_input("Commits per dev per sprint", 1, 200, 20)
    sprints = st.number_input("Sprints", 1, 50, 3)
    # assumptions: ~1.5 min per hand-written good commit, 15 min per README
    saved = devs * commits * sprints * 1.5 + devs * 15
    st.metric("Estimated minutes saved", f"{saved:,.0f}")
    st.caption("Assumes ~1.5 min per commit message and ~15 min per README.")
