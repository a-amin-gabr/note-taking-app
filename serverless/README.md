# Serverless Deployment — Stage 4

Deploys the Note-Taking App as a **fully serverless architecture** on AWS using **Terraform** — zero servers, near-zero cost.

## Architecture

```
          Route 53 → CloudFront (CDN + SSL)
                      ├── /static/*  → S3 (cached assets)
                      └── /*         → API Gateway → Lambda (Flask)
                                                      ├── DynamoDB
                                                      └── S3 (attachments)
```

## Cost Comparison

| Resource | EC2 (Stage 1–3) | Serverless (Stage 4) |
| :--- | :--- | :--- |
| Compute | ~$8.50/mo | Lambda — Free Tier |
| Database | MariaDB on EC2 | DynamoDB — Free Tier |
| Web Server | Nginx on EC2 | CloudFront — Free Tier |
| **Total** | **~$12/mo** | **~$0.50/mo** |

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) (v1.5+)
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- An existing Route 53 hosted zone for your domain

## Quick Start

**1. Configure your variables:**

```bash
cd serverless/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your actual values
```

**2. Create the S3 backend bucket (one-time):**

```bash
aws s3 mb s3://notes-app-terraform-state --region eu-central-1
```

If you want a different state bucket or region, export `TF_STATE_BUCKET` and `TF_STATE_REGION` before running the deploy script.

**3. Deploy everything:**

```bash
cd serverless/scripts
chmod +x deploy.sh
./deploy.sh
```

The deploy script passes the Terraform backend settings with `-backend-config`, so the state bucket is configurable without editing `main.tf`.

This will:
1. Package the Lambda function (install deps + zip)
2. Run `terraform apply` (create all AWS resources)
3. Sync static assets to S3
4. Invalidate CloudFront cache

## Structure

```
serverless/
├── app/                         # Lambda application
│   ├── app.py                   # Flask routes (DynamoDB)
│   ├── auth.py                  # Cognito + Guest auth
│   ├── db.py                    # DynamoDB data access layer
│   ├── lambda_handler.py        # Mangum entry point
│   ├── requirements.txt         # Python dependencies
│   └── templates/               # Jinja2 templates
│
├── terraform/                   # Root module
│   ├── main.tf                  # Provider + module composition
│   ├── variables.tf             # Input variables
│   ├── outputs.tf               # Final URLs
│   └── modules/                 # Reusable child modules
│       ├── database/            # DynamoDB (single-table)
│       ├── storage/             # S3 (static + attachments)
│       ├── compute/             # Lambda + API Gateway + IAM
│       ├── cdn/                 # CloudFront + ACM certificate
│       └── dns/                 # Route 53 records
│
├── scripts/
│   ├── deploy.sh                # Full deployment
│   └── deploy-static.sh         # Static assets only
└── .gitignore
```

## Terraform Modules

| Module | Resources Created |
| :--- | :--- |
| `database` | DynamoDB table (single-table design, GSI, PITR) |
| `storage` | S3 buckets (public static + private attachments) |
| `compute` | Lambda function, IAM role, API Gateway HTTP API |
| `cdn` | CloudFront distribution, ACM certificate |
| `dns` | Route 53 A record → CloudFront |

## Common Commands

| Command | Description |
| :--- | :--- |
| `./scripts/deploy.sh` | Full deploy (Lambda + Terraform + static) |
| `./scripts/deploy-static.sh` | Sync only static assets to S3 |
| `terraform -chdir=terraform plan` | Preview infrastructure changes |
| `terraform -chdir=terraform output` | Show deployed URLs |
| `terraform -chdir=terraform destroy` | Tear down everything |

## Environment Variables

- `APP_DOMAIN` — (optional) public domain for share links (e.g. notes.example.com). When set, the app will build share links using this domain instead of the API Gateway host.
- `DYNAMODB_TABLE` — DynamoDB table name used by Lambda.
- `S3_BUCKET` — S3 bucket used for attachments and assets.
- `S3_REGION` — region of the S3 bucket.
- `SECRET_KEY` — Flask secret key for session encryption (sensitive).
- `USE_FAKE_DDB` — Set to `1` to run a local in-memory mock DB (default for local dev). Lambda should have this set to `0`.

## Local Development

1. Create and activate a Python virtualenv (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
```

2. Install dependencies and run the Flask app locally (mock DB):

```powershell
pip install -r serverless/app/requirements.txt
$env:FLASK_APP='serverless/app/app.py'
$env:USE_FAKE_DDB='1'   # use mock DB for local testing
python -m flask run --host=127.0.0.1 --port=5000
```

3. Test flows in the browser: create a guest session (`/auth/guest`), create a note, test Edit / Share / Delete, upload attachments.

## Troubleshooting

- Share links show API Gateway domain: ensure `APP_DOMAIN` is set in Lambda environment (Terraform sets `APP_DOMAIN = var.app_domain`). Redeploy if needed.
- Attachments upload shows "Upload error" even when file uploaded: check API returns `attachment.type` and `attachment.url`. Recent fixes include returning `type` from upload API and safer frontend parsing.
- If static assets show old content after deploy: wait for CloudFront invalidation to finish or run `./scripts/deploy-static.sh`.

## Rollback

If a deployment causes regressions:

1. Run `terraform -chdir=terraform plan` to inspect changes.
2. Use `terraform -chdir=terraform apply -auto-approve` to re-apply a previous configuration if you have it in VCS.
3. Optionally use `terraform -chdir=terraform output` to find resources and manually revert (last resort).

## Security & Maintenance Notes

- Keep `secret_key` and OAuth client secrets in a secure secrets backend — do not commit them to git. Use Terraform variables and env var injection.
- Limit IAM roles (least privilege): Lambda role grants DynamoDB and S3 access scoped to the specific resources.
- Monitor CloudWatch logs for errors (Lambda / API Gateway) and set up alerting for elevated error rates.

## Change Log (recent)

- 2026-05-13: Fixed `note.id` mapping; ensured Lambda uses real DynamoDB by setting `USE_FAKE_DDB=0` in Terraform; fixed share URL generation to prefer `APP_DOMAIN`; fixed attachment upload response to include `type`; added inline image previews in the view modal; updated docs.

## Key Improvements Over Docker

| Feature | Docker (Stage 3) | Serverless (Stage 4) |
| :--- | :--- | :--- |
| Cost | ~$12/mo (EC2 required) | ~$0.50/mo (pay-per-request) |
| Scaling | Manual (add containers) | Automatic (Lambda scales to 1000+) |
| Maintenance | OS patches, Docker updates | Zero (AWS manages everything) |
| Cold start | None | ~1-2s on first request |
| Infrastructure | Imperative (docker-compose) | Declarative (Terraform) |
