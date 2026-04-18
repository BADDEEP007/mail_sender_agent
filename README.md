# Pipeline Explained — Automated Outreach System

A complete walkthrough of every module, every function, and how they connect.

---

## Big Picture — How It All Flows

```
You run main.py
      │
      ▼
pipeline.py  ←── the brain, calls everything else
      │
      ├─── resume_store.py  →  reads your PDFs, builds FAISS index, returns relevant chunks
      │
      ├─── chains.py        →  sends chunks + contact info to Groq LLM, gets email back
      │
      ├─── sender.py        →  takes the email, connects to Gmail SMTP, delivers it
      │
      └─── output_writer.py →  saves everything to JSON + CSV in output/
```

Supporting files that everything depends on:
- `config.py` — all settings and env vars in one place
- `logger.py` — writes logs to console and a file in `logs/`

---

## Module 1: `config.py`
**Role: Central settings store. Every other module imports from here.**

```python
GROQ_API_KEY    = os.getenv("groq_key")
EMAIL_USER      = os.getenv("personal_mail")
EMAIL_PASSWORD  = os.getenv("email_password")
```
Reads credentials from your `.env` file using `python-dotenv`. Nothing is hardcoded.

```python
LLM_MODEL        = "llama-3.1-8b-instant"
LLM_TEMPERATURE  = 0.7
```
The Groq model to use. `llama-3.1-8b-instant` is fast and free. Temperature 0.7 gives
creative but consistent output — lower = more robotic, higher = more random.

```python
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50
RETRIEVER_K   = 3
```
Controls how your resume is split and how many chunks are retrieved per query.
- `CHUNK_SIZE=500` — each piece of resume text is ~500 characters
- `CHUNK_OVERLAP=50` — chunks share 50 chars with their neighbor so context isn't cut mid-sentence
- `RETRIEVER_K=3` — fetch the 3 most relevant resume sections per role query

```python
EMAIL_RATE_LIMIT = 2   # seconds between sends
EMAIL_MAX_RETRY  = 3
```
Prevents Gmail from flagging you as spam (rate limit) and retries on network failures (retry).

---

## Module 2: `logger.py`
**Role: Write timestamped logs to both the terminal and a file.**

```python
log_file = os.path.join(LOGS_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
```
Every run creates a new log file named with the current timestamp, e.g. `run_20260417_210000.log`.
This means you never overwrite old logs — you can always go back and see what happened.

```python
logger = logging.getLogger("outreach")
```
Every module imports this `logger` object and calls `logger.info(...)`, `logger.error(...)` etc.
One logger, consistent format everywhere.

---

## Module 3: `resume_store.py`
**Role: Turn your PDF resumes into a searchable vector database.**

This is the RAG (Retrieval-Augmented Generation) layer. Instead of dumping your entire
resume into every prompt (expensive, hits token limits), it finds only the sections
most relevant to the role you're applying for.

### `_get_embeddings()`
```python
return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```
Creates the embedding model. `all-MiniLM-L6-v2` runs locally on your machine — no API
call, no cost. It converts text into vectors (lists of numbers) that capture semantic meaning.
"Backend engineer" and "server-side developer" will have similar vectors even though the
words are different.

### `load_resumes()`
```python
loader = PyPDFLoader(path)
docs.extend(loader.load())
```
Scans `data/resumes/` for every `.pdf` file and loads them using LangChain's `PyPDFLoader`.
Each page becomes a `Document` object with the text content and metadata (filename, page number).
Supports multiple resumes — if you have a backend resume and an AI resume, both get loaded.

### `build_vector_store(force_rebuild=False)`
The core indexing function. Does this in order:

1. Checks if a FAISS index already exists in `data/faiss_index/`
   - If yes and `force_rebuild=False` → loads it from disk (fast, skips re-embedding)
   - If no or `force_rebuild=True` → builds from scratch

2. Calls `load_resumes()` to get all PDF pages

3. Splits them with `RecursiveCharacterTextSplitter`:
   ```python
   splitter = RecursiveCharacterTextSplitter(
       chunk_size=500,
       chunk_overlap=50,
       separators=["\n\n", "\n", ".", " "]
   )
   ```
   Tries to split on paragraph breaks first, then newlines, then sentences, then spaces.
   This keeps meaningful units together rather than cutting mid-sentence.

4. Embeds all chunks using `_get_embeddings()` and stores them in FAISS

5. Saves the index to disk so next run is instant

### `get_retriever(force_rebuild=False)`
```python
return store.as_retriever(search_kwargs={"k": RETRIEVER_K})
```
Wraps the FAISS store as a LangChain retriever. When you call `.invoke(query)` on it,
it does a cosine similarity search and returns the top-K most relevant chunks.

### `retrieve_context(role, company, retriever)`
```python
query = f"{role} at {company} — relevant skills, experience, and projects"
docs = retriever.invoke(query)
context = "\n\n".join(d.page_content for d in docs)
```
Builds a natural language query from the role and company, runs it against FAISS,
and joins the top 3 matching resume chunks into a single string.
This string becomes the `resume_context` variable injected into the email prompt.

---

## Module 4: `chains.py`
**Role: Build LangChain chains that call the Groq LLM with structured prompts.**

### `_load_prompt(filename)`
```python
path = os.path.join(PROMPTS_DIR, filename)
with open(path, "r") as f:
    return f.read()
```
Reads a `.txt` file from `prompts/`. This means you can change the email style, tone,
or constraints by editing a text file — no code changes needed.

### `_get_llm()`
```python
return ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.7,
    groq_api_key=GROQ_API_KEY
)
```
Creates a Groq chat client. Every chain call goes through this. Groq runs LLaMA 3.1
on custom hardware (LPUs) — it's significantly faster than OpenAI for the same model size.

### `build_cold_email_chain()`
Loads `prompts/cold_email.txt` and creates an `LLMChain` with these input variables:
- `name` — recipient's name
- `role` — job role being applied for
- `company` — target company
- `resume_context` — the relevant resume chunks from FAISS

The prompt instructs the LLM to write under 150 words, no buzzwords, never start with "I",
focus on value alignment.

### `build_subject_chain()`
Loads `prompts/subject_line.txt`. Takes `name`, `role`, `company`.
Returns 3 subject line options, each under 60 characters.

### `build_referral_chain()`
Loads `prompts/referral.txt`. Takes `name`, `role`, `company`, `relationship`.
The `relationship` field (`stranger` / `alumni` / `mutual`) changes the tone:
- `stranger` → polite, professional, lead with value
- `alumni` → warm, mention shared institution
- `mutual` → reference the mutual connection

### `generate_cold_email(name, role, company, resume_context)`
Calls `build_cold_email_chain().invoke(...)` and returns the cleaned body text.

### `generate_subject_lines(name, role, company)`
Calls `build_subject_chain().invoke(...)`, splits the response by newlines,
returns a list of up to 3 subject strings.

### `generate_referral(name, role, company, relationship)`
Validates `relationship` is one of the 3 allowed values, then calls the referral chain.
Raises `ValueError` immediately if an invalid value is passed — fail fast, don't waste an API call.

---

## Module 5: `sender.py`
**Role: Deliver emails via Gmail SMTP with retry and rate limiting.**

### `_build_message(to, subject, body, resume_path)`
Constructs a `MIMEMultipart` email object:
- Sets From, To, Subject headers
- Attaches the plain text body
- If `resume_path` is provided and the file exists, reads the PDF as binary,
  base64-encodes it, and attaches it as `application/pdf`
- If the file doesn't exist, logs a warning and skips the attachment (doesn't crash)

### `send_email(to, subject, body, resume_path=None)`
The main send function. Two paths:

**Dry run mode** (`DRY_RUN=true` in `.env`):
```python
logger.info(f"[DRY RUN] Would send to: {to} | Subject: {subject}")
return True
```
Logs what would happen, returns True, sends nothing. Safe for testing.

**Live mode:**
```python
for attempt in range(1, EMAIL_MAX_RETRY + 1):
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, to, msg.as_string())
        return True
    except Exception as e:
        time.sleep(2 ** attempt)  # 2s, 4s, 8s
```
Opens a fresh SMTP connection per email (avoids timeout issues on long batches).
`starttls()` upgrades the connection to encrypted. On failure, waits 2^attempt seconds
before retrying — exponential backoff prevents hammering a temporarily unavailable server.

### `send_batch(records)`
Loops through a list of `{to, subject, body, resume_path}` dicts, calls `send_email()`
for each, and sleeps `EMAIL_RATE_LIMIT` seconds between sends.
Returns a summary: `{sent: int, failed: int, results: list}`.

---

## Module 6: `output_writer.py`
**Role: Persist every generated email to disk.**

### `save_results(records, run_id=None)`
Takes the list of result dicts from the pipeline and writes two files:

```
output/run_20260417_210000.json   ← full structured data, easy to parse
output/run_20260417_210000.csv    ← spreadsheet-friendly, one row per email
```

The JSON preserves nested fields like `subject_alternatives` (list).
The CSV flattens everything — good for reviewing in Excel or importing into a CRM.

If `run_id` is not provided, it auto-generates one from the current timestamp.
This means every run produces a new file — you never lose previous output.

---

## Module 7: `pipeline.py`
**Role: The orchestrator. Calls all other modules in the right order.**

### `run_single(name, email, company, role, resume_path, relationship, send, retriever)`
The core function. Runs the full pipeline for one contact:

```
Step 1: retrieve_context(role, company, retriever)
        → queries FAISS, returns 3 resume chunks as a string

Step 2: generate_cold_email(name, role, company, context)
        → sends to Groq LLM via cold_email chain, returns body text

Step 3: generate_subject_lines(name, role, company)
        → sends to Groq LLM via subject chain, returns [sub1, sub2, sub3]
        → picks subjects[0] as the primary subject

Step 4: generate_referral(name, role, company, relationship)  [optional]
        → only runs if relationship is provided
        → sends to Groq LLM via referral chain

Step 5: send_email(to, subject, body, resume_path)  [optional]
        → only runs if send=True
        → returns True/False

Returns a result dict with all of the above + timestamp + sent status
```

The `retriever` parameter is passed in from the caller so batch runs don't rebuild
the FAISS index for every single contact — it's built once and reused.

### `run_batch_from_csv(csv_path, resume_path, send, force_rebuild)`
Reads a CSV file where each row is one contact. Required columns: `name, email, company, role`.
Optional columns: `resume_path` (per-row override), `relationship`.

Builds the retriever once, then loops through every row calling `run_single()`.
Wraps each call in a `try/except` — if one contact fails (bad email, LLM error),
it logs the error and continues to the next. The batch never stops for one failure.

At the end, calls `save_results()` to write everything to `output/`.

### `run_batch_from_list(contacts, resume_path, send, force_rebuild)`
Same as `run_batch_from_csv` but accepts a Python list of dicts instead of a file path.
Useful when calling the pipeline programmatically from another script.

---

## Module 8: `main.py`
**Role: CLI entry point. Parses arguments and routes to the right pipeline function.**

### `parse_args()`
Defines all CLI flags:
- `--name`, `--email`, `--company`, `--role` → single contact mode
- `--csv` → batch mode
- `--resume` → PDF to attach (applies to all contacts in batch, or overridden per-row in CSV)
- `--relationship` → triggers referral generation (single mode only)
- `--no-send` → generate emails but don't send them
- `--rebuild-index` → force FAISS to re-embed resumes from scratch

### `main()`
Decision logic:
```
if --csv provided       → run_batch_from_csv(...)
elif all 4 single args  → run_single(...)
else                    → print usage, exit
```

In single mode, prints the generated email and referral to the terminal so you can
review it before it's sent.

---

## Full Data Flow — One Contact

```
Input: name="Nishant", email="nishant@softude.com", company="Softude", role="CTO"
                                    │
                                    ▼
                         resume_store.retrieve_context()
                         query: "CTO at Softude — relevant skills..."
                         FAISS similarity search → top 3 resume chunks
                                    │
                         context = "14 months backend lead...AWS Lambda...5000 users..."
                                    │
                                    ▼
                         chains.generate_cold_email()
                         Groq API call with: name + role + company + context
                         LLaMA 3.1 generates 120-word personalized email body
                                    │
                                    ▼
                         chains.generate_subject_lines()
                         Groq API call → 3 subject options
                         picks first: "Backend Lead → Softude | Pradeep Argal"
                                    │
                                    ▼
                         sender.send_email()
                         Gmail SMTP → starttls → login → sendmail
                         attaches Backend_Resume.pdf
                                    │
                                    ▼
                         output_writer.save_results()
                         writes output/run_20260417_210000.json
                                    │
                                    ▼
                         Result: { sent: true, body: "...", subject: "..." }
```

---

## Prompts Directory

The 3 files in `prompts/` are the only thing controlling what the LLM writes.
Edit them freely — no code changes needed.

| File | Controls | Key variables |
|---|---|---|
| `cold_email.txt` | Email body tone, length, structure | `{name}` `{role}` `{company}` `{resume_context}` |
| `subject_line.txt` | Subject line format and style | `{name}` `{role}` `{company}` |
| `referral.txt` | Referral tone per relationship type | `{name}` `{role}` `{company}` `{relationship}` |

---

## Environment Variables (`.env`)

| Variable | Used In | Purpose |
|---|---|---|
| `groq_key` | `config.py` → `chains.py` | Groq API authentication |
| `personal_mail` | `config.py` → `sender.py` | Gmail sender address |
| `email_password` | `config.py` → `sender.py` | Gmail App Password |
| `SMTP_SERVER` | `config.py` → `sender.py` | Default: `smtp.gmail.com` |
| `SMTP_PORT` | `config.py` → `sender.py` | Default: `587` |
| `DRY_RUN` | `config.py` → `sender.py` | `true` = generate only, never send |

---

## Dependency Map

```
main.py
  └── pipeline.py
        ├── resume_store.py
        │     ├── config.py
        │     └── logger.py
        ├── chains.py
        │     ├── config.py
        │     └── logger.py
        ├── sender.py
        │     ├── config.py
        │     └── logger.py
        └── output_writer.py
              ├── config.py
              └── logger.py
```

`config.py` and `logger.py` are imported by every module.
No module imports another module except through `pipeline.py` — clean separation.
