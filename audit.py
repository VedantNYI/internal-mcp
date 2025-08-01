#!/usr/bin/env python3
"""
Website Audit MCP Server
A minimal MCP server for website auditing using Playwright.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Browser, Page
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Website Audit")

class WebsiteAuditor:
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def get_page(self, url: str) -> Page:
        """Create a new page and navigate to URL."""
        page = await self.browser.new_page()
        
        # Set reasonable timeouts
        page.set_default_timeout(30000)  # 30 seconds
        
        # Navigate to the page
        response = await page.goto(url, wait_until='networkidle')
        
        # Wait a bit more for any lazy-loaded content
        await page.wait_for_timeout(2000)
        
        return page, response

@mcp.tool()
async def get_page_info(url: str) -> Dict[str, Any]:
    """
    Get basic page information including title, meta description, and response status.
    
    Args:
        url: The URL to analyze
        
    Returns:
        Dictionary containing page information
    """
    try:
        async with WebsiteAuditor() as auditor:
            page, response = await auditor.get_page(url)
            
            # Get basic page info
            title = await page.title()
            
            # Get meta description
            meta_desc_element = await page.query_selector('meta[name="description"]')
            meta_desc = ""
            if meta_desc_element:
                meta_desc = await meta_desc_element.get_attribute('content') or ""
            
            # Count elements
            h1_count = len(await page.query_selector_all('h1'))
            h2_count = len(await page.query_selector_all('h2'))
            image_count = len(await page.query_selector_all('img'))
            link_count = len(await page.query_selector_all('a[href]'))
            
            # Get page load time
            load_time = await page.evaluate("""
                () => {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    return perfData ? perfData.loadEventEnd - perfData.fetchStart : null;
                }
            """)
            
            await page.close()
            
            return {
                "url": url,
                "status_code": response.status if response else None,
                "title": title,
                "title_length": len(title),
                "meta_description": meta_desc,
                "meta_description_length": len(meta_desc),
                "h1_count": h1_count,
                "h2_count": h2_count,
                "image_count": image_count,
                "link_count": link_count,
                "load_time_ms": round(load_time) if load_time else None
            }
            
    except Exception as e:
        return {"error": f"Error analyzing {url}: {str(e)}"}

@mcp.tool()
async def check_meta_tags(url: str) -> Dict[str, Any]:
    """
    Check for essential SEO meta tags.
    
    Args:
        url: The URL to check
        
    Returns:
        Dictionary containing meta tag analysis
    """
    try:
        async with WebsiteAuditor() as auditor:
            page, response = await auditor.get_page(url)
            
            # Check for various meta tags
            meta_checks = {
                "title": await page.query_selector('title') is not None,
                "meta_description": await page.query_selector('meta[name="description"]') is not None,
                "meta_keywords": await page.query_selector('meta[name="keywords"]') is not None,
                "og_title": await page.query_selector('meta[property="og:title"]') is not None,
                "og_description": await page.query_selector('meta[property="og:description"]') is not None,
                "og_image": await page.query_selector('meta[property="og:image"]') is not None,
                "twitter_card": await page.query_selector('meta[name="twitter:card"]') is not None,
                "canonical": await page.query_selector('link[rel="canonical"]') is not None,
                "viewport": await page.query_selector('meta[name="viewport"]') is not None,
                "charset": await page.query_selector('meta[charset]') is not None,
                "robots": await page.query_selector('meta[name="robots"]') is not None
            }
            
            # Calculate completeness score
            total_tags = len(meta_checks)
            present_tags = sum(meta_checks.values())
            completeness_score = (present_tags / total_tags) * 100
            
            await page.close()
            
            return {
                "url": url,
                "meta_tags": meta_checks,
                "completeness_score": round(completeness_score, 1),
                "missing_tags": [tag for tag, present in meta_checks.items() if not present]
            }
            
    except Exception as e:
        return {"error": f"Error checking meta tags for {url}: {str(e)}"}

@mcp.tool()
async def get_images_without_alt(url: str) -> Dict[str, Any]:
    """
    Find images without alt text for accessibility audit.
    
    Args:
        url: The URL to check
        
    Returns:
        Dictionary containing image analysis
    """
    try:
        async with WebsiteAuditor() as auditor:
            page, response = await auditor.get_page(url)
            
            # Get all images and check alt text
            images_data = await page.evaluate("""
                () => {
                    const images = Array.from(document.querySelectorAll('img'));
                    return images.map(img => ({
                        src: img.src,
                        alt: img.alt || '',
                        hasAlt: Boolean(img.alt && img.alt.trim())
                    }));
                }
            """)
            
            total_images = len(images_data)
            images_without_alt = [img for img in images_data if not img['hasAlt']]
            missing_alt_count = len(images_without_alt)
            
            accessibility_score = ((total_images - missing_alt_count) / total_images * 100) if total_images > 0 else 100
            
            await page.close()
            
            return {
                "url": url,
                "total_images": total_images,
                "images_without_alt": missing_alt_count,
                "accessibility_score": round(accessibility_score, 1),
                "missing_alt_images": [img['src'] for img in images_without_alt[:10]]  # Limit to first 10
            }
            
    except Exception as e:
        return {"error": f"Error checking images for {url}: {str(e)}"}

@mcp.tool()
async def check_page_performance(url: str) -> Dict[str, Any]:
    """
    Get basic performance metrics using Playwright.
    
    Args:
        url: The URL to check
        
    Returns:
        Dictionary containing performance metrics
    """
    try:
        async with WebsiteAuditor() as auditor:
            page, response = await auditor.get_page(url)
            
            # Get performance metrics
            metrics = await page.evaluate("""
                () => {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    if (!perfData) return null;
                    
                    return {
                        dns_lookup: perfData.domainLookupEnd - perfData.domainLookupStart,
                        tcp_connect: perfData.connectEnd - perfData.connectStart,
                        request_time: perfData.responseStart - perfData.requestStart,
                        response_time: perfData.responseEnd - perfData.responseStart,
                        dom_loading: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                        total_load_time: perfData.loadEventEnd - perfData.fetchStart,
                        first_paint: null,
                        first_contentful_paint: null
                    };
                }
            """)
            
            # Try to get paint metrics
            paint_metrics = await page.evaluate("""
                () => {
                    const paintEntries = performance.getEntriesByType('paint');
                    const result = {};
                    paintEntries.forEach(entry => {
                        if (entry.name === 'first-paint') {
                            result.first_paint = entry.startTime;
                        } else if (entry.name === 'first-contentful-paint') {
                            result.first_contentful_paint = entry.startTime;
                        }
                    });
                    return result;
                }
            """)
            
            if metrics and paint_metrics:
                metrics.update(paint_metrics)
            
            # Get resource counts
            resource_counts = await page.evaluate("""
                () => {
                    const resources = performance.getEntriesByType('resource');
                    const counts = {
                        scripts: 0,
                        stylesheets: 0,
                        images: 0,
                        fonts: 0,
                        other: 0
                    };
                    
                    resources.forEach(resource => {
                        if (resource.initiatorType === 'script') counts.scripts++;
                        else if (resource.initiatorType === 'css') counts.stylesheets++;
                        else if (resource.initiatorType === 'img') counts.images++;
                        else if (resource.initiatorType === 'font') counts.fonts++;
                        else counts.other++;
                    });
                    
                    return {
                        ...counts,
                        total_requests: resources.length
                    };
                }
            """)
            
            await page.close()
            
            return {
                "url": url,
                "timing_metrics": metrics,
                "resource_counts": resource_counts,
                "status_code": response.status if response else None
            }
            
    except Exception as e:
        return {"error": f"Error checking performance for {url}: {str(e)}"}

@mcp.tool()
async def quick_seo_audit(url: str) -> Dict[str, Any]:
    """
    Perform a quick SEO audit combining multiple checks.
    
    Args:
        url: The URL to audit
        
    Returns:
        Dictionary containing comprehensive SEO analysis
    """
    try:
        # Run all checks concurrently
        page_info_task = get_page_info(url)
        meta_tags_task = check_meta_tags(url)
        images_task = get_images_without_alt(url)
        performance_task = check_page_performance(url)
        
        page_info, meta_tags, images, performance = await asyncio.gather(
            page_info_task, meta_tags_task, images_task, performance_task
        )
        
        # Calculate overall SEO score
        scores = []
        
        # Title score (50-60 chars is optimal)
        if 'title_length' in page_info and not page_info.get('error'):
            title_len = page_info['title_length']
            if 50 <= title_len <= 60:
                title_score = 100
            elif 30 <= title_len <= 70:
                title_score = 80
            else:
                title_score = 50
            scores.append(title_score)
        
        # Meta description score (150-160 chars is optimal)
        if 'meta_description_length' in page_info and not page_info.get('error'):
            desc_len = page_info['meta_description_length']
            if 150 <= desc_len <= 160:
                desc_score = 100
            elif 120 <= desc_len <= 180:
                desc_score = 80
            else:
                desc_score = 50 if desc_len > 0 else 0
            scores.append(desc_score)
        
        # Meta tags completeness score
        if 'completeness_score' in meta_tags and not meta_tags.get('error'):
            scores.append(meta_tags['completeness_score'])
        
        # Accessibility score
        if 'accessibility_score' in images and not images.get('error'):
            scores.append(images['accessibility_score'])
        
        # Performance score (basic - load time under 3s gets good score)
        if 'timing_metrics' in performance and not performance.get('error'):
            timing = performance['timing_metrics']
            if timing and timing.get('total_load_time'):
                load_time = timing['total_load_time']
                if load_time < 1000:  # Under 1s
                    perf_score = 100
                elif load_time < 3000:  # Under 3s
                    perf_score = 80
                elif load_time < 5000:  # Under 5s
                    perf_score = 60
                else:
                    perf_score = 40
                scores.append(perf_score)
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "url": url,
            "overall_seo_score": round(overall_score, 1),
            "page_info": page_info,
            "meta_tags": meta_tags,
            "images_audit": images,
            "performance": performance,
            "recommendations": _generate_recommendations(page_info, meta_tags, images, performance)
        }
        
    except Exception as e:
        return {"error": f"Error performing SEO audit for {url}: {str(e)}"}

def _generate_recommendations(page_info: Dict, meta_tags: Dict, images: Dict, performance: Dict) -> List[str]:
    """Generate SEO recommendations based on audit results."""
    recommendations = []
    
    # Title recommendations
    if 'title_length' in page_info and not page_info.get('error'):
        title_len = page_info['title_length']
        if title_len < 30:
            recommendations.append("Title is too short. Aim for 50-60 characters.")
        elif title_len > 70:
            recommendations.append("Title is too long. Keep it under 60 characters.")
    
    # Meta description recommendations
    if 'meta_description_length' in page_info and not page_info.get('error'):
        desc_len = page_info['meta_description_length']
        if desc_len == 0:
            recommendations.append("Add a meta description (150-160 characters).")
        elif desc_len < 120:
            recommendations.append("Meta description is too short. Aim for 150-160 characters.")
        elif desc_len > 180:
            recommendations.append("Meta description is too long. Keep it under 160 characters.")
    
    # H1 recommendations
    if 'h1_count' in page_info and not page_info.get('error'):
        h1_count = page_info['h1_count']
        if h1_count == 0:
            recommendations.append("Add at least one H1 tag to the page.")
        elif h1_count > 1:
            recommendations.append("Use only one H1 tag per page.")
    
    # Meta tags recommendations
    if 'missing_tags' in meta_tags and not meta_tags.get('error'):
        missing = meta_tags['missing_tags']
        if 'og_title' in missing or 'og_description' in missing:
            recommendations.append("Add Open Graph tags for better social media sharing.")
        if 'canonical' in missing:
            recommendations.append("Add canonical URL to avoid duplicate content issues.")
        if 'viewport' in missing:
            recommendations.append("Add viewport meta tag for mobile responsiveness.")
        if 'charset' in missing:
            recommendations.append("Add charset meta tag for proper encoding.")
    
    # Image recommendations
    if 'images_without_alt' in images and not images.get('error'):
        if images['images_without_alt'] > 0:
            recommendations.append(f"Add alt text to {images['images_without_alt']} images for better accessibility.")
    
    # Performance recommendations
    if 'timing_metrics' in performance and not performance.get('error'):
        timing = performance['timing_metrics']
        if timing and timing.get('total_load_time'):
            load_time = timing['total_load_time']
            if load_time > 3000:
                recommendations.append(f"Page load time is {load_time/1000:.1f}s. Optimize for faster loading (aim for under 3s).")
    
    return recommendations

if __name__ == "__main__":
    mcp.run()