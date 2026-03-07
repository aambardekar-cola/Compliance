# PaceCareOnline Compliance Intelligence Platform

An AI-powered compliance monitoring platform for Collabrios Health's PACE Market EHR. Automatically monitors regulatory changes from CMS and other federal sources, analyzes codebase impact, generates client communications, tracks remediation in Jira, and delivers weekly executive summaries.

## Architecture

- **Frontend**: React (Vite) hosted on CloudFront + S3
- **Backend**: Python (FastAPI) on AWS Lambda via API Gateway
- **Database**: Aurora Serverless v2 (PostgreSQL)
- **AI**: Amazon Bedrock (Claude 3.5 Sonnet)
- **Auth**: Descope (multi-tenant)
- **Email**: Amazon SES
- **Infrastructure**: AWS CDK (Python)

## Project Structure

```
├── infrastructure/   # AWS CDK stacks
├── backend/          # Python Lambda functions
├── frontend/         # React SPA
└── tests/            # Backend & frontend tests
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- AWS CLI configured
- AWS CDK CLI (`npm install -g aws-cdk`)
- Descope project (with tenant organizations)

## Quick Start

### Backend (local development)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### Frontend (local development)
```bash
cd frontend
npm install
npm run dev
```

### Deploy to AWS
```bash
cd infrastructure
pip install -r requirements.txt
cdk deploy --all
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
# Descope
DESCOPE_PROJECT_ID=your_project_id

# AWS
AWS_REGION=us-east-1

# Database (auto-configured via CDK in production)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/compliance

# Amazon Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```
