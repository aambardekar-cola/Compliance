#!/usr/bin/env python3
"""Wire Datadog monitors to MS Teams via webhook.

Creates a Datadog Webhook integration pointing to MS Teams,
then updates all existing PCO monitors to include the webhook notification.

Usage:
    DD_API_KEY=... DD_APP_KEY=... python setup_teams_alerts.py \
        --env dev \
        --webhook-url "https://collabrios.webhook.office.com/..."
"""
import argparse
import json
import os
import sys

try:
    from datadog_api_client import Configuration, ApiClient
    from datadog_api_client.v1.api.monitors_api import MonitorsApi
    from datadog_api_client.v1.api.webhooks_integration_api import WebhooksIntegrationApi
    from datadog_api_client.v1.model.webhooks_integration import WebhooksIntegration
    from datadog_api_client.v1.model.monitor_update_request import MonitorUpdateRequest
except ImportError:
    print("ERROR: pip install datadog-api-client")
    sys.exit(1)

# Adaptive Card payload for Teams — shows monitor name, status, and link
TEAMS_PAYLOAD = json.dumps({
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "{{#is_alert}}FF0000{{/is_alert}}{{#is_warning}}FFA500{{/is_warning}}{{#is_recovery}}00FF00{{/is_recovery}}",
    "summary": "$EVENT_TITLE",
    "sections": [{
        "activityTitle": "🔔 $EVENT_TITLE",
        "facts": [
            {"name": "Status", "value": "$ALERT_STATUS"},
            {"name": "Priority", "value": "$PRIORITY"},
            {"name": "Tags", "value": "$TAGS"},
        ],
        "text": "$EVENT_MSG",
        "markdown": True,
    }],
    "potentialAction": [{
        "@type": "OpenUri",
        "name": "View in Datadog",
        "targets": [{"os": "default", "uri": "$LINK"}],
    }],
})


def main():
    parser = argparse.ArgumentParser(description="Wire Datadog monitors to MS Teams")
    parser.add_argument("--env", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--webhook-url", required=True, help="MS Teams Incoming Webhook URL")
    args = parser.parse_args()

    webhook_name = f"teams-pco-{args.env}"
    configuration = Configuration()

    with ApiClient(configuration) as api_client:
        # Step 1: Create/update the webhook integration
        webhooks_api = WebhooksIntegrationApi(api_client)
        try:
            webhook = WebhooksIntegration(
                name=webhook_name,
                url=args.webhook_url,
                payload=TEAMS_PAYLOAD,
                encode_as="json",
            )
            result = webhooks_api.create_webhooks_integration(body=webhook)
            print(f"✅ Webhook created: {webhook_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"ℹ️  Webhook '{webhook_name}' already exists, updating...")
                try:
                    webhooks_api.update_webhooks_integration(
                        webhook_name=webhook_name,
                        body=WebhooksIntegration(
                            name=webhook_name,
                            url=args.webhook_url,
                            payload=TEAMS_PAYLOAD,
                            encode_as="json",
                        ),
                    )
                    print(f"✅ Webhook updated: {webhook_name}")
                except Exception as update_err:
                    print(f"❌ Failed to update webhook: {update_err}")
                    sys.exit(1)
            else:
                print(f"❌ Failed to create webhook: {e}")
                sys.exit(1)

        # Step 2: Update all PCO monitors to include webhook notification
        monitors_api = MonitorsApi(api_client)
        notify_tag = f"@webhook-{webhook_name}"

        # List monitors with our env tag
        all_monitors = monitors_api.list_monitors(
            tags=f"env:{args.env}",
        )

        pco_monitors = [m for m in all_monitors if "pco" in (m.name or "").lower() or "compliance" in (m.name or "").lower()]
        print(f"\n🔔 Found {len(pco_monitors)} PCO monitors for [{args.env}], adding Teams notifications...")

        for monitor in pco_monitors:
            current_msg = monitor.message or ""
            if notify_tag in current_msg:
                print(f"  ⏭ Already has Teams: {monitor.name}")
                continue

            updated_msg = f"{current_msg}\n\n{notify_tag}"
            try:
                monitors_api.update_monitor(
                    monitor_id=monitor.id,
                    body=MonitorUpdateRequest(message=updated_msg),
                )
                print(f"  ✅ Updated: {monitor.name}")
            except Exception as e:
                print(f"  ❌ Failed: {monitor.name} — {e}")

    print(f"\n✅ Teams alerts configured! Alerts will route to your Teams channel.")


if __name__ == "__main__":
    main()
