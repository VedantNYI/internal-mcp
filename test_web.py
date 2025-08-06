from fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("WebCrawler")

@mcp.tool
async def init_browser(headless: bool = True, viewport: dict = {"width": 1280, "height": 800}):
    """Initialize the browser with specified configurations."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport=viewport)
        page = await context.new_page()
        return {"browser": browser, "context": context, "page": page}

@mcp.tool
async def get_all_links(page, base_url: str):
    """Retrieve all internal and external links from the page."""
    await page.goto(base_url)
    links = await page.locator("a").all_hrefs()
    return links

@mcp.tool
async def fetch_page_source(page, url: str):
    """Fetch the HTML source of the page."""
    await page.goto(url)
    return await page.content()

@mcp.tool
async def crawl_site(base_url: str):
    """Crawl the website and fetch all links."""
    browser_data = await init_browser()
    links = await get_all_links(browser_data["page"], base_url)
    page_source = await fetch_page_source(browser_data["page"], base_url)
    await browser_data["browser"].close()
    return {"links": links, "page_source": page_source}

if __name__ == "__main__":
    mcp.run()
