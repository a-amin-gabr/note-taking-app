# Serverless App — Local development

This folder contains the Flask application that runs in AWS Lambda (via `apig_wsgi`) and is used by the serverless deployment.

Quick local dev steps

1. Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
```

2. Install dependencies:

```powershell
pip install -r serverless/app/requirements.txt
```

3. Run the app locally using the in-memory mock DB (recommended for development):

```powershell
$env:FLASK_APP='serverless/app/app.py'
$env:FLASK_ENV='development'
$env:USE_FAKE_DDB='1'
python -m flask run --host=127.0.0.1 --port=5000
```

Notes on environment variables

- `USE_FAKE_DDB` (default for local dev): when `1` the app will use an in-memory mock store. In production, set to `0`.
- `APP_DOMAIN`: when set, share links will be generated using this domain (recommended in production).
- `S3_BUCKET` / `S3_REGION`: configure S3 if you want to test attachment uploads to S3 locally (requires valid AWS credentials).
- `SECRET_KEY`: Flask session secret; must be set for production deployments.

Testing

- Guest login: open `/auth/guest` to create a temporary session.
- Create a note, then click Edit / Share / Delete to verify functionality.
- Attach a small image (<2 MB) using the Attach button and confirm inline preview in the view modal.

Troubleshooting

- If attachments fail but are present in S3: check Lambda & app logs; recent updates ensure the upload endpoint returns `attachment.type` and `attachment.url` so the frontend can render safely.
- If share links point to API Gateway domain: ensure `APP_DOMAIN` is set in Lambda environment and redeploy.

Linting & formatting

- Use your preferred Python linter and formatters. Keep `serverless/app/requirements.txt` consistent with Lambda runtime.

Security

- Never commit `SECRET_KEY` or OAuth client secrets to git. Use Terraform variables or a secrets manager.

Contact

For deployment-related questions, reach out to the platform owner or the repository maintainer.
