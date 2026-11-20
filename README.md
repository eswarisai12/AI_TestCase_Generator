# AI Test Case Generator

A Streamlit application that turns plain-language software requirements into
editable manual test cases using a local Ollama model. Generated cases include
positive, negative, and edge scenarios where applicable, plus steps, test data,
expected results, priority, and any assumptions.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running locally
- A model pulled into Ollama (the default is `llama3.2`)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull llama3.2
streamlit run app.py
```

In the sidebar, select a model that is available in your Ollama installation.
Set `OLLAMA_MODEL` or `OLLAMA_BASE_URL` in the environment to change the defaults.
Ollama's default URL is `http://localhost:11434`.

The app validates the model's JSON response before displaying it. Users can edit
cases in the table, delete selected cases, save results to SQLite, reload prior
results, and export the displayed cases as CSV. The SQLite database is created
at `data/test_cases.db`.

AI-generated test cases should be reviewed by a human before being used for
actual software testing.

## Run focused validation tests

```powershell
python -m unittest test_generator
```