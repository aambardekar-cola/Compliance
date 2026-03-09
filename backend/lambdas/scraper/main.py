import asyncio
import hashlib
import json
import logging
import os
from typing import Dict, Any

import boto3
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from shared.db import get_db_session
from shared.models import ComplianceRuleUrl, ScrapedContent
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
    
    stats = {"urls_processed": 0, "updates_found": 0, "errors": 0}
    
    async with get_db_session() as session:
        # Get active URLs
        result = await session.execute(
            select(ComplianceRuleUrl).where(ComplianceRuleUrl.is_active == True)
        )
        active_urls = result.scalars().all()
        
        if not active_urls:
            await logger.warning("No active compliance URLs found to scrape.")
            return {"statusCode": 200, "body": json.dumps(stats)}
            
        await logger.info(f"Found {len(active_urls)} active URLs to process.")
        
        async with httpx.AsyncClient() as client:
            for rule_url in active_urls:
                await logger.info(f"Scraping: {rule_url.name}", {"url": rule_url.url, "id": str(rule_url.id)})
                try:
                    text_content = await scrape_url(client, rule_url.url)
                    
                    if not text_content:
                        await logger.error(f"Failed to scrape {rule_url.name}: No content returned", {"url": rule_url.url})
                        stats["errors"] += 1
                        continue
                        
                    # Hash the text to check for changes
                    content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
                    
                    # Check the most recent scrape for this URL
                    recent_scrape = await session.execute(
                        select(ScrapedContent)
                        .where(ScrapedContent.url_id == rule_url.id)
                        .order_by(ScrapedContent.scraped_at.desc())
                        .limit(1)
                    )
                    last_scrape = recent_scrape.scalar_one_or_none()
                    
                    if not last_scrape or last_scrape.content_hash != content_hash:
                        # Content has changed or is new, insert new record
                        await logger.info(f"New or updated content detected for '{rule_url.name}'")
                        new_content = ScrapedContent(
                            url_id=rule_url.id,
                            content_text=text_content,
                            content_hash=content_hash,
                            is_processed=False
                        )
                        session.add(new_content)
                        
                        # We must flush to get the new_content ID
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
                                        "url_name": rule_url.name
                                    })
                                )
                                await logger.info(f"Queued ScrapedContent {new_content.id} for analysis.")
                            except Exception as e:
                                await logger.error(f"Failed to queue for analysis: {e}", exc_info=True)
                        
                        stats["updates_found"] += 1
                    else:
                        await logger.info(f"No changes detected for '{rule_url.name}'")
                    
                    stats["urls_processed"] += 1
                except Exception as e:
                    await logger.error(f"Unexpected error scraping {rule_url.name}: {e}", {"url": rule_url.url}, exc_info=True)
                    stats["errors"] += 1

        await session.commit()
    
    await logger.info(f"Scraper completed: {stats}")
    return {
        "statusCode": 200,
        "body": json.dumps(stats)
    }

def handler(event, context):
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(run_scraper(event))
