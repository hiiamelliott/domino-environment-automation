# domino-environment-automation

Automate creation and maintenance of Domino Compute Environments from simple YAML templates. 

This script reads one or more environment templates, creates the corresponding environments in Domino (if they don't already exist), and updates them by creating new revisions when the template changes. 
It also supports optional restrictions and workspace tool (IDE) configuration.

## Templates

- Example template: `environment_templates/test_env/environment.yaml`. Treat this as a reference for how to configure an environment.
- You can create additional environments by adding more subdirectories under `environment_templates/`, each with its own `environment.yaml`.
- Alternatively, you could modify `main.py` to use one directory, and infer the name of the environment from the YAML filename.

## Requirements

- Environment variables:
  - `DOMINO_PROJECT_OWNER` and `DOMINO_PROJECT_NAME` (Required): These are required for configuring the Domino client from `python-domino`. 
  - `TARGET_DIRECTORY` (optional): Base directory that contains `environment_templates/`. If unset, the script will look for `environment_templates/` in the current directory and one directory up from the current working directory.
  

If run outside Domino:
  - `DOMINO_URL` (Required if run outside a Domino instance): Base URL to your Domino instance (e.g., `https://your-domino.example.com/`).
  - One of (Required):
    - `DOMINO_API_KEY`: Your Domino API key to authenticate with Domino's REST API
    - or
    - `DOMINO_AUTH_TOKEN`: A Service Account token for the same purpose.
  
## Run

```bash
python scripts/main.py
```

Logs are emitted at `INFO` level by default; set `LOG_LEVEL` to adjust (e.g., `DEBUG`, `WARNING`).
