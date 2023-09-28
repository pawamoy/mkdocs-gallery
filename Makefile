.PHONY: setup
setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

.PHONY: build
build:
	.venv/bin/python build.py

.PHONY: format
format:
	black -l 120 build.py
	ruff check --fix --select I build.py

.PHONY: serve
serve:
	cd site; python -m http.server
