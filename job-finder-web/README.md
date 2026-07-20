# Job Finder Web App

Application code for the local-first job search system in this repository.

For repository-level documentation, start at `../README.md` and `../docs/README.md`.

## What It Is

A FastAPI application with server-rendered templates for:

- candidate management
- document upload and parsing
- skills and preferences management
- platform account management
- job search and job analysis workflows

## Structure

```text
job-finder-web/
├── backend/
├── frontend/
├── tests/
├── requirements.txt
├── setup.sh
├── setup.bat
└── run.py
```

## Setup

### Linux or macOS

```bash
cd job-finder-web
chmod +x setup.sh
./setup.sh
```

### Windows

```cmd
cd job-finder-web
setup.bat
```

### Manual

```bash
cd job-finder-web
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m playwright install chromium
venv/bin/python run.py
```

## Configuration

The app reads environment variables from `.env` when present.

Important settings include:

- `ENCRYPTION_KEY`
- `HOST`
- `PORT`
- `DEBUG`
- `OLLAMA_URL`
- provider API keys

See `backend/config.py` for current defaults.

## Testing

```bash
cd job-finder-web
venv/bin/python -m pytest -q
```

## Notes

- Runtime behavior and current defaults should be verified from the code, especially `backend/config.py`, `backend/app.py`, and `run.py`.
- Older implementation summaries and phase documents live under `../history/`.
