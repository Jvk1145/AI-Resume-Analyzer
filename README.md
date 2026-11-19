# AI Resume Analyzer

A Streamlit app that scores a resume against ATS best practices, matches it to a job description, and uses
free-tier LLMs (Groq, then Gemini) for parsing, honest bullet rewrites, cover letters and interview prep.

The **ATS score and JD match are deterministic**: they are computed locally with fixed, explainable rules,
so the same resume always gets the same score, and each point comes with a reason.

## Features

- **Explainable ATS score (0-100)**: 8 rule-based categories, each with points and plain-language reasons.
- **JD matching**: about 300 tech and soft skills with synonyms ("js" → JavaScript, "postgres" →
  PostgreSQL). Each skill is marked required or nice-to-have, the whole resume is searched, and the app shows
  where each skill was found (Skills / Experience / Projects).
- **Honest bullet rewrites**: the AI suggests improvements but may not invent facts. Any number not in the
  original bullet is automatically replaced with a placeholder such as `[X%]` or `[number]`, and suggestions
  for bullets that aren't in your resume are discarded.
- **Accept/edit suggestions**: edit each rewrite, tick *Accept*, and download a single-column DOCX with the
  accepted rewrites applied.
- **Cover letter generator**: 250-300 words, editable, downloadable as DOCX.
- **Interview prep**: 8 likely questions, each with a tip that points to your own experience.
- **Privacy**: email, phone numbers and street addresses are redacted before any text is sent to an AI
  provider. They are added back only in the DOCX files generated on your machine.
- **History**: each analysis (date, file name, ATS score, JD match %, top missing skills) is saved to a local
  SQLite file and shown as a chart and table.

## Architecture

```
            upload (PDF / DOCX)
                    │
          parsers/  ▼  (temp file, always deleted)
   ┌──────────────────────────────────────┐
   │ pdf_parser / docx_parser → raw text  │
   │ layout.py → tables, columns, images, │
   │             header text, page count  │
   └──────────────────────────────────────┘
            │                         │
   deterministic (local)          AI (remote, redacted text only)
            │                         │
   matching/jd_matcher.py      privacy/redact.py
     + skills_db.py                   │
            │                  ai/llm_service.py ── Groq (key 1, key 2)
   scoring/ats_score.py               │         └─ Gemini (key 1, key 2)
            │                  ai/json_helper.py  (repair JSON)
            │                  ai/schemas.py      (pydantic validation,
            │                                      invalid → next provider)
            │                  ai/honesty.py      (no invented numbers)
            ▼                         ▼
                 app.py (Streamlit tabs)
   Analysis │ JD match │ Suggestions │ Cover letter │ Interview prep │ History
                    │                                     │
     exporters/docx_exporter.py                 storage/history.py
     (contact info restored locally)            (data/history.db)
```

AI results are cached with `st.cache_data`, keyed by a SHA-256 hash of the resume text, the JD text and
the prompt version.

## How scoring works

| Category | Points | Rule |
|---|---|---|
| Contact info | 10 | Email 4, phone 3, LinkedIn or GitHub URL 3 |
| Standard sections | 15 | Summary, Skills, Experience-or-Projects, Education headings (3.75 each) |
| JD keyword coverage | 30 | Weighted match % from the JD matcher (only when a JD is given) |
| Action verbs | 10 | Share of bullets starting with one of ~110 strong verbs; full marks at 80% |
| Quantified achievements | 15 | Share of bullets with a number, %, ₹, $, € or £; full marks at 50% |
| Bullet quality | 10 | Share of bullets that are 8-30 words with no "I/me/my"; full marks at 80% |
| Length | 5 | Pages (1 page under 3 years of experience, at most 2 otherwise) and word count |
| Layout | 5 | Minus points for tables (-2), multiple columns (-2), images (-1), header/footer text (-1) |

- **No job description?** The 30 keyword points are shared across the other categories in proportion to
  their weights, so the maximum is still 100.
- **JD match %** = matched weight ÷ total weight, where required skills weigh 2 and nice-to-have skills
  weigh 1. A skill is *required* when its sentence contains words like *required / must / mandatory*, or
  when it sits under a heading such as "Requirements:". Words like *preferred / nice to have / plus* mark
  it nice-to-have.
- **Limits:** these are heuristics, not a copy of any specific commercial ATS. Page count is exact for PDFs
  and estimated from word count for DOCX files. Multi-column detection on PDFs looks for a vertical gap in
  the text, and unusual layouts can fool it.

## How to run

```bash
git clone https://github.com/Jvk1145/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer
pip install -r requirements.txt
cp .env.example .env      # then paste your keys into .env
streamlit run app.py
```

`.env` keys (the `_2` keys are optional backups, tried if the first key fails):

```
GROQ_API_KEY=
GROQ_API_KEY_2=
GEMINI_API_KEY=
GEMINI_API_KEY_2=
# Optional model overrides if a provider retires a default:
# GROQ_MODEL=openai/gpt-oss-120b
# GEMINI_MODEL=gemini-3.8-flash
```

Both providers have free tiers. If every key fails (for example, all rate-limited), the app shows a short
reason for each provider.

On Streamlit Community Cloud, put the same keys in the app's **Secrets** settings instead of `.env`. Note that
`data/history.db` lives on the server, so in a shared deployment every visitor sees the same history, and the
file is lost whenever the app restarts.

## How to run tests

```bash
python -m pytest -q
```

The tests use small inline fixture resumes and make **no API calls**. They cover every ATS category, JD
matching (synonyms, required vs nice-to-have, locations), JSON repair, redaction, schema validation, the
provider fallback chain, the honesty guards, the DOCX export, history and layout detection.

## Project layout

```
app.py                  Streamlit entry point (inputs, progress, tabs)
ui/                     pipeline + caching, page views, reusable components
.streamlit/config.toml  light/dark theme
ai/                     providers, prompts, schemas, fallback chain, JSON repair, honesty guards
matching/               skills database and JD matcher
scoring/ats_score.py    deterministic ATS engine
parsers/                text, sections, contact details, layout
privacy/redact.py       PII redaction
exporters/              DOCX resume and cover letter
storage/history.py      SQLite history
tests/                  pytest suite
```
