# Gallery of MkDocs themes

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python prepare.py
bash build.sh  # will take a long time the first time to install deps
bash serve.sh  # go to localhost:8000
```

```bash
bash build.sh -D  # or --no-deps, to avoid running pip installs
bash build.sh -T  # or --no-themes, to avoid rebuilding themes
bash build.sh -S  # or --no-shots, to avoid taking screenshots
```
