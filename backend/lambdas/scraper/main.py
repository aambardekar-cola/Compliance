import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

import boto3
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from shared.db import get_db_session
from shared.models import (
    ComplianceRuleUrl, ScrapedContent,
    PipelineRun, PipelineRunType, PipelineRunStatus,
    AdminNotification, NotificationType,
)
from shared.logging import get_pipeline_logger

logger = get_pipeline_logger("scraper")


async def scrape_url(client: httpx.AsyncClient, url: str) -> str:
    """Fetch structured JSON/XML for known Gov APIs, else fallback to HTML."""
    try:
        # Federal Register: Extract Document ID and use API
        if "federalregister.gov" in url:
            # Parse document ID like "2024-07105" from the URL
            parts = url.split("/")
            doc_id = next((p for p in parts if "-" in p and p[0].isdigit() and len(p.split("-")[0]) == 4), None)
            
            if doc_id:
                api_url = f"https://www.federalregister.gov/api/v1/documents/{doc_id}.json"
                r = await client.get(api_url)
                r.raise_for_status()
                data = r.json()
                if "raw_text_url" in data:
                    r2 = await client.get(data["raw_text_url"])
                    r2.raise_for_status()
                    return r2.text
                return data.get("abstract", "")
                
        # eCFR: Look up latest issue date, then fetch XML API
        if "ecfr.gov" in url and "title-" in url and "part-" in url:
            title = url.split("title-")[1].split("/")[0]
            part = url.split("part-")[1].split("/")[0]
            
            date_r = await client.get("https://www.ecfr.gov/api/versioner/v1/titles.json")
            date_r.raise_for_status()
            titles = date_r.json().get("titles", [])
            target = next((t for t in titles if str(t.get("number")) == title), None)
            
            if target:
                issue_date = target.get("latest_issue_date")
                api_url = f"https://www.ecfr.gov/api/versioner/v1/full/{issue_date}/title-{title}.xml?part={part}"
                r = await client.get(api_url, headers={"User-Agent": "PaceCareOnline/1.0"})
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                return soup.get_text(separator="\n", strip=True)

        # Fallback HTML scraping (e.g. CMS)
        response = await client.get(url, timeout=30.0, follow_redirects=True, headers={"User-Agent": "PaceCareOnline/1.0"})
        response.raise_for_status()
        
        # Parse HTML and extract visible text
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script, style, header, footer, and nav elements
        for element in soup(["script", "style", "header", "footer", "nav", "noscript", "iframe"]):
            element.extract()
            
        text = soup.get_text(separator=" ", strip=True)
        return text
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return ""


async def run_scraper(event: Dict[str, Any] = None) -> Dict[str, Any]:
    """Fetch active URLs from DB, scrape them, and store changes."""
    await logger.info("Starting regulatory URL scraper")
    start_time = datetime.utcnow()
    
    stats = {"urls_processed": 0, "updates_found": 0, "errors": 0}
    error_messages = []
    pipeline_run_id = None

    # Create pipeline run record for tracking
    try:
        async with get_db_session() as session:
            pipeline_run = PipelineRun(
                run_type=PipelineRunType.SCRAPER,
                status=PipelineRunStatus.STARTED,
                started_at=start_time,
            )
            session.add(pipeline_run)
            await session.commit()
            pipeline_run_id = pipeline_run.id
    except Exception as e:
        await logger.error(f"Failed to create PipelineRun: {e}")

    try:
        # First, fetch the list of active URLs
        async with get_db_session() as session:
            result = await session.execute(
                select(ComplianceRuleUrl).where(ComplianceRuleUrl.is_active == True)
            )
            active_urls = result.scalars().all()
            # Detach URL data so we can use it outside this session
            url_data = [{"id": u.id, "name": u.name, "url": u.url} for u in active_urls]
        
        if not url_data:
            await logger.warning("No active compliance URLs found to scrape.")
            return {"statusCode": 200, "body": json.dumps(stats)}
            
        await logger.info(f"Found {len(url_data)} active URLs to process.")
        
        async with httpx.AsyncClient() as client:
            for rule_url in url_data:
                # Each URL gets its own DB session so one failure doesn't
                # roll back all successfully scraped content.
                try:
                    await logger.info(f"Scraping: {rule_url['name']}", {"url": rule_url["url"], "id": str(rule_url["id"])})
                    text_content = await scrape_url(client, rule_url["url"])
                    
                    if not text_content:
                        await logger.error(f"Failed to scrape {rule_url['name']}: No content returned", {"url": rule_url["url"]})
                        stats["errors"] += 1
                        error_messages.append(f"{rule_url['name']}: No content")
                        continue
                        
                    # Hash the text to check for changes
                    content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
                    
                    # Strip null bytes — PostgreSQL rejects \x00 in text columns
                    text_content = text_content.replace("\x00", "")
                    
                    async with get_db_session() as session:
                        # Check the most recent scrape for this URL
                        recent_scrape = await session.execute(
                            select(ScrapedContent)
                            .where(ScrapedContent.url_id == rule_url["id"])
                            .order_by(ScrapedContent.scraped_at.desc())
                            .limit(1)
                        )
                        last_scrape = recent_scrape.scalar_one_or_none()
                        
                        if not last_scrape or last_scrape.content_hash != content_hash:
                            await logger.info(f"New or updated content detected for '{rule_url['name']}'")
                            new_content = ScrapedContent(
                                url_id=rule_url["id"],
                                content_text=text_content,
                                content_hash=content_hash,
                                is_processed=False
                            )
                            session.add(new_content)
                            await session.flush()
                            
                            # Queue for gap analysis
                            queue_url = os.environ.get("ANALYSIS_QUEUE_URL")
                            if queue_url:
                                try:
                                    sqs = boto3.client("sqs")
                                    sqs.send_message(
                                        QueueUrl=queue_url,
                                        MessageBody=json.dumps({
                                            "scraped_content_id": str(new_content.id),
                                            "url_name": rule_url["name"]
                                        })
                                    )
                                    await logger.info(f"Queued ScrapedContent {new_content.id} for analysis.")
                                except Exception as e:
                                    await logger.error(f"Failed to queue for analysis: {e}", exc_info=True)
                            
                            stats["updates_found"] += 1
                        else:
                            await logger.info(f"No changes detected for '{rule_url['name']}'")
                        
                        # Commit is handled by get_db_session() context manager
                    
                    stats["urls_processed"] += 1
                    await logger.info(f"Successfully processed: {rule_url['name']}")
                except Exception as e:
                    await logger.error(f"Unexpected error scraping {rule_url['name']}: {e}", {"url": rule_url["url"]}, exc_info=True)
                    stats["errors"] += 1
                    error_messages.append(f"{rule_url['name']}: {str(e)[:100]}")

        await logger.info(f"Scraper completed: {stats}")
    finally:
        # Finalize pipeline run — always runs even on Lambda timeout
        if pipeline_run_id:
            try:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                async with get_db_session() as session:
                    run = await session.get(PipelineRun, pipeline_run_id)
                    if run:
                        run.status = (
                            PipelineRunStatus.FAILED if stats["errors"] > 0 and stats["urls_processed"] == 0
                            else PipelineRunStatus.PARTIAL if stats["errors"] > 0
                            else PipelineRunStatus.COMPLETED
                        )
                        run.ended_at = end_time
                        run.duration_seconds = duration
                        run.urls_scraped = stats["urls_processed"]
                        run.errors_count = stats["errors"]
                        run.error_message = "; ".join(error_messages[:5]) if error_messages else None

                        # Create notification
                        if stats["errors"] > 0 and stats["urls_processed"] == 0:
                            notif_type = NotificationType.PIPELINE_FAILED
                            title = "Scraper Pipeline Failed"
                            message = f"Scraper failed: {'; '.join(error_messages[:3])}"
                        else:
                            notif_type = NotificationType.PIPELINE_COMPLETED
                            title = "Scraper Pipeline Completed"
                            parts = []
                            if stats["urls_processed"]:
                                parts.append(f"{stats['urls_processed']} URL(s) scraped")
                            if stats["updates_found"]:
                                parts.append(f"{stats['updates_found']} update(s) found")
                            if stats["errors"]:
                                parts.append(f"{stats['errors']} error(s)")
                            message = ("Scraper completed: " + ", ".join(parts)) if parts else "Scraper completed with no changes."

                        notification = AdminNotification(
                            pipeline_run_id=pipeline_run_id,
                            notification_type=notif_type,
                            title=title,
                            message=message,
                            metadata_json={
                                "urls_processed": stats["urls_processed"],
                                "updates_found": stats["updates_found"],
                                "errors": stats["errors"],
                                "duration_seconds": round(duration, 1),
                            },
                        )
                        session.add(notification)
                        await session.commit()
            except Exception as e:
                await logger.error(f"Failed to finalize scraper PipelineRun: {e}")

    return {
        "statusCode": 200,
        "body": json.dumps(stats)
    }

def handler(event, context):
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(run_scraper(event))

