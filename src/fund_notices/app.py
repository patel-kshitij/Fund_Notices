"""A small web page that shows the tool reading one PDF at a time.

Run with: FUND_NOTICES_MODEL=qwen3:4b .venv/bin/streamlit run src/fund_notices/app.py

Everything runs on this laptop with the local model. No document leaves the machine.
Streamlit runs this whole file again on every click, so slow setup is cached
with st.cache_resource and the last result is kept in st.session_state.
"""

import hashlib
import time
from pathlib import Path

import streamlit as st

from fund_notices.demo import choice_label, field_rows, without_frontmatter
from fund_notices.llm import CachedClient, OllamaClient, model_from_env
from fund_notices.pdftext import pdf_text
from fund_notices.pipeline import NoticeReader, load_split
from fund_notices.render import SYNTHETIC_LINE
from fund_notices.retrieve import minilm_embedder
from fund_notices.schema import AnswerFile

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / "data" / "test"


@st.cache_resource(show_spinner="Training the classifier and loading MiniLM...")
def get_reader() -> tuple[NoticeReader, CachedClient]:
    """Build the reader once. Later clicks reuse it."""
    texts, answers = load_split(ROOT / "data" / "train")
    client = CachedClient(OllamaClient(model_from_env()), ROOT / "cache")
    embed = minilm_embedder(ROOT / "cache" / "models")
    return NoticeReader.from_train(texts, answers, client, embed), client


def test_answers() -> list[AnswerFile]:
    return [
        AnswerFile.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(TEST.glob("*.json"))
    ]


st.set_page_config(page_title="Fund Notices", layout="wide")
st.title("Fund Notices")
st.caption(f"{SYNTHETIC_LINE}. Every document here is invented. Everything runs on this laptop.")

read_tab, results_tab = st.tabs(["Read a document", "Test set results"])

with results_tab:
    results = ROOT / "docs" / "results.md"
    if results.is_file():
        st.markdown(without_frontmatter(results.read_text(encoding="utf-8")))
    else:
        st.info("No results yet. Run: python -m fund_notices.evaluate")

with read_tab:
    if not (ROOT / "data" / "train").is_dir() or not TEST.is_dir():
        st.warning("No data yet. Run: python -m fund_notices.generate")
        st.stop()

    source = st.radio("Choose a PDF", ["From the test set", "Upload a PDF"], horizontal=True)
    truth: AnswerFile | None = None
    pdf: bytes | None = None
    if source == "From the test set":
        truth = st.selectbox("Test document", test_answers(), format_func=choice_label)
        if truth is not None:
            pdf = (TEST / f"{truth.doc_id}.pdf").read_bytes()
    else:
        upload = st.file_uploader("A PDF from your computer", type="pdf")
        pdf = None if upload is None else upload.getvalue()

    if pdf is None:
        st.info("Choose a test document or upload a PDF.")
        st.stop()

    key = hashlib.sha256(pdf).hexdigest()
    left, right = st.columns(2)

    with left:
        st.subheader("The PDF")
        st.pdf(pdf, height=700)
        with st.expander("The text the model reads"):
            st.code(pdf_text(pdf), language=None)

    with right:
        st.subheader("What the tool found")
        if st.button("Read it", type="primary"):
            try:
                reader, client = get_reader()
                hits_before = client.cache_hits
                start = time.perf_counter()
                with st.spinner("Reading. A new document takes about 20 seconds..."):
                    outcome = reader.read(pdf_text(pdf))
                seconds = time.perf_counter() - start
                st.session_state["last"] = (key, outcome, seconds, client.cache_hits > hits_before)
            except RuntimeError as exc:
                st.error(str(exc))
            except ConnectionError:
                st.error("Ollama is not running. Open the Ollama app and try again.")

        last = st.session_state.get("last")
        if last is None or last[0] != key:
            st.info("Press Read it.")
            st.stop()

        _, outcome, seconds, cached = last
        if outcome.needs_review:
            st.error("Send to a person")
            for reason in outcome.review_reasons:
                st.markdown(f"* {reason}")
        else:
            st.success("No problems found. The numbers add up.")

        prediction = outcome.prediction
        st.markdown(
            f"**Type:** `{prediction.doc_type}`, probability {prediction.confidence:.2f}  \n"
            f"**Second opinion, nearest train document by meaning:** `{outcome.second_opinion}`  \n"
            f"**Worked example shown to the model:** `{outcome.example_id}`"
        )
        if outcome.extraction.fields is None:
            st.warning(f"Extraction failed twice: {outcome.extraction.error}")
        else:
            truth_fields = None if truth is None else truth.fields
            st.dataframe(
                field_rows(outcome.extraction.fields, truth_fields),
                hide_index=True,
                width="stretch",
            )
        origin = "the reply came from the cache" if cached else "a new model call"
        st.caption(f"Read in {seconds:.1f} seconds, {origin}.")
