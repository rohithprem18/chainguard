setup    : ; python -m venv .venv && .venv/bin/pip install -r requirements.txt
train    : ; python train.py                  # writes models/, prints metrics
serve    : ; uvicorn app.main:app --reload --port 7860
test     : ; pytest -q
lint     : ; ruff check . && make lint-language
lint-language : ; ! grep -rniE "fraudster|criminal|guilty|scammer|verdict|caught|thief" --include="*.py" --include="*.html" --include="*.md" --include="*.json" --exclude-dir=".venv" --exclude-dir="node_modules" --exclude="claude.md" --exclude="Makefile" .
check    : lint test
docker   : ; docker build -t chainguard . && docker run -p 7860:7860 chainguard
