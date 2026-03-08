import asyncio
import sys
import os
import httpx

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from lambdas.scraper.main import scrape_url

urls = [
    "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-E/part-460",
    "https://www.federalregister.gov/documents/2024/04/04/2024-07105/medicare-and-medicaid-programs-contract-year-2025-policy-and-technical-changes-to-the-medicare",
    "https://www.medicaid.gov/medicaid/long-term-services-supports/program-all-inclusive-care-elderly/index.html"
]

async def run():
    async with httpx.AsyncClient() as client:
        for url in urls:
            print(f"== SCRAPING: {url} ==")
            try:
                text = await scrape_url(client, url)
                if not text:
                    print("Failed to scrape or returned empty.\n")
                    continue
                
                print(f"Characters Extracted: {len(text)}")
                print("Preview:")
                print(text[:1500].strip())
                print("\n" + "="*80 + "\n")
            except Exception as e:
                print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(run())
