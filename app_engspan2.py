# app.py — LLM Readability (textstat) Web App (Processed vs Unprocessed)
# Run locally:
#   pip install -U streamlit textstat pandas openpyxl xlsxwriter
#   streamlit run app.py
import io
import re
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

try:
    import textstat  # type: ignore
except Exception:
    st.error("textstat is not installed. In a terminal run: pip install -U textstat")
    st.stop()

# ----------------- Helpers -----------------
def clean_text(s: str, strip_markdown: bool) -> str:
    s = str(s)
    if strip_markdown:
        s = re.sub(r"[*_]{2,}", "", s)  # remove **, __
        s = re.sub(r"[*_]", "", s)      # remove single * or _
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n\s+", "\n", s)
    return s.strip()

def normalize_bullets(text: str) -> str:
    """Ensure bullet lines (starting with *, -, •) end with terminal punctuation so they count as sentences."""
    lines = text.splitlines()
    out = []
    for ln in lines:
        s = ln.rstrip()
        if s.lstrip().startswith(("*", "-", "•")) and not re.search(r"[.!?]\s*$", s):
            s = s + "."
        out.append(s)
    return "\n".join(out)

READABILITY_FUNCS = {
    "smog_index": textstat.smog_index,
    "flesch_reading_ease": textstat.flesch_reading_ease,
    "flesch_kincaid_grade": textstat.flesch_kincaid_grade,
    "gunning_fog": textstat.gunning_fog,
    "coleman_liau_index": textstat.coleman_liau_index,
    "automated_readability_index": textstat.automated_readability_index,
    "dale_chall_readability_score": textstat.dale_chall_readability_score,
    "linsear_write_formula": textstat.linsear_write_formula,
    "spache_readability": textstat.spache_readability,

    # 🇪🇸 Spanish-specific formulas
    "fernandez_huerta": textstat.fernandez_huerta,
    "szigriszt_pazos": textstat.szigriszt_pazos,
    "gutierrez_polini": textstat.gutierrez_polini,
    "crawford": textstat.crawford,
}

COUNT_FUNCS = {
    "sentences": textstat.sentence_count,
    "words": lambda t: textstat.lexicon_count(t, removepunct=True),
    "syllables": textstat.syllable_count,
    "polysyllables": textstat.polysyllabcount,
    "monosyllables": textstat.monosyllabcount,
    "characters_no_spaces": lambda t: textstat.char_count(t, ignore_spaces=True),
    "characters_with_spaces": lambda t: textstat.char_count(t, ignore_spaces=False),
    "avg_syllables_per_word": textstat.avg_syllables_per_word,
}

METRIC_ORDER = [
    "smog_index",
    "flesch_reading_ease",
    "flesch_kincaid_grade",
    "gunning_fog",
    "coleman_liau_index",
    "automated_readability_index",
    "dale_chall_readability_score",
    # 🇪🇸 Spanish-specific
    "fernandez_huerta",
    "szigriszt_pazos",
    "gutierrez_polini",
    "crawford",
    "linsear_write_formula",
    "spache_readability",
    "sentences",
    "words",
    "syllables",
    "polysyllables",
    "monosyllables",
    "characters_no_spaces",
    "characters_with_spaces",
    "avg_syllables_per_word",
]

def score_text(text: str, strip_markdown: bool) -> Dict[str, Any]:
    base = clean_text(text, strip_markdown)
    processed = normalize_bullets(base)

    out: Dict[str, Any] = {}
    # Unprocessed
    for k, fn in READABILITY_FUNCS.items():
        try:
            out[f"{k}_unprocessed"] = round(float(fn(base)), 3)
        except Exception:
            out[f"{k}_unprocessed"] = None
    for k, fn in COUNT_FUNCS.items():
        try:
            v = fn(base)
            out[f"{k}_unprocessed"] = round(float(v), 3) if isinstance(v, float) else v
        except Exception:
            out[f"{k}_unprocessed"] = None

    # Processed (bullet-normalized)
    for k, fn in READABILITY_FUNCS.items():
        try:
            out[f"{k}_processed"] = round(float(fn(processed)), 3)
        except Exception:
            out[f"{k}_processed"] = None
    for k, fn in COUNT_FUNCS.items():
        try:
            v = fn(processed)
            out[f"{k}_processed"] = round(float(v), 3) if isinstance(v, float) else v
        except Exception:
            out[f"{k}_processed"] = None

    return out

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as ew:
        df.to_excel(ew, index=False, sheet_name="Results")
    buffer.seek(0)
    return buffer.read()

# ----------------- UI -----------------
st.set_page_config(page_title="LLM Readability (textstat) — raw vs processed", layout="wide")
st.title("LLM Readability (textstat) — raw vs processed")

with st.sidebar:
    st.header("Options")
    
    # --- UPDATED SECTION: Language Selector ---
    st.subheader("Language Settings")
    language = st.selectbox(
        "Select Text Language",
        options=["en", "es"],
        format_func=lambda x: "🇪🇸 Spanish" if x == "es" else "🇺🇸 English",
        index=1, # Defaults to Spanish for your use case
        help="Sets the syllable counter. Selecting 'Spanish' ensures Fernandez-Huerta and Szigriszt-Pazos are calculated correctly."
    )
    
    # Apply the language setting globally to textstat
    textstat.set_lang(language)
    st.caption(f"Engine set to: **{language}**")
    st.divider()
    # -------------------------------------------

    strip_md = st.checkbox("Strip Markdown (**bold**/_italics_)", value=True)
    st.caption("App computes BOTH: *_unprocessed* (raw) and *_processed* (bullets normalized with trailing periods).")

paste_tab, file_tab = st.tabs(["📋 Paste text", "📁 Upload file"])

# --------- Paste Tab ---------
with paste_tab:
    st.subheader("Paste text")
    paste_mode = st.radio(
        "Paste handling",
        options=["Each line = one cell", "Entire block = one cell"],
        index=0,
        horizontal=True,
        key="paste_mode_choice",
    )

    text_block = st.text_area(
        "Paste here",
        height=300,
        placeholder=(
            "If 'Each line = one cell', paste one cell per line.\n"
            "If 'Entire block = one cell', paste the whole output exactly as-is."
        ),
    )
    if st.button("Compute metrics for pasted text", type="primary"):
        if paste_mode == "Entire block = one cell":
            rows = [text_block] if text_block.strip() else []
        else:
            rows = [r for r in text_block.splitlines() if r.strip()]

        if not rows:
            st.warning("No non-empty text detected.")
        else:
            out_rows: List[Dict[str, Any]] = []
            for i, cell in enumerate(rows, start=1):
                metrics = score_text(cell, strip_md)
                out_rows.append({"row": i, **metrics})
            out_df = pd.DataFrame(out_rows)
            # Column order: unprocessed then processed
            desired = (["row"] +
                       [f"{m}_unprocessed" for m in METRIC_ORDER] +
                       [f"{m}_processed" for m in METRIC_ORDER])
            for col in desired:
                if col not in out_df.columns:
                    out_df[col] = None
            out_df = out_df[desired]

            st.success(f"Scored {len(out_df)} row(s)")
            st.dataframe(out_df, use_container_width=True)

            csv_bytes = out_df.to_csv(index=False).encode("utf-8")
            xlsx_bytes = to_excel_bytes(out_df)
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="readability_paste.csv", mime="text/csv")
            with col2:
                st.download_button("⬇️ Download Excel", data=xlsx_bytes, file_name="readability_paste.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --------- File Tab ---------
with file_tab:
    st.subheader("Upload Excel/CSV and pick columns")
    up = st.file_uploader("Choose an Excel (.xlsx/.xls) or CSV file", type=["xlsx", "xls", "csv"])
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                df = pd.read_csv(up)
            else:
                xls = pd.ExcelFile(up)
                df = pd.read_excel(up, sheet_name=xls.sheet_names[0])
        except Exception as e:
            st.error(f"Failed to read file: {e}")
            st.stop()

        st.write("Preview:")
        st.dataframe(df.head(20), use_container_width=True)

        text_candidates = [c for c in df.columns if df[c].dtype == object]
        sel_cols = st.multiselect("Select columns to score", options=text_candidates, default=text_candidates[:1])

        if st.button("Compute metrics for selected columns", type="primary"):
            if not sel_cols:
                st.warning("Pick at least one column.")
            else:
                out_rows = []
                for c in sel_cols:
                    series = df[c].fillna("").astype(str)
                    for idx, txt in series.items():
                        if txt.strip():
                            metrics = score_text(txt, strip_md)
                            out_rows.append({"row_index": int(idx) + 1, "column": c, **metrics})

                if not out_rows:
                    st.warning("No non-empty cells in selected columns.")
                else:
                    out_df = pd.DataFrame(out_rows)
                    desired = (["row_index", "column"] +
                               [f"{m}_unprocessed" for m in METRIC_ORDER] +
                               [f"{m}_processed" for m in METRIC_ORDER])
                    for col in desired:
                        if col not in out_df.columns:
                            out_df[col] = None
                    out_df = out_df[desired]

                    st.success(f"Scored {len(out_df)} cells across {len(sel_cols)} column(s)")
                    st.dataframe(out_df, use_container_width=True)

                    csv_bytes = out_df.to_csv(index=False).encode("utf-8")
                    xlsx_bytes = to_excel_bytes(out_df)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="readability_file.csv", mime="text/csv")
                    with col2:
                        st.download_button("⬇️ Download Excel", data=xlsx_bytes, file_name="readability_file.xlsx",
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")