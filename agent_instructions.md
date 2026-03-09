# Agent Pre-requisites & Instructions

*This file contains persistent instructions for the AI agent to follow during all development tasks on the Compliance project.*

## 1. Architectural Explanations First
- **Rule**: Before making any code changes, infrastructure updates, or executing automated scripts, the agent MUST explicitly explain the proposed architecture, data flow, and exact planned changes to the user.
- **Reason**: To provide safeguards, ensure transparency, and allow the user to approve the design before execution.

## 2. Admin Infrastructure Page Updates
- **Rule**: Whenever new AWS infrastructure is added (e.g., a new S3 bucket, a new Lambda function, an SQS queue, changes to CDK outputs), the agent MUST immediately update the corresponding "Environments" Admin page in the frontend UI to display this new infrastructure.
- **Reason**: The internal Admin UI must always serve as an accurate, living dashboard of the current AWS deployment state. If the CDK stack changes, the UI displaying that stack must change in the same PR.

## 3. Reliability & Testing
- **Rule**: ALWAYS test code locally (syntax check, dry-run, or unit test) BEFORE pushing to Git.
- **Rule**: If a mistake is made twice, or a similar error occurs twice, the agent MUST implement logic or safeguards to ensure it NEVER repeats.
- **Rule**: ALWAYS write unit tests for all new code. This is **non-negotiable**.

## 4. Environment Dependencies
- **Rule**: Do not assume existence of the GitHub CLI (`gh`). If you need to check workflow status, use `curl` with the GitHub API as a fallback. If a system tool is missing, document the workaround here to fix it "once for all".

## 5. Master Plan
- **Rule**: The master plan artifact (`master_plan.md` in the brain directory) MUST always be kept up to date. Whenever phases change, priorities shift, or architectural decisions are made, update the master plan immediately.
- **Rule**: Reference the master plan at the start of new conversations to maintain continuity across sessions.
- **Location**: `<appDataDir>/brain/<conversation-id>/master_plan.md`
