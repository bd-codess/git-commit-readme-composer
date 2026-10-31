"""Git-Commit & Readme Composer (Google Gemini edition)
Single-screen Streamlit utility: paste code or changes -> get a README.md draft
and Conventional Commit message options.

Run:  streamlit run app.py
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

# ---------------------------------------------------------------- config ----
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")  # check AI Studio for current names
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")  # lighter backup
THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low")  # low = fast; "" keeps the model default
MAX_INPUT_CHARS = 20_000
MAX_RETRIES = 2  # attempts per model for temporary errors (503/429/500/504)
REQUEST_TIMEOUT_MS = 15_000  # give up on a slow request after 15 seconds
README_MAX_TOKENS = 2048
COMMIT_MAX_TOKENS = 1024

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
Use exactly these sections, in this order:

# <Project Title>
<one-sentence description>

## Features
- short bullet list

## Tech Stack
- languages, frameworks, libraries detected in the code

## Installation
numbered steps with fenced shell commands

## Usage
fenced example showing how to run or use the code

## License
MIT (placeholder)
"""

COMMIT_PROMPT = CORE_PROMPT + """

TASK: Write git commit messages for the provided code changes, following the
Conventional Commits 1.0.0 specification exactly.

Format of each message:
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]

Rules:
- Types: feat (adds a new feature), fix (fixes a bug), docs, style, refactor,
  perf, test, build, ci, chore, revert. Use feat ONLY for new features and fix
  ONLY for bug fixes.
- Type and scope are lowercase. The scope is a noun in parentheses, e.g. (auth).
- The description follows the colon and a space. Use imperative mood, keep it
  under 72 characters, with no trailing period.
- The body, if present, starts one blank line after the description.
- Footers start one blank line after the body, in the form `Token: value`
  or `Token #value` (e.g. `Refs: #123`). Tokens use hyphens instead of spaces.
- If the change breaks an existing interface, mark it with `!` before the colon
  and/or add a footer `BREAKING CHANGE: <description>` in uppercase.
- For a revert, use the type revert and a `Refs:` footer if a commit hash is
  known.

Output exactly three options. Put each option in its own fenced code block so
it can be copied directly into git, with only a bold label line before each
block, like **Option 1 (recommended)**. Make the options meaningfully
different (type, scope or level of detail). If the input mixes unrelated
changes, add one final line: "Tip: split this into separate commits."
"""

TONE_SUFFIX = {
    "Concise": "\n\nStyle: be brief. Keep the README under 200 words and commit bodies under 2 lines.",
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


RETRYABLE = (429, 500, 503, 504)


def make_config(system_prompt: str, max_tokens: int, use_thinking: bool):
    kwargs = {"system_instruction": system_prompt, "max_output_tokens": max_tokens}
    if use_thinking and THINKING_LEVEL:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING_LEVEL)
    return types.GenerateContentConfig(**kwargs)


def generate(api_key: str, system_prompt: str, max_tokens: int, code: str, language: str) -> str:
    """Call the model fast: low thinking, short timeout, retry, then fall back."""
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
    )
    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL and FALLBACK_MODEL != MODEL else [])
    contents = f"Language: {language}\n\n<code>\n{code}\n</code>"
    use_thinking = True
    last_error = None
    for model in models:
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=make_config(system_prompt, max_tokens, use_thinking),
                )
                return (response.text or "").strip()
            except errors.APIError as e:
                last_error = e
                if e.code == 400 and use_thinking and "think" in str(e).lower():
                    use_thinking = False  # this model rejects the thinking setting
                    continue
                attempt += 1
                if e.code in RETRYABLE and attempt < MAX_RETRIES:
                    time.sleep(1)
                    continue
                break  # permanent error or retries used up: try the next model
            except Exception as e:  # timeouts and network errors: move on quickly
                last_error = e
                break
    raise last_error


@st.cache_resource
def get_cache() -> dict:
    """Server-side memory of finished results so repeat demos are instant."""
    return {}


def run_pipeline(code: str, language: str, tone: str) -> None:
    """Generate both artifacts (in parallel) and store them in session state."""
    suffix = TONE_SUFFIX.get(tone, "")
    cache = get_cache()
    key = (code, language, tone, MODEL)
    start = time.perf_counter()
    if key in cache:
        st.session_state.readme, st.session_state.commits = cache[key]
        st.session_state.elapsed = (time.perf_counter() - start, True)
        return
    try:
        with st.spinner("Generating README and commit messages..."):
            api_key = get_api_key()  # read in the main thread
            with ThreadPoolExecutor(max_workers=2) as pool:  # run both calls at once
                readme_job = pool.submit(generate, api_key, README_PROMPT + suffix, README_MAX_TOKENS, code, language)
                commits_job = pool.submit(generate, api_key, COMMIT_PROMPT + suffix, COMMIT_MAX_TOKENS, code, language)
                readme, commits = readme_job.result(), commits_job.result()
        st.session_state.readme = readme
        st.session_state.commits = commits
        st.session_state.elapsed = (time.perf_counter() - start, False)
        if len(cache) >= 50:
            cache.clear()
        cache[key] = (readme, commits)
    except errors.APIError as e:
        if e.code in (401, 403):
            st.error("Invalid or missing API key. Check your .env file or Streamlit secrets.")
        elif e.code == 429:
            st.warning("Rate limit reached. Please wait a minute and try again.")
        elif e.code in (500, 503, 504):
            st.warning("The AI model is busy right now (temporary). Please try again in a minute.")
        else:
            st.error(f"API error ({e.code}): {e.message}")
    except Exception as e:  # keep the demo alive no matter what
        st.error(f"Unexpected error: {e}")


def clear_input() -> None:
    """Button callback: empty the input box in one click."""
    st.session_state.code_input = ""


# --------------------------------------------------------------------- UI ---
st.set_page_config(page_title="Git-Commit & Readme Composer", page_icon="📝", layout="wide")

st.markdown(
    """
    <style>
    /* Palette: #b38cb4 Amethyst Smoke, #b7918c Rosy Taupe, #c5a48a Tan,
       #ddc67b Golden Sand, #f8f272 Canary Yellow */
    textarea { border: 1.5px solid #b7918c !important; border-radius: 8px !important; }
    textarea:focus { border-color: #ddc67b !important; box-shadow: 0 0 0 2px rgba(221,198,123,0.35) !important; }
    h1 { color: #ddc67b; }
    h2, h3 { color: #b38cb4; }
    /* dark text on the light gold primary button for readability */
    button[kind="primary"] p,
    button[data-testid="stBaseButton-primary"] p { color: #1c1720 !important; font-weight: 600; }
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
        key="code_input",
        height=380,
        placeholder="Paste modified code, a git diff, or rough notes here...",
    )
    st.caption(f"{len(code):,} / {MAX_INPUT_CHARS:,} characters")
    gen_col, clear_col = st.columns([3, 1])
    run = gen_col.button("✨ Generate", type="primary", use_container_width=True)
    clear_col.button("🗑 Clear", on_click=clear_input, use_container_width=True)

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
    if "elapsed" in st.session_state:
        secs, hit = st.session_state.elapsed
        st.caption(f"⚡ {'Loaded from cache' if hit else 'Generated'} in {secs:.1f}s")
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
            st.caption("Hover over an option and use its copy icon to copy a single commit message.")
            st.markdown(st.session_state.commits)  # each option renders as its own copyable code block
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
