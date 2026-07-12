# ChainGuard — Ethereum address risk scoring

Paste an Ethereum address, get a calibrated risk score with the three behavioural patterns that drove it. A LightGBM model over on-chain activity features, served by FastAPI, shipped as one Docker image.

**Name:** ChainGuard · **Line:** "Score any Ethereum address for patterns seen in reported scam activity." · **Package:** `chainguard`

---

## 0. Rules for this build

- **Budget: 45 minutes.** Follow §10 in order. Train first, serve second, style third. Never the reverse.
- **Do not ask me questions.** Every decision is made below. Take the option written here.
- **Ethical framing is a hard constraint, not a nicety.** The words `fraudster`, `criminal`, `guilty`, `scammer`, `verdict`, `caught` must never appear in code, API fields, UI copy, commit messages or docs. This model finds *patterns*; it does not accuse people. A lint check enforces it (§8).
- Plain `.py` scripts. **No notebooks** — they don't deploy, don't diff, and don't run in CI.
- The trained model is **committed to the repo** as a file. The container must not train at build time.
- Write whole files in one pass. No `# TODO`, no placeholder metrics, no invented numbers in the README — every figure printed there comes from an actual run.
- Ship working over ship complete. A finished-looking single-address scorer beats a half-built batch pipeline.

---

## 1. Stack — chosen for deployment, not novelty

| Layer | Choice | Why this one |
|---|---|---|
| Language | Python 3.11 | Model, API and feature code stay in one language |
| Model | **LightGBM** + isotonic calibration | Beats a neural net on 9.8k tabular rows, trains in seconds, ~1 MB artifact |
| Explainability | **SHAP** `TreeExplainer` | Exact for trees, fast enough for per-request use |
| API | **FastAPI** + Uvicorn | Typed request/response, free OpenAPI docs at `/docs` |
| Store | A Parquet feature table loaded into memory at startup | **No database.** Nothing to provision, nothing to pay for |
| UI | **One `static/index.html`** — vanilla JS + CSS, Google Fonts | Zero build step. No npm, no bundler, no node in the image |
| Container | One `python:3.11-slim` image, port 7860 | One artifact, one port |
| Host | **Hugging Face Spaces, Docker SDK, free CPU tier** | Free, no card, `git push` deploys. Same image runs on Render or Fly |

**Deliberately rejected:** Gradio and Streamlit — fast to write, but the interface is theirs, not yours, and this project is judged partly on the interface. Node/React — a build step and a second runtime in the image, for a page with one input and one card. Any managed database — a 9,800-row table is a file.

---

## 2. Architecture

```
Browser  ──  GET /  ──▶  static/index.html            (no build, served by FastAPI)
             │
             └─ POST /api/score {"address": "0x..."}
                     ▼
                FastAPI :7860
                ├─ look up address in features.parquet   (in-memory DataFrame, indexed)
                ├─ model.predict_proba → isotonic calibrator → risk_score
                ├─ TreeExplainer(row) → top 3 signed contributions → plain-English facts
                └─ band = low | medium | high   (thresholds from §4.5, never guessed)

Offline, run once, committed:
  data/raw/transaction_dataset.csv ──▶ train.py ──▶ models/{model.txt, calibrator.joblib,
                                                            features.parquet, columns.json,
                                                            metrics.json, thresholds.json}
```

---

## 3. Data

**Dataset:** the public *Ethereum Fraud Detection* set (~9,841 addresses, 51 columns, binary `FLAG`, roughly 22% flagged). Kaggle original, mirrored on GitHub and HF Datasets. Save to `data/raw/transaction_dataset.csv`; `data/` is gitignored except `.gitkeep`.

**The column names in this file are inconsistent** — mixed case, embedded spaces, and a stray unnamed index column. First thing `train.py` does: drop `Unnamed: 0` and `Index`, then slugify every column to `snake_case`. Do not hand-type a raw column name anywhere else in the repo.

**Features to use — 12 behavioural columns.** No ERC20 token-name columns: they leak and don't generalise.

```
sent_tnx, received_tnx, unique_sent_to_addresses, unique_received_from_addresses,
avg_min_between_sent_tnx, avg_min_between_received_tnx,
time_diff_between_first_and_last_mins,
min_value_sent, max_value_sent, avg_val_sent,
avg_val_received, total_ether_balance
```

Plus two engineered ones, because the ratios are what actually separate the classes:

```
send_receive_ratio  = sent_tnx / (received_tnx + 1)
counterparty_reuse  = unique_sent_to_addresses / (sent_tnx + 1)
```

**Honesty rules — these belong in the README, not only in the code:**
- Deduplicate on `address` **before** splitting. Duplicate rows landing in both train and test are the single biggest source of fake accuracy on this dataset.
- This dataset carries **no timestamps**, so a temporal split is impossible. Say that plainly rather than implying the split is time-aware.
- Labels come from historical reports of scam activity: noisy, incomplete, and skewed toward addresses someone bothered to report. State this in the README and in the UI footer.

---

## 4. Model pipeline — `train.py`, one script, top to bottom

### 4.1 Split
Dedupe → stratified 80/20, `random_state=42`. Also run 5-fold stratified CV on the train half and report mean ± std. A single split on 9.8k rows moves a couple of points between seeds; report both or the number means little.

### 4.2 Baseline first
Fit `LogisticRegression(class_weight="balanced")` on standardised features and print its PR-AUC. **If LightGBM doesn't clearly beat it, something is wrong with the features** — that check happens before any tuning.

### 4.3 Model
```python
LGBMClassifier(
    n_estimators=400, learning_rate=0.05, num_leaves=31,
    min_child_samples=30, subsample=0.9, colsample_bytree=0.8,
    class_weight="balanced", random_state=42,
)
```
No hyperparameter search. It is not where the 45 minutes go.

### 4.4 Calibration
Wrap the fitted model in `CalibratedClassifierCV(method="isotonic", cv="prefit")`, fitted on a held-out 15% slice of train. **An uncalibrated GBM probability is not a risk score** — a 0.8 has to mean roughly 80%, or the bands in the UI are decoration. Print the Brier score before and after.

### 4.5 Metrics — print these and write them to `models/metrics.json`
`PR-AUC` (primary — the classes are imbalanced, so ROC-AUC flatters), `ROC-AUC`, `precision@100`, `recall at 90% precision`, `Brier score`, and the confusion matrix at the chosen threshold.

Derive thresholds from the precision-recall curve, not from round numbers: `high` = the score at which precision first reaches 0.90; `medium` = where recall first reaches 0.80. Write both to `models/thresholds.json` and load them at serve time. Nothing in the codebase may hardcode 0.3 / 0.7.

### 4.6 Explanations
Fit `shap.TreeExplainer` on the model and save it. At request time take the row's SHAP values, sort by absolute magnitude, take the top 3, and render each through a template table mapping feature → neutral fact:

| feature | a positive contribution reads as |
|---|---|
| `send_receive_ratio` | Sends far more often than it receives |
| `counterparty_reuse` | Sends to many addresses it never interacts with again |
| `avg_min_between_sent_tnx` | Very short gaps between outgoing transactions |
| `time_diff_between_first_and_last_mins` | Short total lifetime of activity |
| `total_ether_balance` | Balance near zero despite high throughput |

Every phrase is an observation. None names a person or an intent. Write the full 14-row table, both directions.

---

## 5. API — `app/main.py`

```
GET  /                → static/index.html
POST /api/score       → {"address": "0x..."}
GET  /api/model/info  → metrics.json + thresholds + trained_on date + n_rows
GET  /api/examples    → 3 real dataset addresses (1 flagged, 2 not), labels hidden
GET  /health          → {"status": "up"}
```

`POST /api/score` response — a Pydantic model, this exact shape:

```json
{
  "address": "0x00009277775ac7d0d59eaad8fee3d10ac6c805e8",
  "risk_score": 0.83,
  "risk_band": "high",
  "top_reasons": [
    {"fact": "Sends far more often than it receives", "weight": 0.31, "direction": "raises"},
    {"fact": "Very short gaps between outgoing transactions", "weight": 0.18, "direction": "raises"},
    {"fact": "Interacts with a small set of repeat counterparties", "weight": -0.07, "direction": "lowers"}
  ],
  "activity": {"sent": 704, "received": 12, "unique_counterparties": 689, "lifetime_days": 41},
  "disclaimer": "Risk scores describe patterns in publicly reported data. They are not an accusation and not financial advice."
}
```

Validation and errors:

| Cause | HTTP | `message` | `hint` |
|---|---|---|---|
| fails `^0x[a-fA-F0-9]{40}$` | 422 | That doesn't look like an Ethereum address. | An address is `0x` followed by 40 hex characters. |
| valid but not in table | 404 | This address isn't in the demo dataset. | Try one of the example addresses. |
| model files missing | 503 | The scoring model isn't loaded. | Run `make train`, then restart. |

Load the model, calibrator, explainer and Parquet table **once** in a FastAPI `lifespan` handler — never per request. A cold score must come back in under 50 ms.

`tests/test_api.py`: a valid address returns a score in [0,1] with exactly 3 reasons; garbage input returns 422; valid-but-unknown returns 404. Three tests, that's the suite.

---

## 6. Frontend — `static/index.html`, one file

A single centred **720px** column. No framework, no bundler, no `<form>` element — use a click handler.

**Content order:** wordmark + model-info chip · h1 · address input + button · three example chips · result card · permanent footer disclaimer.

**Behaviour**
- Enter in the input scores it. `/` focuses it from anywhere.
- Loading: a skeleton card where the result will be, never a spinner over the page.
- Addresses render in monospace, truncated as `0x0000…05e8`, with click-to-copy on the full value.
- Push `?address=…` with `history.replaceState` and read it on load, so a result is shareable.
- Reasons animate in with a 60 ms stagger, once. Nothing else animates.

---

## 7. Design system — forensic ledger, not crypto casino

Cold, light, precise, dense with real numbers. It should look like a compliance tool someone uses at work, not a token launch page.

```css
--bg:        #F6F8FA;   /* page */
--surface:   #FFFFFF;   /* cards */
--line:      #E3E8EE;   /* 1px borders — no shadows anywhere */
--ink:       #16202E;
--ink-soft:  #5B6B7F;
--ink-faint: #93A1B2;
--action:    #2952CC;   /* the only interactive colour: button, links, focus ring */
--low:       #2E7D5B;
--medium:    #B7791F;
--high:      #B3372E;
--r: 10px;  --ease: cubic-bezier(.2,.7,.3,1);
```

**The risk colours are load-bearing and appear nowhere else.** No green button, no red border on a text input. Band colour touches exactly two things: the gauge ring and the band label.

**Type — three faces, three jobs:**
- **Bricolage Grotesque** 700 — the `h1` and the big score number only.
- **Instrument Sans** 400/500 — body text, labels, buttons.
- **JetBrains Mono** 400/500 — every address, every number, the model-info chip. Hex is monospace or it's wrong.

Scale `12 / 14 / 16 / 20 / 30 / 64`px. Body `16px/1.6`.

**Signature element — the score ring.** A 160px circle drawn with `conic-gradient` in the band colour, the score as a `64px` Bricolage number centred inside, the band name beneath in `12px` mono caps in the band colour. It fills once on arrival, 0 → score over 400 ms with `--ease`. Below it, "Why this score" as three thin horizontal bars — width proportional to `|weight|`, band colour for `raises`, `--ink-faint` for `lowers` — each with its fact in `14px` alongside. That pairing of one number with its three drivers is the whole product; everything around it stays quiet.

Honour `prefers-reduced-motion: reduce`: ring renders filled, no sweep, no stagger.

**Quality floor:** responsive to 360px · visible focus rings on every control · `aria-live="polite"` on the result region · contrast ≥ 4.5:1 · no gradients except the ring · no emoji · no dark mode.

---

## 8. Language rules — enforced

Add `make lint-language`: grep the repo for `fraudster|criminal|guilty|scammer|verdict|caught|thief`, exit 1 on any hit outside this file. Wire it into `make check`.

Write like a report, not a headline: "Risk score 0.83, high band" — never "This address is a scam." The footer disclaimer is permanent, not dismissible, and comes from the API so it's written once. Buttons say what they do: "Score address". Errors state the fact and the fix and never apologise.

---

## 9. Commands — `Makefile`

```make
setup    : python -m venv .venv && pip install -r requirements.txt
train    : python train.py                  # writes models/, prints metrics
serve    : uvicorn app.main:app --reload --port 7860
test     : pytest -q
lint     : ruff check . && make lint-language
check    : lint test
docker   : docker build -t chainguard . && docker run -p 7860:7860 chainguard
```

`requirements.txt`, pinned: `fastapi`, `uvicorn[standard]`, `pandas`, `pyarrow`, `scikit-learn`, `lightgbm`, `shap`, `joblib`, `pydantic`, `pytest`, `httpx`, `ruff`.

---

## 10. Build order

**0–5 min · Scaffold**
- [ ] Tree: `app/`, `static/`, `models/`, `data/raw/`, `tests/`; `Makefile`, `requirements.txt`, `.gitignore`, `.dockerignore`
- [ ] Venv, install, CSV into `data/raw/`

**5–18 min · Model**
- [ ] `train.py`: load → drop index cols → slugify → dedupe → engineer the 2 ratios → split
- [ ] Logistic baseline printed, then LightGBM, then isotonic calibration
- [ ] Metrics and 5-fold CV printed; thresholds derived from the PR curve
- [ ] Save `model.txt`, `calibrator.joblib`, `features.parquet`, `columns.json`, `metrics.json`, `thresholds.json`
- [ ] **Verify:** PR-AUC beats the baseline and Brier improves after calibration. Do not proceed until both hold.

**18–28 min · API**
- [ ] `app/schemas.py`, `app/scoring.py` (load once, score, SHAP → facts), `app/main.py`
- [ ] Five routes, three error cases, static mount at `/`
- [ ] `tests/test_api.py` green
- [ ] **Verify:** `curl -X POST localhost:7860/api/score -d '{"address":"0x..."}'` returns the full payload

**28–40 min · UI**
- [ ] `static/index.html` — tokens and fonts first, then structure, then the ring
- [ ] Idle, loading, result, 404 and 422 states all styled
- [ ] Example chips wired to `/api/examples`; copy-on-click; URL sync; 360px check

**40–45 min · Ship**
- [ ] `Dockerfile`, build and run locally on 7860
- [ ] `README.md`: the real metrics table, the data-limitations section from §3, setup in four commands
- [ ] `make check` green, commit, push to a Space

---

## 11. Deploy — Hugging Face Spaces, free tier

`Dockerfile`:

```dockerfile
FROM python:3.11-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
USER user
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

`models/` **must be committed** — the image does not train. Total artifacts are a few MB. Put `data/raw/*.csv` in both `.gitignore` and `.dockerignore`.

`README.md` needs this YAML frontmatter as its first lines or the Space won't boot. The `emoji` field is HF metadata — the one place an emoji is allowed in this repo.

```yaml
---
title: ChainGuard
emoji: 🛡️
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---
```

Then: create a Space → Docker → Blank → `git remote add space https://huggingface.co/spaces/<user>/chainguard` → `git push space main`. It builds and serves itself. No secrets, no env vars, no card. The same image runs unchanged on Render or Fly if you later want a custom domain.

---

## 12. Definition of done

`git push space main` produces a live URL where pasting a dataset address returns a calibrated score, a band, and three plain-English drivers in under a second. The README's metrics match `models/metrics.json` exactly and name the dataset's limitations without hedging. `make check` is green. Nothing in the repo or the interface accuses anyone of anything.

## 13. Do not

Notebooks · a database · Gradio or Streamlit · npm anywhere · training inside the container · a deep learning model · hardcoded 0.3/0.7 thresholds · SMOTE (use `class_weight`) · accuracy as a headline metric · ERC20 token-name features · uncalibrated probabilities presented as a risk score · verdict language · gradients outside the ring · emoji in the UI · `print()` left in `app/`.

---

## 14. Optional, only if the build finished early

**Live address lookup.** Add `ETHERSCAN_API_KEY` as a Space secret and an `app/onchain.py` that pulls an address's `txlist`, derives the same 14 features from the raw transactions, and scores addresses outside the dataset. This is the highest-value addition available — it turns a demo over a fixed table into a tool that works on any address. But it is a second feature pipeline that must produce features identically to `train.py`, so factor the derivation into one shared function *before* you start, and keep the 404 path as the fallback when the key is absent.