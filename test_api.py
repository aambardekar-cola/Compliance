import asyncio
import httpx

async def run():
    async with httpx.AsyncClient() as client:
        # Test eCFR API
        print("== eCFR API ==")
        url = "https://www.ecfr.gov/api/versioner/v1/full/2026-03-08/title-42.xml?part=460"
        try:
            r = await client.get(url, headers={"User-Agent": "PaceCareOnline/1.0 (admin@pacecareonline.com)"})
            r.raise_for_status()
            print(f"Success! Fetched {len(r.text)} bytes of XML.")
            print(r.text[:500])
        except Exception as e:
            print(f"Failed eCFR: {e}")
            if hasattr(e, "response") and e.response:
                print(e.response.text[:500])
                
        # Test Federal Register API
        print("\n== Federal Register API ==")
        url = "https://www.federalregister.gov/api/v1/documents/2024-07105.json"
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            print(f"Success! Title: {data['title']}")
            if 'raw_text_url' in data:
                print(f"Raw Text URL: {data['raw_text_url']}")
                r2 = await client.get(data['raw_text_url'])
                print(f"Raw Text fetch success, {len(r2.text)} bytes")
        except Exception as e:
            print(f"Failed FedReg: {e}")

        # Test CMS
        print("\n== CMS PACE Homepage ==")
        url = "https://www.cms.gov/medicare/medicare-medicaid-coordination/program-all-inclusive-care-elderly-pace"
        try:
            r = await client.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            r.raise_for_status()
            print(f"Success! CMS page is functional, {len(r.text)} bytes.")
        except Exception as e:
            print(f"Failed CMS: {e}")

if __name__ == "__main__":
    asyncio.run(run())
