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
  - (Required) `DOMINO_URL`: Base URL to your Domino instance (e.g., `https://your-domino.example.com/`).
  - (Required) `DOMINO_API_KEY`: Your Domino API key.
  - `TARGET_DIRECTORY` (optional): Base directory that contains `environment_templates/`. If unset, the script will look for templates one directory up from the current working directory.

## Run

```bash
python scripts/main.py
```

Logs are emitted at `INFO` level by default; set `LOG_LEVEL` to adjust (e.g., `DEBUG`, `WARNING`).
