# Agent Pre-requisites & Instructions

*This file contains persistent instructions for the AI agent to follow during all development tasks on the Compliance project.*

## 1. Architectural Explanations First
- **Rule**: Before making any code changes, infrastructure updates, or executing automated scripts, the agent MUST explicitly explain the proposed architecture, data flow, and exact planned changes to the user.
- **Reason**: To provide safeguards, ensure transparency, and allow the user to approve the design before execution.

## 2. Admin Infrastructure Page Updates
- **Rule**: Whenever new AWS infrastructure is added (e.g., a new S3 bucket, a new Lambda function, an SQS queue, changes to CDK outputs), the agent MUST immediately update the corresponding "Environments" Admin page in the frontend UI to display this new infrastructure.
- **Reason**: The internal Admin UI must always serve as an accurate, living dashboard of the current AWS deployment state. If the CDK stack changes, the UI displaying that stack must change in the same PR.
