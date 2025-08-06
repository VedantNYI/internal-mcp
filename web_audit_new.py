# web_audit.py
from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Optional, Any, Union
import json
import asyncio
from urllib.parse import urljoin, urlparse, urlunparse
import time
import sys
from dataclasses import dataclass
from collections import defaultdict

# Import web scraping libraries
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Import Lighthouse CI for performance auditing
try:
    import subprocess
    import tempfile
    import os
    LIGHTHOUSE_AVAILABLE = True
except ImportError:
    LIGHTHOUSE_AVAILABLE = False

# Import requests for HTTP status checking
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Import SSL and socket for certificate checking
try:
    import ssl
    import socket
    from datetime import datetime
    SSL_AVAILABLE = True
except ImportError:
    SSL_AVAILABLE = False

# Axe-core JavaScript for accessibility auditing
AXE_CORE_JS = """
// Axe-core accessibility engine - simplified version for basic checks
window.axeCore = {
    async runAccessibilityChecks() {
        const results = {
            violations: [],
            passes: [],
            incomplete: [],
            total_elements: 0
        };
        
        // Check images for alt text
        const images = document.querySelectorAll('img');
        results.total_elements += images.length;
        
        images.forEach((img, index) => {
            const altText = img.getAttribute('alt');
            const src = img.getAttribute('src') || 'unknown';
            
            if (altText === null) {
                results.violations.push({
                    id: 'image-alt',
                    impact: 'critical',
                    description: 'Images must have alternate text',
                    element: `img[${index}]`,
                    src: src
                });
            } else if (altText.trim() === '') {
                results.violations.push({
                    id: 'image-alt-empty',
                    impact: 'serious',
                    description: 'Images should have meaningful alt text',
                    element: `img[${index}]`,
                    src: src
                });
            } else {
                results.passes.push({
                    id: 'image-alt',
                    element: `img[${index}]`,
                    src: src
                });
            }
        });
        
        // Check for missing labels on form elements
        const formElements = document.querySelectorAll('input, textarea, select');
        results.total_elements += formElements.length;
        
        formElements.forEach((element, index) => {
            const type = element.type || element.tagName.toLowerCase();
            const id = element.id;
            const ariaLabel = element.getAttribute('aria-label');
            const ariaLabelledby = element.getAttribute('aria-labelledby');
            const label = id ? document.querySelector(`label[for="${id}"]`) : null;
            
            if (!ariaLabel && !ariaLabelledby && !label) {
                results.violations.push({
                    id: 'label',
                    impact: 'critical',
                    description: 'Form elements must have labels',
                    element: `${type}[${index}]`,
                    elementId: id || 'no-id'
                });
            } else {
                results.passes.push({
                    id: 'label',
                    element: `${type}[${index}]`,
                    elementId: id || 'no-id'
                });
            }
        });
        
        // Check for proper heading structure
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        results.total_elements += headings.length;
        
        let previousLevel = 0;
        headings.forEach((heading, index) => {
            const level = parseInt(heading.tagName.charAt(1));
            const text = heading.textContent.trim();
            
            if (level > previousLevel + 1) {
                results.violations.push({
                    id: 'heading-order',
                    impact: 'moderate',
                    description: 'Headings should not skip levels',
                    element: `${heading.tagName.toLowerCase()}[${index}]`,
                    text: text.substring(0, 50)
                });
            }
            
            if (text === '') {
                results.violations.push({
                    id: 'empty-heading',
                    impact: 'minor',
                    description: 'Headings should not be empty',
                    element: `${heading.tagName.toLowerCase()}[${index}]`
                });
            }
            
            previousLevel = level;
        });
        
        // Check for color contrast (basic check using computed styles)
        const textElements = document.querySelectorAll('p, span, div, a, button, h1, h2, h3, h4, h5, h6, li');
        let contrastChecked = 0;
        
        textElements.forEach((element, index) => {
            if (contrastChecked >= 20) return; // Limit to 20 elements for performance
            
            const text = element.textContent.trim();
            if (text.length === 0) return;
            
            const computedStyle = window.getComputedStyle(element);
            const color = computedStyle.color;
            const backgroundColor = computedStyle.backgroundColor;
            
            // Simple contrast check - this is a basic implementation
            if (color && backgroundColor && backgroundColor !== 'rgba(0, 0, 0, 0)') {
                const colorLuminance = this.calculateLuminance(color);
                const backgroundLuminance = this.calculateLuminance(backgroundColor);
                
                const contrast = this.calculateContrastRatio(colorLuminance, backgroundLuminance);
                
                if (contrast < 4.5) { // WCAG AA standard
                    results.violations.push({
                        id: 'color-contrast',
                        impact: 'serious',
                        description: 'Text must have sufficient color contrast',
                        element: `${element.tagName.toLowerCase()}[${index}]`,
                        contrast: contrast.toFixed(2),
                        text: text.substring(0, 30)
                    });
                } else {
                    results.passes.push({
                        id: 'color-contrast',
                        element: `${element.tagName.toLowerCase()}[${index}]`,
                        contrast: contrast.toFixed(2)
                    });
                }
                contrastChecked++;
            }
        });
        
        return results;
    },
    
    // Helper function to calculate luminance
    calculateLuminance(color) {
        const rgb = this.parseColor(color);
        if (!rgb) return 0;
        
        const [r, g, b] = rgb.map(c => {
            c = c / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    },
    
    // Helper function to calculate contrast ratio
    calculateContrastRatio(luminance1, luminance2) {
        const lighter = Math.max(luminance1, luminance2);
        const darker = Math.min(luminance1, luminance2);
        return (lighter + 0.05) / (darker + 0.05);
    },
    
    // Helper function to parse color values
    parseColor(color) {
        const div = document.createElement('div');
        div.style.color = color;
        document.body.appendChild(div);
        const computedColor = window.getComputedStyle(div).color;
        document.body.removeChild(div);
        
        const match = computedColor.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
        return match ? [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])] : null;
    }
};
"""


# Create an MCP server
mcp = FastMCP("web-audit-mcp-server")

# --- Data Classes ---
@dataclass
class CrawlResult:
    """Structure for crawl results"""
    url: str
    title: str
    status_code: int
    links: List[str]
    resources: Dict[str, List[str]]  # css, js, images, etc.
    meta_data: Dict[str, Any]
    text_content: str
    error: Optional[str] = None

@dataclass
class SiteCrawlSummary:
    """Summary of entire site crawl"""
    total_pages: int
    total_links: int
    total_resources: int
    unique_domains: List[str]
    crawl_time: float
    errors: List[str]
    pages: List[CrawlResult]

# --- Helper Functions ---

def _normalize_url(url: str, base_url: str) -> str:
    """Normalize and resolve relative URLs"""
    if not url:
        return ""
    
    # Handle absolute URLs
    if url.startswith(('http://', 'https://')):
        return url
    
    # Handle protocol-relative URLs
    if url.startswith('//'):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}:{url}"
    
    # Handle relative URLs
    return urljoin(base_url, url)

def _is_valid_url(url: str) -> bool:
    """Check if URL is valid and crawlable"""
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc]) and parsed.scheme in ['http', 'https']
    except:
        return False

def _should_crawl_url(url: str, base_domain: str, visited: set, max_pages: int) -> bool:
    """Determine if URL should be crawled"""
    if not url or url in visited:
        return False
    
    if len(visited) >= max_pages:
        return False
    
    try:
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_domain)
        
        # Only crawl same domain
        return parsed_url.netloc == parsed_base.netloc
    except:
        return False


async def _extract_resources_playwright(page) -> Dict[str, List[str]]:
    """Extract resources using Playwright"""
    resources = defaultdict(list)
    
    try:
        # CSS files
        css_links = await page.query_selector_all("link[rel='stylesheet']")
        for link in css_links:
            href = await link.get_attribute('href')
            if href:
                resources['css'].append(href)
        
        # JavaScript files
        js_scripts = await page.query_selector_all("script[src]")
        for script in js_scripts:
            src = await script.get_attribute('src')
            if src:
                resources['js'].append(src)
        
        # Images
        images = await page.query_selector_all("img[src]")
        for img in images:
            src = await img.get_attribute('src')
            if src:
                resources['images'].append(src)
        
        # Other resources
        media = await page.query_selector_all("video[src], audio[src]")
        for item in media:
            src = await item.get_attribute('src')
            if src:
                resources['media'].append(src)
                
    except Exception as e:
        print(f"Error extracting resources: {e}")
    
    return dict(resources)


async def _extract_links_playwright(page, base_url: str) -> List[str]:
    """Extract all links using Playwright"""
    links = []
    try:
        link_elements = await page.query_selector_all("a[href]")
        for link in link_elements:
            href = await link.get_attribute('href')
            if href:
                normalized = _normalize_url(href, base_url)
                if _is_valid_url(normalized):
                    links.append(normalized)
    except Exception as e:
        print(f"Error extracting links: {e}")
    
    return list(set(links))  # Remove duplicates


# --- Speed Audit Helper Functions ---

async def _run_lighthouse(url: str, categories: str = "performance") -> Dict[str, Any]:
    """Run Lighthouse audit and return results"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Run Lighthouse CLI
        cmd = [
            'lighthouse',
            url,
            '--output=json',
            f'--output-path={temp_path}',
            f'--only-categories={categories}',
            '--chrome-flags=--headless',
            '--quiet'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            return {"error": f"Lighthouse failed: {result.stderr}"}
        
        # Read the results
        with open(temp_path, 'r') as f:
            lighthouse_data = json.load(f)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        return lighthouse_data
        
    except subprocess.TimeoutExpired:
        return {"error": "Lighthouse audit timed out"}
    except Exception as e:
        return {"error": f"Lighthouse error: {str(e)}"}


def _measure_fcp_lcp(lighthouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract First Contentful Paint (FCP) and Largest Contentful Paint (LCP) metrics"""
    try:
        audits = lighthouse_data.get('audits', {})
        
        # First Contentful Paint
        fcp_audit = audits.get('first-contentful-paint', {})
        fcp_value = fcp_audit.get('numericValue', 0) / 1000  # Convert to seconds
        fcp_score = fcp_audit.get('score', 0)
        
        # Largest Contentful Paint
        lcp_audit = audits.get('largest-contentful-paint', {})
        lcp_value = lcp_audit.get('numericValue', 0) / 1000  # Convert to seconds
        lcp_score = lcp_audit.get('score', 0)
        
        return {
            "first_contentful_paint": {
                "value_seconds": round(fcp_value, 2),
                "score": fcp_score,
                "rating": _get_metric_rating(fcp_score)
            },
            "largest_contentful_paint": {
                "value_seconds": round(lcp_value, 2),
                "score": lcp_score,
                "rating": _get_metric_rating(lcp_score)
            }
        }
    except Exception as e:
        return {"error": f"Failed to extract FCP/LCP metrics: {str(e)}"}


def _measure_tti(lighthouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Time to Interactive (TTI) metric"""
    try:
        audits = lighthouse_data.get('audits', {})
        
        # Time to Interactive
        tti_audit = audits.get('interactive', {})
        tti_value = tti_audit.get('numericValue', 0) / 1000  # Convert to seconds
        tti_score = tti_audit.get('score', 0)
        
        return {
            "time_to_interactive": {
                "value_seconds": round(tti_value, 2),
                "score": tti_score,
                "rating": _get_metric_rating(tti_score)
            }
        }
    except Exception as e:
        return {"error": f"Failed to extract TTI metric: {str(e)}"}


def _measure_total_load_time(lighthouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract total page load time metrics"""
    try:
        audits = lighthouse_data.get('audits', {})
        
        # Speed Index
        speed_index_audit = audits.get('speed-index', {})
        speed_index_value = speed_index_audit.get('numericValue', 0) / 1000
        speed_index_score = speed_index_audit.get('score', 0)
        
        # Total Blocking Time
        tbt_audit = audits.get('total-blocking-time', {})
        tbt_value = tbt_audit.get('numericValue', 0)
        tbt_score = tbt_audit.get('score', 0)
        
        # Cumulative Layout Shift
        cls_audit = audits.get('cumulative-layout-shift', {})
        cls_value = cls_audit.get('numericValue', 0)
        cls_score = cls_audit.get('score', 0)
        
        return {
            "speed_index": {
                "value_seconds": round(speed_index_value, 2),
                "score": speed_index_score,
                "rating": _get_metric_rating(speed_index_score)
            },
            "total_blocking_time": {
                "value_ms": round(tbt_value, 2),
                "score": tbt_score,
                "rating": _get_metric_rating(tbt_score)
            },
            "cumulative_layout_shift": {
                "value": round(cls_value, 3),
                "score": cls_score,
                "rating": _get_metric_rating(cls_score)
            }
        }
    except Exception as e:
        return {"error": f"Failed to extract load time metrics: {str(e)}"}


def _get_metric_rating(score: float) -> str:
    """Convert Lighthouse score to rating"""
    if score >= 0.9:
        return "good"
    elif score >= 0.5:
        return "needs_improvement"
    else:
        return "poor"


# --- Schema Audit Helper Functions ---

async def _fetch_jsonld(page) -> List[Dict[str, Any]]:
    """Extract JSON-LD structured data from the page"""
    jsonld_data = []
    
    try:
        # Find all script tags with type="application/ld+json"
        jsonld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
        
        for script in jsonld_scripts:
            try:
                content = await script.inner_text()
                if content.strip():
                    # Parse JSON-LD content
                    parsed_data = json.loads(content)
                    jsonld_data.append({
                        "type": "json-ld",
                        "data": parsed_data,
                        "raw": content.strip()
                    })
            except json.JSONDecodeError as e:
                jsonld_data.append({
                    "type": "json-ld",
                    "error": f"Invalid JSON-LD: {str(e)}",
                    "raw": content.strip() if 'content' in locals() else ""
                })
            except Exception as e:
                jsonld_data.append({
                    "type": "json-ld",
                    "error": f"Error extracting JSON-LD: {str(e)}",
                    "raw": ""
                })
                
    except Exception as e:
        print(f"Error finding JSON-LD scripts: {e}")
    
    return jsonld_data


async def _fetch_microdata(page) -> List[Dict[str, Any]]:
    """Extract Microdata structured data from the page"""
    microdata_items = []
    
    try:
        # Find all elements with itemscope attribute
        itemscope_elements = await page.query_selector_all('[itemscope]')
        
        for element in itemscope_elements:
            try:
                microdata_item = {
                    "type": "microdata",
                    "itemtype": await element.get_attribute('itemtype') or "",
                    "properties": {}
                }
                
                # Find all itemprop elements within this itemscope
                itemprop_elements = await element.query_selector_all('[itemprop]')
                
                for prop_element in itemprop_elements:
                    prop_name = await prop_element.get_attribute('itemprop')
                    
                    # Get the property value based on element type
                    tag_name = await prop_element.evaluate('el => el.tagName.toLowerCase()')
                    
                    if tag_name in ['meta']:
                        prop_value = await prop_element.get_attribute('content') or ""
                    elif tag_name in ['img', 'audio', 'video', 'source', 'embed']:
                        prop_value = await prop_element.get_attribute('src') or ""
                    elif tag_name in ['a', 'link', 'area']:
                        prop_value = await prop_element.get_attribute('href') or ""
                    elif tag_name in ['time']:
                        prop_value = await prop_element.get_attribute('datetime') or await prop_element.inner_text()
                    else:
                        prop_value = await prop_element.inner_text()
                    
                    if prop_name:
                        if prop_name in microdata_item["properties"]:
                            # Handle multiple values for the same property
                            if not isinstance(microdata_item["properties"][prop_name], list):
                                microdata_item["properties"][prop_name] = [microdata_item["properties"][prop_name]]
                            microdata_item["properties"][prop_name].append(prop_value.strip())
                        else:
                            microdata_item["properties"][prop_name] = prop_value.strip()
                
                if microdata_item["properties"]:  # Only add if it has properties
                    microdata_items.append(microdata_item)
                    
            except Exception as e:
                microdata_items.append({
                    "type": "microdata",
                    "error": f"Error extracting microdata item: {str(e)}"
                })
                
    except Exception as e:
        print(f"Error finding microdata elements: {e}")
    
    return microdata_items


async def _fetch_rdfa(page) -> List[Dict[str, Any]]:
    """Extract RDFa structured data from the page"""
    rdfa_items = []
    
    try:
        # Find all elements with RDFa attributes
        rdfa_selectors = [
            '[typeof]',      # RDFa 1.1
            '[about]',       # RDFa 1.1
            '[property]',    # RDFa 1.1
            '[resource]',    # RDFa 1.1
            '[vocab]',       # RDFa 1.1
            '[prefix]'       # RDFa 1.1
        ]
        
        for selector in rdfa_selectors:
            elements = await page.query_selector_all(selector)
            
            for element in elements:
                try:
                    rdfa_item = {
                        "type": "rdfa",
                        "attributes": {},
                        "content": await element.inner_text()
                    }
                    
                    # Extract RDFa attributes
                    rdfa_attrs = ['typeof', 'about', 'property', 'resource', 'vocab', 'prefix', 'content', 'datatype', 'rel', 'rev']
                    
                    for attr in rdfa_attrs:
                        value = await element.get_attribute(attr)
                        if value:
                            rdfa_item["attributes"][attr] = value
                    
                    # Only add if it has RDFa attributes
                    if rdfa_item["attributes"]:
                        # Check if we already have this item (avoid duplicates)
                        duplicate = False
                        for existing_item in rdfa_items:
                            if (existing_item.get("attributes") == rdfa_item["attributes"] and 
                                existing_item.get("content") == rdfa_item["content"]):
                                duplicate = True
                                break
                        
                        if not duplicate:
                            rdfa_items.append(rdfa_item)
                        
                except Exception as e:
                    rdfa_items.append({
                        "type": "rdfa",
                        "error": f"Error extracting RDFa item: {str(e)}"
                    })
                    
    except Exception as e:
        print(f"Error finding RDFa elements: {e}")
    
    return rdfa_items


def _validate_schema_data(schema_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and analyze extracted schema data"""
    validation_results = {
        "total_items": len(schema_data),
        "by_type": {
            "json-ld": 0,
            "microdata": 0,
            "rdfa": 0
        },
        "errors": [],
        "warnings": [],
        "schema_types": set(),
        "recommendations": []
    }
    
    for item in schema_data:
        item_type = item.get("type", "unknown")
        validation_results["by_type"][item_type] = validation_results["by_type"].get(item_type, 0) + 1
        
        # Check for errors
        if "error" in item:
            validation_results["errors"].append(item["error"])
            continue
        
        # Extract schema types for JSON-LD
        if item_type == "json-ld" and "data" in item:
            data = item["data"]
            if isinstance(data, dict):
                if "@type" in data:
                    schema_type = data["@type"]
                    if isinstance(schema_type, list):
                        validation_results["schema_types"].update(schema_type)
                    else:
                        validation_results["schema_types"].add(schema_type)
            elif isinstance(data, list):
                for subitem in data:
                    if isinstance(subitem, dict) and "@type" in subitem:
                        schema_type = subitem["@type"]
                        if isinstance(schema_type, list):
                            validation_results["schema_types"].update(schema_type)
                        else:
                            validation_results["schema_types"].add(schema_type)
        
        # Extract schema types for Microdata
        elif item_type == "microdata" and "itemtype" in item:
            itemtype = item["itemtype"]
            if itemtype:
                # Extract schema type from URL (e.g., "https://schema.org/Article" -> "Article")
                if "/" in itemtype:
                    schema_type = itemtype.split("/")[-1]
                    validation_results["schema_types"].add(schema_type)
        
        # Extract schema types for RDFa
        elif item_type == "rdfa" and "attributes" in item:
            typeof = item["attributes"].get("typeof")
            if typeof:
                validation_results["schema_types"].add(typeof)
    
    # Convert set to list for JSON serialization
    validation_results["schema_types"] = list(validation_results["schema_types"])
    
    # Generate recommendations
    if validation_results["total_items"] == 0:
        validation_results["recommendations"].append("No structured data found. Consider adding schema markup to improve SEO.")
    
    if validation_results["by_type"]["json-ld"] == 0:
        validation_results["recommendations"].append("Consider using JSON-LD format as it's Google's preferred structured data format.")
    
    if len(validation_results["errors"]) > 0:
        validation_results["recommendations"].append("Fix JSON-LD parsing errors to ensure search engines can read your structured data.")
    
    if len(validation_results["schema_types"]) > 10:
        validation_results["warnings"].append("Large number of different schema types detected. Ensure they are all necessary.")
    
    return validation_results


# --- External Links Audit Helper Functions ---

async def _fetch_all_links(page, base_url: str) -> Dict[str, List[str]]:
    """Extract all links from the page, categorized as internal or external"""
    links_data = {
        "internal_links": [],
        "external_links": [],
        "email_links": [],
        "tel_links": [],
        "other_links": []
    }
    
    try:
        # Extract base domain for comparison
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc.lower()
        
        # Find all link elements
        link_elements = await page.query_selector_all("a[href]")
        
        for link in link_elements:
            try:
                href = await link.get_attribute('href')
                if not href:
                    continue
                
                # Clean and normalize the URL
                href = href.strip()
                
                # Skip javascript: and data: links
                if href.startswith(('javascript:', 'data:', '#')):
                    links_data["other_links"].append(href)
                    continue
                
                # Handle email links
                if href.startswith('mailto:'):
                    links_data["email_links"].append(href)
                    continue
                
                # Handle telephone links
                if href.startswith('tel:'):
                    links_data["tel_links"].append(href)
                    continue
                
                # Normalize relative URLs
                if href.startswith(('http://', 'https://')):
                    full_url = href
                elif href.startswith('//'):
                    # Protocol-relative URL
                    full_url = f"{base_parsed.scheme}:{href}"
                else:
                    # Relative URL
                    full_url = urljoin(base_url, href)
                
                # Parse the normalized URL
                parsed_url = urlparse(full_url)
                if not parsed_url.netloc:
                    links_data["other_links"].append(href)
                    continue
                
                # Categorize as internal or external
                link_domain = parsed_url.netloc.lower()
                if link_domain == base_domain or link_domain.endswith(f'.{base_domain}'):
                    links_data["internal_links"].append(full_url)
                else:
                    links_data["external_links"].append(full_url)
                    
            except Exception as e:
                print(f"Error processing link {href}: {e}")
                links_data["other_links"].append(href if 'href' in locals() else "unknown")
    
    except Exception as e:
        print(f"Error extracting links: {e}")
    
    # Remove duplicates from each category
    for category in links_data:
        links_data[category] = list(set(links_data[category]))
    
    return links_data


async def _check_link_status(url: str, timeout: int = 10, max_redirects: int = 5) -> Dict[str, Any]:
    """Check the HTTP status of a single link"""
    try:
        if not REQUESTS_AVAILABLE:
            return {
                "url": url,
                "status": "unknown",
                "error": "requests library not available"
            }
        
        # Configure session with reasonable defaults
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WebAuditBot/1.0; +https://example.com/bot)'
        })
        
        # Make the request
        response = session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            stream=False,  # Don't download the full content
            verify=True    # Verify SSL certificates
        )
        
        return {
            "url": url,
            "status_code": response.status_code,
            "status": "working" if response.status_code < 400 else "broken",
            "final_url": response.url if response.url != url else None,
            "response_time": response.elapsed.total_seconds(),
            "content_type": response.headers.get('content-type', ''),
            "redirect_count": len(response.history)
        }
        
    except requests.exceptions.Timeout:
        return {
            "url": url,
            "status": "timeout",
            "error": "Request timed out",
            "status_code": 0
        }
    except requests.exceptions.ConnectionError:
        return {
            "url": url,
            "status": "connection_error",
            "error": "Could not connect to the server",
            "status_code": 0
        }
    except requests.exceptions.SSLError:
        return {
            "url": url,
            "status": "ssl_error",
            "error": "SSL certificate error",
            "status_code": 0
        }
    except requests.exceptions.TooManyRedirects:
        return {
            "url": url,
            "status": "too_many_redirects",
            "error": "Too many redirects",
            "status_code": 0
        }
    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "status": "error",
            "error": f"Request failed: {str(e)}",
            "status_code": 0
        }
    except Exception as e:
        return {
            "url": url,
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "status_code": 0
        }


def _analyze_link_results(link_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze link checking results and provide summary statistics"""
    analysis = {
        "total_checked": len(link_results),
        "working_links": 0,
        "broken_links": 0,
        "timeout_links": 0,
        "error_links": 0,
        "redirected_links": 0,
        "status_code_breakdown": {},
        "broken_link_details": [],
        "recommendations": []
    }
    
    for result in link_results:
        status = result.get("status", "unknown")
        status_code = result.get("status_code", 0)
        
        # Count by status
        if status == "working":
            analysis["working_links"] += 1
        elif status == "broken":
            analysis["broken_links"] += 1
            analysis["broken_link_details"].append({
                "url": result["url"],
                "status_code": status_code,
                "error": result.get("error", "")
            })
        elif status == "timeout":
            analysis["timeout_links"] += 1
        else:
            analysis["error_links"] += 1
        
        # Count redirects
        if result.get("redirect_count", 0) > 0:
            analysis["redirected_links"] += 1
        
        # Status code breakdown
        if status_code > 0:
            analysis["status_code_breakdown"][str(status_code)] = analysis["status_code_breakdown"].get(str(status_code), 0) + 1
    
    # Generate recommendations
    if analysis["broken_links"] > 0:
        analysis["recommendations"].append(f"Fix {analysis['broken_links']} broken external links to improve user experience and SEO.")
    
    if analysis["timeout_links"] > 3:
        analysis["recommendations"].append("Several links are timing out. Consider checking if these external sites are reliable.")
    
    if analysis["redirected_links"] > analysis["total_checked"] * 0.3:
        analysis["recommendations"].append("Many external links are redirecting. Consider updating to point directly to final destinations.")
    
    if analysis["working_links"] == analysis["total_checked"]:
        analysis["recommendations"].append("All external links are working correctly!")
    
    return analysis


# --- Accessibility Audit Helper Functions ---

async def _check_alt_text(page) -> Dict[str, Any]:
    """Check all images for proper alt text implementation"""
    alt_text_results = {
        "total_images": 0,
        "images_with_alt": 0,
        "images_without_alt": 0,
        "images_with_empty_alt": 0,
        "decorative_images": 0,
        "violations": [],
        "passes": []
    }
    
    try:
        # Find all images
        images = await page.query_selector_all('img')
        alt_text_results["total_images"] = len(images)
        
        for i, img in enumerate(images):
            src = await img.get_attribute('src') or 'unknown'
            alt = await img.get_attribute('alt')
            
            if alt is None:
                alt_text_results["images_without_alt"] += 1
                alt_text_results["violations"].append({
                    "type": "missing_alt",
                    "element": f"img[{i}]",
                    "src": src,
                    "description": "Image missing alt attribute"
                })
            elif alt.strip() == "":
                alt_text_results["decorative_images"] += 1
                alt_text_results["passes"].append({
                    "type": "decorative",
                    "element": f"img[{i}]",
                    "src": src,
                    "description": "Decorative image with empty alt text"
                })
            else:
                alt_text_results["images_with_alt"] += 1
                # Check for poor alt text patterns
                alt_lower = alt.lower()
                if any(phrase in alt_lower for phrase in ['image of', 'picture of', 'photo of', 'graphic of']):
                    alt_text_results["violations"].append({
                        "type": "redundant_alt",
                        "element": f"img[{i}]",
                        "src": src,
                        "alt": alt,
                        "description": "Alt text contains redundant phrases"
                    })
                elif len(alt) > 125:
                    alt_text_results["violations"].append({
                        "type": "long_alt",
                        "element": f"img[{i}]",
                        "src": src,
                        "alt": alt[:50] + "...",
                        "description": "Alt text is too long (over 125 characters)"
                    })
                else:
                    alt_text_results["passes"].append({
                        "type": "good_alt",
                        "element": f"img[{i}]",
                        "src": src,
                        "alt": alt[:50] + ("..." if len(alt) > 50 else ""),
                        "description": "Image has appropriate alt text"
                    })
                    
    except Exception as e:
        alt_text_results["violations"].append({
            "type": "error",
            "description": f"Error checking alt text: {str(e)}"
        })
    
    return alt_text_results


async def _check_contrast(page) -> Dict[str, Any]:
    """Check color contrast using JavaScript evaluation"""
    try:
        # Inject our accessibility checker
        await page.add_script_tag(content=AXE_CORE_JS)
        
        # Run contrast checks
        contrast_results = await page.evaluate('window.axeCore.runAccessibilityChecks()')
        
        # Filter for contrast-related results
        contrast_violations = [v for v in contrast_results.get('violations', []) if v.get('id') == 'color-contrast']
        contrast_passes = [p for p in contrast_results.get('passes', []) if p.get('id') == 'color-contrast']
        
        return {
            "total_elements_checked": len(contrast_violations) + len(contrast_passes),
            "contrast_violations": len(contrast_violations),
            "contrast_passes": len(contrast_passes),
            "violations": contrast_violations,
            "passes": contrast_passes[:10]  # Limit passes to first 10 for brevity
        }
        
    except Exception as e:
        return {
            "error": f"Error checking contrast: {str(e)}",
            "total_elements_checked": 0,
            "contrast_violations": 0,
            "contrast_passes": 0,
            "violations": [],
            "passes": []
        }


async def _check_aria_labels(page) -> Dict[str, Any]:
    """Check ARIA labels and accessibility attributes"""
    aria_results = {
        "total_interactive_elements": 0,
        "elements_with_labels": 0,
        "elements_without_labels": 0,
        "violations": [],
        "passes": [],
        "warnings": []
    }
    
    try:
        # Check form elements
        form_elements = await page.query_selector_all('input, textarea, select, button')
        
        for i, element in enumerate(form_elements):
            element_type = await element.evaluate('el => el.type || el.tagName.toLowerCase()')
            element_id = await element.get_attribute('id') or f'no-id-{i}'
            
            aria_results["total_interactive_elements"] += 1
            
            # Check for various labeling methods
            aria_label = await element.get_attribute('aria-label')
            aria_labelledby = await element.get_attribute('aria-labelledby')
            aria_describedby = await element.get_attribute('aria-describedby')
            
            # Check for associated label
            label_element = None
            if element_id != f'no-id-{i}':
                try:
                    label_element = await page.query_selector(f'label[for="{element_id}"]')
                except:
                    pass
            
            # Check for title attribute (not ideal but acceptable)
            title = await element.get_attribute('title')
            
            # Determine if element is properly labeled
            is_labeled = any([aria_label, aria_labelledby, label_element, title])
            
            if not is_labeled:
                aria_results["elements_without_labels"] += 1
                aria_results["violations"].append({
                    "type": "missing_label",
                    "element": f"{element_type}[{i}]",
                    "element_id": element_id,
                    "description": f"Interactive {element_type} element lacks accessible name"
                })
            else:
                aria_results["elements_with_labels"] += 1
                label_method = "aria-label" if aria_label else \
                             "aria-labelledby" if aria_labelledby else \
                             "label" if label_element else \
                             "title" if title else "unknown"
                
                aria_results["passes"].append({
                    "type": "has_label",
                    "element": f"{element_type}[{i}]",
                    "element_id": element_id,
                    "label_method": label_method,
                    "description": f"Element properly labeled via {label_method}"
                })
                
                # Warning for title-only labeling
                if title and not any([aria_label, aria_labelledby, label_element]):
                    aria_results["warnings"].append({
                        "type": "title_only",
                        "element": f"{element_type}[{i}]",
                        "description": "Element uses title attribute for labeling (not ideal)"
                    })
        
        # Check for proper heading structure
        headings = await page.query_selector_all('h1, h2, h3, h4, h5, h6')
        
        if len(headings) == 0:
            aria_results["violations"].append({
                "type": "no_headings",
                "description": "Page has no heading elements"
            })
        else:
            h1_count = len(await page.query_selector_all('h1'))
            if h1_count == 0:
                aria_results["violations"].append({
                    "type": "no_h1",
                    "description": "Page should have exactly one h1 element"
                })
            elif h1_count > 1:
                aria_results["violations"].append({
                    "type": "multiple_h1",
                    "description": f"Page has {h1_count} h1 elements, should have exactly one"
                })
            else:
                aria_results["passes"].append({
                    "type": "h1_structure",
                    "description": "Page has proper h1 structure"
                })
        
        # Check for skip links
        skip_links = await page.query_selector_all('a[href^="#"]')
        skip_link_found = False
        
        for link in skip_links:
            text = await link.inner_text()
            if any(phrase in text.lower() for phrase in ['skip to', 'skip nav', 'skip content']):
                skip_link_found = True
                break
        
        if skip_link_found:
            aria_results["passes"].append({
                "type": "skip_link",
                "description": "Page includes skip navigation link"
            })
        else:
            aria_results["warnings"].append({
                "type": "no_skip_link",
                "description": "Consider adding skip navigation link for keyboard users"
            })
                
    except Exception as e:
        aria_results["violations"].append({
            "type": "error",
            "description": f"Error checking ARIA labels: {str(e)}"
        })
    
    return aria_results


def _analyze_accessibility_results(alt_results: Dict, contrast_results: Dict, aria_results: Dict) -> Dict[str, Any]:
    """Analyze all accessibility check results and provide summary"""
    total_violations = (
        len(alt_results.get('violations', [])) + 
        len(contrast_results.get('violations', [])) + 
        len(aria_results.get('violations', []))
    )
    
    total_passes = (
        len(alt_results.get('passes', [])) + 
        len(contrast_results.get('passes', [])) + 
        len(aria_results.get('passes', []))
    )
    
    # Calculate accessibility score (0-100)
    if total_violations + total_passes == 0:
        score = 0
    else:
        score = int((total_passes / (total_violations + total_passes)) * 100)
    
    # Categorize violations by severity
    critical_violations = 0
    serious_violations = 0
    moderate_violations = 0
    minor_violations = 0
    
    all_violations = (
        alt_results.get('violations', []) + 
        contrast_results.get('violations', []) + 
        aria_results.get('violations', [])
    )
    
    for violation in all_violations:
        impact = violation.get('impact', 'minor')
        if impact == 'critical':
            critical_violations += 1
        elif impact == 'serious':
            serious_violations += 1
        elif impact == 'moderate':
            moderate_violations += 1
        else:
            minor_violations += 1
    
    # Generate recommendations
    recommendations = []
    
    if alt_results.get('images_without_alt', 0) > 0:
        recommendations.append(f"Add alt attributes to {alt_results['images_without_alt']} images without alt text")
    
    if contrast_results.get('contrast_violations', 0) > 0:
        recommendations.append(f"Fix {contrast_results['contrast_violations']} color contrast issues")
    
    if aria_results.get('elements_without_labels', 0) > 0:
        recommendations.append(f"Add accessible labels to {aria_results['elements_without_labels']} interactive elements")
    
    if critical_violations > 0:
        recommendations.append("Address critical accessibility violations first - they prevent users from accessing content")
    
    if score >= 90:
        recommendations.append("Excellent accessibility! Consider manual testing with screen readers for final validation")
    elif score >= 70:
        recommendations.append("Good accessibility foundation. Focus on fixing remaining violations")
    elif score >= 50:
        recommendations.append("Accessibility needs improvement. Prioritize critical and serious violations")
    else:
        recommendations.append("Significant accessibility barriers present. Comprehensive remediation needed")
    
    return {
        "accessibility_score": score,
        "total_violations": total_violations,
        "total_passes": total_passes,
        "violations_by_severity": {
            "critical": critical_violations,
            "serious": serious_violations,
            "moderate": moderate_violations,
            "minor": minor_violations
        },
        "recommendations": recommendations
    }


# --- Robots.txt Audit Helper Functions ---

async def _fetch_robots_txt(base_url: str, timeout: int = 10) -> Dict[str, Any]:
    """Fetch the robots.txt file from the server"""
    try:
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": "requests library not available",
                "content": None,
                "url": None
            }
        
        # Construct robots.txt URL
        parsed_url = urlparse(base_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        # Configure session
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WebAuditBot/1.0; +https://example.com/bot)'
        })
        
        # Fetch robots.txt
        response = session.get(robots_url, timeout=timeout, verify=True)
        
        return {
            "success": True,
            "status_code": response.status_code,
            "content": response.text if response.status_code == 200 else None,
            "url": robots_url,
            "response_time": response.elapsed.total_seconds(),
            "content_type": response.headers.get('content-type', ''),
            "content_length": len(response.text) if response.status_code == 200 else 0
        }
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timed out",
            "content": None,
            "url": robots_url if 'robots_url' in locals() else None,
            "status_code": 0
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Could not connect to the server",
            "content": None,
            "url": robots_url if 'robots_url' in locals() else None,
            "status_code": 0
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}",
            "content": None,
            "url": robots_url if 'robots_url' in locals() else None,
            "status_code": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "content": None,
            "url": robots_url if 'robots_url' in locals() else None,
            "status_code": 0
        }


def _parse_robots_txt(content: str) -> Dict[str, Any]:
    """Parse the robots.txt file content and extract rules"""
    if not content:
        return {
            "user_agents": {},
            "sitemaps": [],
            "crawl_delay": {},
            "host": None,
            "total_rules": 0,
            "warnings": [],
            "errors": []
        }
    
    parsed_data = {
        "user_agents": {},
        "sitemaps": [],
        "crawl_delay": {},
        "host": None,
        "total_rules": 0,
        "warnings": [],
        "errors": []
    }
    
    current_user_agent = None
    lines = content.strip().split('\n')
    
    for line_num, line in enumerate(lines, 1):
        # Remove comments and whitespace
        line = line.split('#')[0].strip()
        if not line:
            continue
            
        try:
            # Parse line into directive and value
            if ':' not in line:
                parsed_data["errors"].append({
                    "line": line_num,
                    "content": line,
                    "error": "Invalid syntax: missing colon"
                })
                continue
                
            directive, value = line.split(':', 1)
            directive = directive.strip().lower()
            value = value.strip()
            
            if not value and directive not in ['user-agent']:
                parsed_data["warnings"].append({
                    "line": line_num,
                    "content": line,
                    "warning": "Empty value for directive"
                })
                continue
            
            # Process different directives
            if directive == 'user-agent':
                current_user_agent = value if value else '*'
                if current_user_agent not in parsed_data["user_agents"]:
                    parsed_data["user_agents"][current_user_agent] = {
                        "allow": [],
                        "disallow": [],
                        "crawl_delay": None
                    }
                parsed_data["total_rules"] += 1
                
            elif directive in ['allow', 'disallow']:
                if current_user_agent is None:
                    parsed_data["errors"].append({
                        "line": line_num,
                        "content": line,
                        "error": f"{directive.capitalize()} directive without User-agent"
                    })
                    continue
                    
                parsed_data["user_agents"][current_user_agent][directive].append(value)
                parsed_data["total_rules"] += 1
                
            elif directive == 'crawl-delay':
                if current_user_agent is None:
                    parsed_data["errors"].append({
                        "line": line_num,
                        "content": line,
                        "error": "Crawl-delay directive without User-agent"
                    })
                    continue
                    
                try:
                    delay = float(value)
                    parsed_data["user_agents"][current_user_agent]["crawl_delay"] = delay
                    parsed_data["crawl_delay"][current_user_agent] = delay
                    parsed_data["total_rules"] += 1
                except ValueError:
                    parsed_data["errors"].append({
                        "line": line_num,
                        "content": line,
                        "error": "Invalid crawl-delay value: must be a number"
                    })
                    
            elif directive == 'sitemap':
                if not value.startswith(('http://', 'https://')):
                    parsed_data["warnings"].append({
                        "line": line_num,
                        "content": line,
                        "warning": "Sitemap URL should be absolute (include http/https)"
                    })
                parsed_data["sitemaps"].append(value)
                parsed_data["total_rules"] += 1
                
            elif directive == 'host':
                parsed_data["host"] = value
                parsed_data["total_rules"] += 1
                
            else:
                parsed_data["warnings"].append({
                    "line": line_num,
                    "content": line,
                    "warning": f"Unknown directive: {directive}"
                })
                
        except Exception as e:
            parsed_data["errors"].append({
                "line": line_num,
                "content": line,
                "error": f"Parse error: {str(e)}"
            })
    
    return parsed_data


def _analyze_robots_txt(parsed_data: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    """Analyze parsed robots.txt data and provide recommendations"""
    analysis = {
        "summary": {
            "total_user_agents": len(parsed_data["user_agents"]),
            "total_sitemaps": len(parsed_data["sitemaps"]),
            "has_crawl_delays": len(parsed_data["crawl_delay"]) > 0,
            "has_errors": len(parsed_data["errors"]) > 0,
            "has_warnings": len(parsed_data["warnings"]) > 0,
            "total_rules": parsed_data["total_rules"]
        },
        "recommendations": [],
        "seo_impact": [],
        "crawlability": {
            "completely_blocked": False,
            "partially_blocked": False,
            "major_sections_blocked": [],
            "allows_crawling": True
        }
    }
    
    # Check for common issues
    user_agents = parsed_data["user_agents"]
    
    # Check if site is completely blocked
    if '*' in user_agents:
        wildcard_rules = user_agents['*']
        if '/' in wildcard_rules.get('disallow', []) and not wildcard_rules.get('allow', []):
            analysis["crawlability"]["completely_blocked"] = True
            analysis["seo_impact"].append("Site completely blocks all crawlers - will hurt SEO")
            analysis["recommendations"].append("Consider allowing at least major search engines to crawl your site")
    
    # Check for important sections being blocked
    important_paths = ['/admin', '/wp-admin', '/private', '/api', '/login']
    blocked_important = []
    
    for ua, rules in user_agents.items():
        for disallow in rules.get('disallow', []):
            if any(path in disallow.lower() for path in ['/admin', '/wp-admin', '/private']):
                blocked_important.append(disallow)
    
    if blocked_important:
        analysis["recommendations"].append("Good: Important admin/private sections are blocked from crawlers")
    
    # Check for sitemap
    if not parsed_data["sitemaps"]:
        analysis["recommendations"].append("Consider adding sitemap URL(s) to help search engines discover content")
        analysis["seo_impact"].append("No sitemap specified - may slow content discovery")
    else:
        # Validate sitemap URLs
        valid_sitemaps = 0
        for sitemap in parsed_data["sitemaps"]:
            if sitemap.startswith(('http://', 'https://')):
                valid_sitemaps += 1
        
        if valid_sitemaps == len(parsed_data["sitemaps"]):
            analysis["recommendations"].append("Good: All sitemap URLs are properly formatted")
        else:
            analysis["recommendations"].append("Some sitemap URLs may be invalid - ensure they are absolute URLs")
    
    # Check crawl delays
    if parsed_data["crawl_delay"]:
        high_delays = {ua: delay for ua, delay in parsed_data["crawl_delay"].items() if delay > 10}
        if high_delays:
            analysis["seo_impact"].append(f"High crawl delays detected: {high_delays}")
            analysis["recommendations"].append("Very high crawl delays may significantly slow indexing")
    
    # Check for errors and warnings
    if parsed_data["errors"]:
        analysis["recommendations"].append(f"Fix {len(parsed_data['errors'])} syntax errors in robots.txt")
        analysis["seo_impact"].append("Syntax errors may cause rules to be ignored")
    
    if parsed_data["warnings"]:
        analysis["recommendations"].append(f"Review {len(parsed_data['warnings'])} warnings in robots.txt")
    
    # Check for specific search engine rules
    search_engines = ['googlebot', 'bingbot', 'slurp', 'duckduckbot', 'facebookexternalhit']
    has_specific_rules = any(ua.lower() in [se.lower() for se in search_engines] for ua in user_agents.keys())
    
    if has_specific_rules:
        analysis["recommendations"].append("Good: Specific rules for major search engines detected")
    
    # Overall crawlability assessment
    if analysis["crawlability"]["completely_blocked"]:
        analysis["crawlability"]["allows_crawling"] = False
    elif len(blocked_important) > 0:
        analysis["crawlability"]["partially_blocked"] = True
    
    return analysis


# --- HTTPS and SSL Audit Helper Functions ---

async def _check_https_status(url: str, timeout: int = 10) -> Dict[str, Any]:
    """Check HTTPS availability and HTTP to HTTPS redirection"""
    try:
        if not REQUESTS_AVAILABLE:
            return {
                "error": "requests library not available",
                "https_available": False,
                "http_redirects_to_https": False
            }
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        base_path = parsed_url.path or '/'
        
        # Configure session
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WebAuditBot/1.0; +https://example.com/bot)'
        })
        
        results = {
            "https_available": False,
            "http_redirects_to_https": False,
            "https_status_code": 0,
            "http_status_code": 0,
            "https_response_time": 0,
            "http_response_time": 0,
            "https_error": None,
            "http_error": None,
            "final_https_url": None,
            "final_http_url": None,
            "redirect_chain": []
        }
        
        # Test HTTPS URL
        https_url = f"https://{domain}{base_path}"
        try:
            https_response = session.get(https_url, timeout=timeout, allow_redirects=True)
            results["https_available"] = True
            results["https_status_code"] = https_response.status_code
            results["https_response_time"] = https_response.elapsed.total_seconds()
            results["final_https_url"] = https_response.url
            
            # Track redirect chain
            if https_response.history:
                results["redirect_chain"] = [resp.url for resp in https_response.history]
                
        except requests.exceptions.SSLError as e:
            results["https_error"] = f"SSL Error: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            results["https_error"] = f"Connection Error: {str(e)}"
        except requests.exceptions.Timeout:
            results["https_error"] = "Request timed out"
        except requests.exceptions.RequestException as e:
            results["https_error"] = f"Request failed: {str(e)}"
        
        # Test HTTP URL and check if it redirects to HTTPS
        http_url = f"http://{domain}{base_path}"
        try:
            http_response = session.get(http_url, timeout=timeout, allow_redirects=True)
            results["http_status_code"] = http_response.status_code
            results["http_response_time"] = http_response.elapsed.total_seconds()
            results["final_http_url"] = http_response.url
            
            # Check if HTTP redirects to HTTPS
            if http_response.url.startswith('https://'):
                results["http_redirects_to_https"] = True
                
        except requests.exceptions.ConnectionError as e:
            results["http_error"] = f"Connection Error: {str(e)}"
        except requests.exceptions.Timeout:
            results["http_error"] = "Request timed out"
        except requests.exceptions.RequestException as e:
            results["http_error"] = f"Request failed: {str(e)}"
        
        return results
        
    except Exception as e:
        return {
            "error": f"HTTPS check failed: {str(e)}",
            "https_available": False,
            "http_redirects_to_https": False
        }


async def _check_ssl_certificate(domain: str, port: int = 443, timeout: int = 10) -> Dict[str, Any]:
    """Check SSL certificate details and validity"""
    try:
        if not SSL_AVAILABLE:
            return {
                "error": "SSL libraries not available",
                "valid": False,
                "certificate_info": {}
            }
        
        # Remove protocol from domain if present
        if '://' in domain:
            domain = urlparse(domain).netloc
        
        # Remove port from domain if present  
        if ':' in domain:
            domain = domain.split(':')[0]
        
        results = {
            "valid": False,
            "certificate_info": {},
            "validation_errors": [],
            "warnings": [],
            "security_details": {}
        }
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect and get certificate
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                # Get certificate info
                cert_info = ssock.getpeercert()
                
                if not cert_info:
                    results["validation_errors"].append("No certificate information available")
                    return results
                
                # Parse certificate details
                results["certificate_info"] = {
                    "subject": dict(x[0] for x in cert_info.get('subject', [])),
                    "issuer": dict(x[0] for x in cert_info.get('issuer', [])),
                    "version": cert_info.get('version'),
                    "serial_number": cert_info.get('serialNumber'),
                    "not_before": cert_info.get('notBefore'),
                    "not_after": cert_info.get('notAfter'),
                    "subject_alt_names": [],
                }
                
                # Extract Subject Alternative Names
                for extension in cert_info.get('subjectAltName', []):
                    if extension[0] == 'DNS':
                        results["certificate_info"]["subject_alt_names"].append(extension[1])
                
                # Check certificate validity dates
                try:
                    not_before = datetime.strptime(cert_info['notBefore'], '%b %d %H:%M:%S %Y %Z')
                    not_after = datetime.strptime(cert_info['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    now = datetime.now()
                    
                    if now < not_before:
                        results["validation_errors"].append("Certificate is not yet valid")
                    elif now > not_after:
                        results["validation_errors"].append("Certificate has expired")
                    else:
                        results["valid"] = True
                        
                        # Check if certificate expires soon (within 30 days)
                        days_until_expiry = (not_after - now).days
                        results["certificate_info"]["days_until_expiry"] = days_until_expiry
                        
                        if days_until_expiry < 30:
                            results["warnings"].append(f"Certificate expires in {days_until_expiry} days")
                        elif days_until_expiry < 90:
                            results["warnings"].append(f"Certificate expires in {days_until_expiry} days - consider renewal planning")
                            
                except ValueError as e:
                    results["validation_errors"].append(f"Could not parse certificate dates: {str(e)}")
                
                # Get SSL/TLS protocol and cipher info
                results["security_details"] = {
                    "protocol": ssock.version(),
                    "cipher": ssock.cipher(),
                    "compression": ssock.compression(),
                }
                
                # Check for common name or SAN match
                common_name = results["certificate_info"]["subject"].get("commonName", "")
                alt_names = results["certificate_info"]["subject_alt_names"]
                
                domain_matches = False
                if common_name == domain or common_name == f"*.{domain}":
                    domain_matches = True
                elif any(alt_name == domain or alt_name == f"*.{domain}" for alt_name in alt_names):
                    domain_matches = True
                elif domain.startswith('www.') and (common_name == domain[4:] or f"*.{domain[4:]}" in alt_names):
                    domain_matches = True
                elif common_name.startswith('*.') and domain.endswith(common_name[2:]):
                    domain_matches = True
                
                if not domain_matches:
                    results["validation_errors"].append(f"Certificate domain mismatch: cert for '{common_name}', requested '{domain}'")
                
                # Check cipher strength
                cipher_info = results["security_details"].get("cipher")
                if cipher_info:
                    cipher_name, protocol, key_bits = cipher_info
                    if key_bits < 128:
                        results["warnings"].append(f"Weak cipher strength: {key_bits} bits")
                    
                    # Check for deprecated protocols
                    if protocol in ['TLSv1', 'TLSv1.1', 'SSLv2', 'SSLv3']:
                        results["warnings"].append(f"Deprecated protocol in use: {protocol}")
        
        # Final validation check
        if not results["validation_errors"]:
            results["valid"] = True
            
        return results
        
    except socket.timeout:
        return {
            "error": "Connection timed out",
            "valid": False,
            "certificate_info": {}
        }
    except socket.gaierror as e:
        return {
            "error": f"DNS resolution failed: {str(e)}",
            "valid": False,
            "certificate_info": {}
        }
    except ConnectionRefusedError:
        return {
            "error": "Connection refused - port may be closed",
            "valid": False,
            "certificate_info": {}
        }
    except ssl.SSLError as e:
        return {
            "error": f"SSL Error: {str(e)}",
            "valid": False,
            "certificate_info": {},
            "validation_errors": [str(e)]
        }
    except Exception as e:
        return {
            "error": f"Certificate check failed: {str(e)}",
            "valid": False,
            "certificate_info": {}
        }


def _analyze_https_security(https_status: Dict[str, Any], ssl_info: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze HTTPS and SSL configuration for security and best practices"""
    analysis = {
        "security_score": 0,  # 0-100
        "security_issues": [],
        "recommendations": [],
        "compliance": {
            "has_https": False,
            "forces_https": False,
            "valid_certificate": False,
            "modern_tls": False
        }
    }
    
    score = 0
    max_score = 100
    
    # Check HTTPS availability (25 points)
    if https_status.get("https_available"):
        analysis["compliance"]["has_https"] = True
        score += 25
        analysis["recommendations"].append("Good: HTTPS is available")
    else:
        analysis["security_issues"].append("HTTPS is not available")
        analysis["recommendations"].append("Critical: Enable HTTPS for secure connections")
    
    # Check HTTP to HTTPS redirect (25 points)
    if https_status.get("http_redirects_to_https"):
        analysis["compliance"]["forces_https"] = True
        score += 25
        analysis["recommendations"].append("Good: HTTP traffic is redirected to HTTPS")
    else:
        analysis["security_issues"].append("HTTP does not redirect to HTTPS")
        analysis["recommendations"].append("Important: Configure HTTP to HTTPS redirect")
    
    # Check SSL certificate validity (30 points)
    if ssl_info.get("valid"):
        analysis["compliance"]["valid_certificate"] = True
        score += 30
        analysis["recommendations"].append("Good: SSL certificate is valid")
        
        # Check expiration warnings
        cert_info = ssl_info.get("certificate_info", {})
        days_until_expiry = cert_info.get("days_until_expiry", 0)
        if days_until_expiry < 30:
            analysis["security_issues"].append(f"SSL certificate expires in {days_until_expiry} days")
        
    else:
        analysis["security_issues"].append("SSL certificate is invalid")
        analysis["recommendations"].append("Critical: Fix SSL certificate issues")
        
        # Add specific certificate errors
        for error in ssl_info.get("validation_errors", []):
            analysis["security_issues"].append(f"Certificate error: {error}")
    
    # Check TLS protocol version (20 points)
    security_details = ssl_info.get("security_details", {})
    protocol = security_details.get("protocol", "")
    
    if protocol in ['TLSv1.2', 'TLSv1.3']:
        analysis["compliance"]["modern_tls"] = True
        score += 20
        analysis["recommendations"].append(f"Good: Using modern TLS protocol ({protocol})")
    elif protocol in ['TLSv1.1', 'TLSv1']:
        analysis["security_issues"].append(f"Using deprecated TLS protocol: {protocol}")
        analysis["recommendations"].append("Update to TLS 1.2 or 1.3 for better security")
        score += 10  # Partial credit
    else:
        analysis["security_issues"].append(f"Unknown or insecure protocol: {protocol}")
        analysis["recommendations"].append("Ensure modern TLS protocol is being used")
    
    # Additional security checks
    if ssl_info.get("warnings"):
        for warning in ssl_info["warnings"]:
            analysis["security_issues"].append(f"SSL Warning: {warning}")
    
    # Calculate final score
    analysis["security_score"] = min(score, max_score)
    
    # Overall recommendations based on score
    if analysis["security_score"] >= 90:
        analysis["recommendations"].append("Excellent HTTPS security configuration!")
    elif analysis["security_score"] >= 75:
        analysis["recommendations"].append("Good HTTPS security with minor improvements needed")
    elif analysis["security_score"] >= 50:
        analysis["recommendations"].append("HTTPS security needs improvement - address critical issues")
    else:
        analysis["recommendations"].append("Poor HTTPS security - immediate attention required")
    
    return analysis


# --- Internal Linking Audit Helper Functions ---

async def _get_internal_links(page, base_url: str) -> Dict[str, Any]:
    """Extract all internal links from the page with detailed analysis"""
    try:
        # Extract base domain for comparison
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc.lower()
        base_scheme = base_parsed.scheme
        
        internal_links_data = {
            "total_internal_links": 0,
            "unique_internal_links": [],
            "internal_links_with_anchors": [],
            "relative_links": [],
            "absolute_internal_links": [],
            "anchor_links": [],
            "mailto_links": [],
            "tel_links": [],
            "link_details": [],
            "navigation_analysis": {
                "has_navigation": False,
                "navigation_links": [],
                "breadcrumb_links": [],
                "footer_links": []
            }
        }
        
        # Find all link elements
        link_elements = await page.query_selector_all("a[href]")
        
        processed_links = set()  # Track unique links
        
        for i, link in enumerate(link_elements):
            try:
                href = await link.get_attribute('href')
                if not href:
                    continue
                
                # Get link text and context
                link_text = (await link.inner_text()).strip()
                
                # Get parent element for context analysis
                parent = await link.evaluate('el => el.parentElement ? el.parentElement.tagName.toLowerCase() : null')
                classes = await link.get_attribute('class') or ''
                
                # Clean and normalize the URL
                href = href.strip()
                
                # Handle different link types
                link_detail = {
                    "href": href,
                    "text": link_text,
                    "index": i,
                    "parent_element": parent,
                    "classes": classes,
                    "type": "unknown"
                }
                
                # Skip javascript: and data: links
                if href.startswith(('javascript:', 'data:')):
                    link_detail["type"] = "javascript_data"
                    continue
                
                # Handle email links
                if href.startswith('mailto:'):
                    internal_links_data["mailto_links"].append(link_detail)
                    link_detail["type"] = "mailto"
                    continue
                
                # Handle telephone links
                if href.startswith('tel:'):
                    internal_links_data["tel_links"].append(link_detail)
                    link_detail["type"] = "tel"
                    continue
                
                # Handle anchor links (same page)
                if href.startswith('#'):
                    internal_links_data["anchor_links"].append(link_detail)
                    link_detail["type"] = "anchor"
                    link_detail["normalized_url"] = href
                    internal_links_data["link_details"].append(link_detail)
                    continue
                
                # Normalize relative URLs
                if href.startswith(('http://', 'https://')):
                    # Absolute URL
                    full_url = href
                    link_detail["type"] = "absolute"
                elif href.startswith('//'):
                    # Protocol-relative URL
                    full_url = f"{base_scheme}:{href}"
                    link_detail["type"] = "protocol_relative"
                else:
                    # Relative URL
                    full_url = urljoin(base_url, href)
                    link_detail["type"] = "relative"
                    internal_links_data["relative_links"].append(link_detail)
                
                # Parse the normalized URL
                try:
                    parsed_url = urlparse(full_url)
                    if not parsed_url.netloc:
                        continue
                    
                    link_detail["normalized_url"] = full_url
                    
                    # Check if it's internal (same domain)
                    link_domain = parsed_url.netloc.lower()
                    if link_domain == base_domain or link_domain.endswith(f'.{base_domain}') or (link_domain.startswith('www.') and link_domain[4:] == base_domain):
                        # It's an internal link
                        internal_links_data["total_internal_links"] += 1
                        
                        if full_url not in processed_links:
                            processed_links.add(full_url)
                            internal_links_data["unique_internal_links"].append(full_url)
                        
                        # Check if it has anchor
                        if '#' in full_url:
                            internal_links_data["internal_links_with_anchors"].append(link_detail)
                        
                        if link_detail["type"] == "absolute":
                            internal_links_data["absolute_internal_links"].append(link_detail)
                        
                        # Analyze navigation context
                        if parent in ['nav', 'header'] or 'nav' in classes.lower():
                            internal_links_data["navigation_analysis"]["has_navigation"] = True
                            internal_links_data["navigation_analysis"]["navigation_links"].append(link_detail)
                        elif 'breadcrumb' in classes.lower() or 'breadcrumbs' in classes.lower():
                            internal_links_data["navigation_analysis"]["breadcrumb_links"].append(link_detail)
                        elif parent == 'footer' or 'footer' in classes.lower():
                            internal_links_data["navigation_analysis"]["footer_links"].append(link_detail)
                        
                        internal_links_data["link_details"].append(link_detail)
                        
                except Exception as e:
                    print(f"Error parsing URL {href}: {e}")
                    continue
                    
            except Exception as e:
                print(f"Error processing link {i}: {e}")
                continue
        
        return internal_links_data
        
    except Exception as e:
        print(f"Error extracting internal links: {e}")
        return {
            "error": f"Failed to extract internal links: {str(e)}",
            "total_internal_links": 0,
            "unique_internal_links": [],
            "link_details": []
        }


async def _validate_internal_links(internal_links: List[str], base_url: str, timeout: int = 10, max_links: int = 100) -> Dict[str, Any]:
    """Validate internal links by checking their HTTP status"""
    try:
        if not REQUESTS_AVAILABLE:
            return {
                "error": "requests library not available",
                "validation_results": [],
                "summary": {
                    "total_checked": 0,
                    "working_links": 0,
                    "broken_links": 0,
                    "error_links": 0
                }
            }
        
        # Limit the number of links to check for performance
        links_to_check = internal_links[:max_links]
        
        # Configure session
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; WebAuditBot/1.0; +https://example.com/bot)',
            'Referer': base_url
        })
        
        validation_results = []
        working_links = 0
        broken_links = 0
        error_links = 0
        
        for i, link_url in enumerate(links_to_check):
            try:
                # Skip anchor-only links (they're on the same page)
                if link_url.startswith('#'):
                    validation_results.append({
                        "url": link_url,
                        "status": "anchor_link",
                        "status_code": 200,
                        "response_time": 0,
                        "description": "Same-page anchor link"
                    })
                    working_links += 1
                    continue
                
                # Make request to check link status
                response = session.get(
                    link_url,
                    timeout=timeout,
                    allow_redirects=True,
                    stream=True  # Don't download full content
                )
                
                result = {
                    "url": link_url,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "final_url": response.url if response.url != link_url else None,
                    "redirect_count": len(response.history),
                    "content_type": response.headers.get('content-type', ''),
                    "status": "working" if response.status_code < 400 else "broken"
                }
                
                if response.status_code < 400:
                    working_links += 1
                else:
                    broken_links += 1
                    result["description"] = f"HTTP {response.status_code} error"
                
                validation_results.append(result)
                
            except requests.exceptions.Timeout:
                error_links += 1
                validation_results.append({
                    "url": link_url,
                    "status": "timeout",
                    "status_code": 0,
                    "response_time": timeout,
                    "description": "Request timed out"
                })
                
            except requests.exceptions.ConnectionError as e:
                error_links += 1
                validation_results.append({
                    "url": link_url,
                    "status": "connection_error",
                    "status_code": 0,
                    "response_time": 0,
                    "description": f"Connection error: {str(e)}"
                })
                
            except requests.exceptions.RequestException as e:
                error_links += 1
                validation_results.append({
                    "url": link_url,
                    "status": "request_error",
                    "status_code": 0,
                    "response_time": 0,
                    "description": f"Request error: {str(e)}"
                })
                
            except Exception as e:
                error_links += 1
                validation_results.append({
                    "url": link_url,
                    "status": "error",
                    "status_code": 0,
                    "response_time": 0,
                    "description": f"Unexpected error: {str(e)}"
                })
        
        return {
            "validation_results": validation_results,
            "summary": {
                "total_checked": len(validation_results),
                "working_links": working_links,
                "broken_links": broken_links,
                "error_links": error_links,
                "total_available": len(internal_links),
                "check_limited": len(internal_links) > max_links
            }
        }
        
    except Exception as e:
        return {
            "error": f"Internal link validation failed: {str(e)}",
            "validation_results": [],
            "summary": {
                "total_checked": 0,
                "working_links": 0,
                "broken_links": 0,
                "error_links": 0
            }
        }


def _analyze_internal_linking(links_data: Dict[str, Any], validation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze internal linking structure and provide SEO/UX recommendations"""
    analysis = {
        "linking_score": 0,  # 0-100
        "strengths": [],
        "issues": [],
        "recommendations": [],
        "seo_analysis": {
            "link_depth_distribution": {},
            "anchor_text_analysis": {},
            "navigation_structure": {}
        },
        "technical_health": {
            "broken_link_percentage": 0,
            "redirect_percentage": 0,
            "average_response_time": 0
        }
    }
    
    total_links = links_data.get("total_internal_links", 0)
    unique_links = len(links_data.get("unique_internal_links", []))
    validation_summary = validation_data.get("summary", {})
    
    score = 0
    max_score = 100
    
    # Check if site has internal links (20 points)
    if total_links > 0:
        score += 20
        analysis["strengths"].append(f"Site has {total_links} internal links")
    else:
        analysis["issues"].append("No internal links found")
        analysis["recommendations"].append("Add internal links to improve navigation and SEO")
    
    # Check link variety and distribution (15 points)
    if unique_links > 10:
        score += 15
        analysis["strengths"].append(f"Good link variety with {unique_links} unique internal destinations")
    elif unique_links > 5:
        score += 10
        analysis["recommendations"].append("Consider adding more internal links to different pages")
    else:
        analysis["issues"].append("Limited internal linking structure")
        analysis["recommendations"].append("Improve internal linking by connecting related content")
    
    # Check navigation structure (20 points)
    nav_analysis = links_data.get("navigation_analysis", {})
    if nav_analysis.get("has_navigation"):
        score += 15
        analysis["strengths"].append("Site has proper navigation structure")
        
        nav_links = len(nav_analysis.get("navigation_links", []))
        if 3 <= nav_links <= 7:
            score += 5
            analysis["strengths"].append(f"Good navigation link count: {nav_links}")
        elif nav_links > 7:
            analysis["recommendations"].append("Consider simplifying navigation - too many nav links can overwhelm users")
    else:
        analysis["issues"].append("No clear navigation structure detected")
        analysis["recommendations"].append("Add proper navigation menu for better user experience")
    
    # Check breadcrumbs (5 points)
    breadcrumbs = len(nav_analysis.get("breadcrumb_links", []))
    if breadcrumbs > 0:
        score += 5
        analysis["strengths"].append("Site includes breadcrumb navigation")
    
    # Check technical health (25 points)
    working_links = validation_summary.get("working_links", 0)
    broken_links = validation_summary.get("broken_links", 0)
    total_checked = validation_summary.get("total_checked", 0)
    
    if total_checked > 0:
        broken_percentage = (broken_links / total_checked) * 100
        analysis["technical_health"]["broken_link_percentage"] = round(broken_percentage, 2)
        
        if broken_percentage == 0:
            score += 25
            analysis["strengths"].append("All internal links are working correctly")
        elif broken_percentage < 5:
            score += 20
            analysis["recommendations"].append(f"Fix {broken_links} broken internal links")
        elif broken_percentage < 15:
            score += 10
            analysis["issues"].append(f"{broken_percentage:.1f}% of internal links are broken")
            analysis["recommendations"].append("High number of broken links hurts user experience and SEO")
        else:
            analysis["issues"].append(f"Critical: {broken_percentage:.1f}% of internal links are broken")
            analysis["recommendations"].append("Immediate action needed to fix broken internal links")
    
    # Check for redirects and performance (10 points)
    redirects = 0
    total_response_time = 0
    valid_responses = 0
    
    for result in validation_data.get("validation_results", []):
        if result.get("redirect_count", 0) > 0:
            redirects += 1
        
        response_time = result.get("response_time", 0)
        if response_time > 0:
            total_response_time += response_time
            valid_responses += 1
    
    if total_checked > 0:
        redirect_percentage = (redirects / total_checked) * 100
        analysis["technical_health"]["redirect_percentage"] = round(redirect_percentage, 2)
        
        if redirect_percentage < 10:
            score += 5
        else:
            analysis["issues"].append(f"{redirect_percentage:.1f}% of links redirect - consider updating to final URLs")
    
    if valid_responses > 0:
        avg_response_time = total_response_time / valid_responses
        analysis["technical_health"]["average_response_time"] = round(avg_response_time, 3)
        
        if avg_response_time < 1:
            score += 5
            analysis["strengths"].append("Internal links load quickly")
        elif avg_response_time > 3:
            analysis["issues"].append("Internal links are slow to load")
    
    # Check anchor text quality (5 points)
    descriptive_anchors = 0
    generic_anchors = 0
    
    for link_detail in links_data.get("link_details", []):
        text = link_detail.get("text", "").lower().strip()
        if text in ["click here", "read more", "here", "more", "link"]:
            generic_anchors += 1
        elif len(text) > 3 and text not in ["home", "about", "contact"]:
            descriptive_anchors += 1
    
    total_text_links = descriptive_anchors + generic_anchors
    if total_text_links > 0:
        descriptive_percentage = (descriptive_anchors / total_text_links) * 100
        if descriptive_percentage > 80:
            score += 5
            analysis["strengths"].append("Most internal links have descriptive anchor text")
        elif descriptive_percentage < 50:
            analysis["issues"].append("Many links use generic anchor text like 'click here'")
            analysis["recommendations"].append("Use descriptive anchor text for better SEO and accessibility")
    
    # Calculate final score
    analysis["linking_score"] = min(score, max_score)
    
    # Overall recommendations based on score
    if analysis["linking_score"] >= 85:
        analysis["recommendations"].append("Excellent internal linking structure!")
    elif analysis["linking_score"] >= 70:
        analysis["recommendations"].append("Good internal linking with room for minor improvements")
    elif analysis["linking_score"] >= 50:
        analysis["recommendations"].append("Internal linking needs improvement for better SEO and user experience")
    else:
        analysis["recommendations"].append("Poor internal linking structure requires immediate attention")
    
    return analysis


# --- MCP Tools ---

@mcp.tool()
async def crawl_site(
    url: str,
    max_pages: int = 10,
    headless: bool = True,
    wait_time: float = 2.0,
    timeout: int = 30
) -> Dict[str, Any]:
    """Crawl a website and extract all pages, resources, and links for analysis using Playwright.
    
    This function uses Playwright to simulate browser interactions and crawl a website systematically,
    extracting comprehensive information about pages, links, and resources.
    
    Args:
        url (str): The starting URL to crawl (must include http:// or https://)
        max_pages (int): Maximum number of pages to crawl (default: 10, max: 100)
        headless (bool): Whether to run browser in headless mode (default: True)
        wait_time (float): Time to wait between page loads in seconds (default: 2.0)
        timeout (int): Page load timeout in seconds (default: 30)
    
    Returns:
        Dict containing:
        - summary: Overall crawl statistics and metadata
        - pages: List of detailed page information including:
          - url: Page URL
          - title: Page title
          - status_code: HTTP status code
          - links: All links found on the page
          - resources: Categorized resources (CSS, JS, images, media)
          - meta_data: Page metadata (description, keywords, etc.)
          - text_content: Extracted text content
          - error: Any error encountered while crawling the page
    
    Example:
        ```python
        # Basic site crawl
        result = crawl_site("https://example.com")
        
        # Detailed crawl with custom settings
        result = crawl_site(
            url="https://mysite.com",
            max_pages=25,
            headless=False,
            wait_time=3.0
        )
        
        # Access results
        print(f"Crawled {result['summary']['total_pages']} pages")
        for page in result['pages']:
            print(f"Page: {page['title']} - {len(page['links'])} links found")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    if max_pages > 100:
        max_pages = 100
        
    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright is not installed. Install with: pip install playwright && playwright install"}
    
    start_time = time.time()
    
    try:
        return await _crawl_with_playwright(url, max_pages, headless, wait_time, timeout, start_time)
            
    except Exception as e:
        return {
            "error": f"Crawl failed: {str(e)}",
            "summary": {
                "total_pages": 0,
                "total_links": 0,
                "total_resources": 0,
                "unique_domains": [],
                "crawl_time": time.time() - start_time,
                "errors": [str(e)]
            },
            "pages": []
        }

async def _crawl_with_playwright(url: str, max_pages: int, headless: bool, wait_time: float, timeout: int, start_time: float) -> Dict[str, Any]:
    """Internal function to crawl with Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        page.set_default_timeout(timeout * 1000)
        
        visited = set()
        to_visit = [url]
        crawled_pages = []
        errors = []
        all_domains = set()
        
        try:
            while to_visit and len(visited) < max_pages:
                current_url = to_visit.pop(0)
                if current_url in visited:
                    continue
                    
                visited.add(current_url)
                print(f"Crawling: {current_url}")
                
                try:
                    response = await page.goto(current_url)
                    await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                    
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    
                    # Extract page information
                    title = await page.title() or "No Title"
                    status_code = response.status if response else 0
                    
                    # Extract links
                    page_links = await _extract_links_playwright(page, current_url)
                    
                    # Extract resources
                    resources = await _extract_resources_playwright(page)
                    
                    # Extract metadata
                    meta_data = {}
                    try:
                        meta_desc = await page.query_selector('meta[name="description"]')
                        if meta_desc:
                            meta_data['description'] = await meta_desc.get_attribute('content')
                        
                        meta_keywords = await page.query_selector('meta[name="keywords"]')
                        if meta_keywords:
                            meta_data['keywords'] = await meta_keywords.get_attribute('content')
                    except:
                        pass
                    
                    # Extract text content
                    text_content = ""
                    try:
                        text_content = await page.inner_text('body')
                        text_content = text_content[:1000]  # Limit to first 1000 chars
                    except:
                        pass
                    
                    # Add domain to tracking
                    parsed = urlparse(current_url)
                    all_domains.add(parsed.netloc)
                    
                    # Create crawl result
                    crawl_result = CrawlResult(
                        url=current_url,
                        title=title,
                        status_code=status_code,
                        links=page_links,
                        resources=resources,
                        meta_data=meta_data,
                        text_content=text_content
                    )
                    crawled_pages.append(crawl_result)
                    
                    # Add new URLs to crawl queue
                    base_domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    for link in page_links:
                        if _should_crawl_url(link, base_domain, visited, max_pages):
                            if link not in to_visit:
                                to_visit.append(link)
                
                except Exception as e:
                    error_msg = f"Error crawling {current_url}: {str(e)}"
                    errors.append(error_msg)
                    print(error_msg)
                    
                    # Still add a result with error info
                    crawl_result = CrawlResult(
                        url=current_url,
                        title="Error",
                        status_code=0,
                        links=[],
                        resources={},
                        meta_data={},
                        text_content="",
                        error=str(e)
                    )
                    crawled_pages.append(crawl_result)
        
        finally:
            await browser.close()
    
    # Calculate summary statistics
    total_links = sum(len(page.links) for page in crawled_pages)
    total_resources = sum(sum(len(resources) for resources in page.resources.values()) for page in crawled_pages)
    
    summary = SiteCrawlSummary(
        total_pages=len(crawled_pages),
        total_links=total_links,
        total_resources=total_resources,
        unique_domains=list(all_domains),
        crawl_time=time.time() - start_time,
        errors=errors,
        pages=crawled_pages
    )
    
    # Convert to dict for JSON serialization
    return {
        "summary": {
            "total_pages": summary.total_pages,
            "total_links": summary.total_links,
            "total_resources": summary.total_resources,
            "unique_domains": summary.unique_domains,
            "crawl_time": round(summary.crawl_time, 2),
            "errors": summary.errors
        },
        "pages": [
            {
                "url": page.url,
                "title": page.title,
                "status_code": page.status_code,
                "links": page.links,
                "resources": page.resources,
                "meta_data": page.meta_data,
                "text_content": page.text_content,
                "error": page.error
            }
            for page in crawled_pages
        ]
    }


@mcp.tool()
async def audit_speed(
    url: str,
    timeout: int = 120
) -> Dict[str, Any]:
    """Audit website performance using Lighthouse CI to measure speed metrics.
    
    This function runs a comprehensive performance audit using Google Lighthouse,
    measuring key web vitals and performance metrics including FCP, LCP, TTI,
    and total load time.
    
    Args:
        url (str): The URL to audit (must include http:// or https://)
        timeout (int): Lighthouse audit timeout in seconds (default: 120)
    
    Returns:
        Dict containing:
        - overall_score: Overall performance score (0-100)
        - metrics: Detailed performance metrics including:
          - first_contentful_paint: FCP timing and score
          - largest_contentful_paint: LCP timing and score
          - time_to_interactive: TTI timing and score
          - speed_index: Speed index timing and score
          - total_blocking_time: TBT timing and score
          - cumulative_layout_shift: CLS value and score
        - audit_info: Metadata about the audit
        - error: Any error encountered during the audit
    
    Example:
        ```python
        # Basic speed audit
        result = audit_speed("https://example.com")
        
        # Audit with custom timeout
        result = audit_speed("https://mysite.com", timeout=180)
        
        # Access results
        print(f"Performance score: {result['overall_score']}/100")
        print(f"FCP: {result['metrics']['first_contentful_paint']['value_seconds']}s")
        print(f"LCP: {result['metrics']['largest_contentful_paint']['value_seconds']}s")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if Lighthouse is available
    if not LIGHTHOUSE_AVAILABLE:
        return {"error": "Lighthouse dependencies not available. Install with: npm install -g lighthouse"}
    
    try:
        # Check if Lighthouse CLI is installed
        lighthouse_check = subprocess.run(['lighthouse', '--version'], 
                                        capture_output=True, text=True, timeout=10)
        if lighthouse_check.returncode != 0:
            return {"error": "Lighthouse CLI not found. Install with: npm install -g lighthouse"}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"error": "Lighthouse CLI not found. Install with: npm install -g lighthouse"}
    
    start_time = time.time()
    
    try:
        # Run Lighthouse audit
        lighthouse_data = await _run_lighthouse(url, "performance")
        
        if "error" in lighthouse_data:
            return {
                "error": lighthouse_data["error"],
                "audit_info": {
                    "url": url,
                    "audit_time": round(time.time() - start_time, 2),
                    "lighthouse_version": "unknown"
                }
            }
        
        # Extract overall performance score
        categories = lighthouse_data.get('categories', {})
        performance_category = categories.get('performance', {})
        overall_score = int((performance_category.get('score', 0) or 0) * 100)
        
        # Extract detailed metrics using helper functions
        fcp_lcp_metrics = _measure_fcp_lcp(lighthouse_data)
        tti_metrics = _measure_tti(lighthouse_data)
        load_time_metrics = _measure_total_load_time(lighthouse_data)
        
        # Combine all metrics
        all_metrics = {}
        if "error" not in fcp_lcp_metrics:
            all_metrics.update(fcp_lcp_metrics)
        if "error" not in tti_metrics:
            all_metrics.update(tti_metrics)
        if "error" not in load_time_metrics:
            all_metrics.update(load_time_metrics)
        
        # Get Lighthouse version and other metadata
        environment = lighthouse_data.get('environment', {})
        lighthouse_version = environment.get('lighthouseVersion', 'unknown')
        user_agent = environment.get('networkUserAgent', 'unknown')
        
        audit_time = round(time.time() - start_time, 2)
        
        return {
            "overall_score": overall_score,
            "metrics": all_metrics,
            "audit_info": {
                "url": url,
                "audit_time": audit_time,
                "lighthouse_version": lighthouse_version,
                "user_agent": user_agent,
                "timestamp": time.time()
            }
        }
        
    except Exception as e:
        return {
            "error": f"Speed audit failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def check_schema(
    url: str,
    headless: bool = True,
    timeout: int = 30
) -> Dict[str, Any]:
    """Audit and validate structured data (schema) implementation on a webpage.
    
    This function uses Playwright to extract and analyze all types of structured data
    including JSON-LD, Microdata, and RDFa markup to help improve SEO and search
    engine understanding of your content.
    
    Args:
        url (str): The URL to audit for structured data (must include http:// or https://)
        headless (bool): Whether to run browser in headless mode (default: True)
        timeout (int): Page load timeout in seconds (default: 30)
    
    Returns:
        Dict containing:
        - validation: Overall validation results and statistics
        - structured_data: All extracted structured data organized by type
        - recommendations: SEO and implementation recommendations
        - errors: Any errors encountered during extraction
    
    The structured_data includes:
        - json_ld: JSON-LD structured data with parsed content
        - microdata: Microdata markup with properties and values
        - rdfa: RDFa markup with attributes and content
    
    Example:
        ```python
        # Basic schema audit
        result = check_schema("https://example.com")
        
        # Audit with custom settings
        result = check_schema("https://mysite.com", headless=False, timeout=60)
        
        # Access results
        print(f"Found {result['validation']['total_items']} structured data items")
        print(f"Schema types: {result['validation']['schema_types']}")
        for item in result['structured_data']['json_ld']:
            print(f"JSON-LD: {item['data']['@type']}")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright is not installed. Install with: pip install playwright && playwright install"}
    
    start_time = time.time()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()
            page.set_default_timeout(timeout * 1000)
            
            try:
                # Navigate to the page
                response = await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                
                if not response or response.status >= 400:
                    return {
                        "error": f"Failed to load page. HTTP status: {response.status if response else 'unknown'}",
                        "audit_info": {
                            "url": url,
                            "audit_time": round(time.time() - start_time, 2)
                        }
                    }
                
                # Extract structured data using helper functions
                print(f"Extracting structured data from: {url}")
                
                # Run all extraction functions concurrently
                jsonld_data, microdata_data, rdfa_data = await asyncio.gather(
                    _fetch_jsonld(page),
                    _fetch_microdata(page),
                    _fetch_rdfa(page)
                )
                
                # Combine all structured data
                all_structured_data = jsonld_data + microdata_data + rdfa_data
                
                # Validate and analyze the data
                validation_results = _validate_schema_data(all_structured_data)
                
                audit_time = round(time.time() - start_time, 2)
                
                return {
                    "validation": validation_results,
                    "structured_data": {
                        "json_ld": jsonld_data,
                        "microdata": microdata_data,
                        "rdfa": rdfa_data
                    },
                    "audit_info": {
                        "url": url,
                        "audit_time": audit_time,
                        "page_title": await page.title(),
                        "timestamp": time.time(),
                        "total_structured_items": len(all_structured_data)
                    }
                }
                
            finally:
                await browser.close()
                
    except Exception as e:
        return {
            "error": f"Schema audit failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def check_external_links(
    url: str,
    headless: bool = True,
    timeout: int = 30,
    link_timeout: int = 10,
    max_links: int = 50
) -> Dict[str, Any]:
    """Check all external links on a webpage to identify broken or problematic links.
    
    This function uses Playwright to extract all links from the page and then uses
    requests to check the HTTP status of each external link to identify broken links,
    timeouts, and other issues.
    
    Args:
        url (str): The URL to audit for external links (must include http:// or https://)
        headless (bool): Whether to run browser in headless mode (default: True)
        timeout (int): Page load timeout in seconds (default: 30)
        link_timeout (int): Timeout for checking individual links in seconds (default: 10)
        max_links (int): Maximum number of external links to check (default: 50)
    
    Returns:
        Dict containing:
        - links_summary: Categorized count of all links found (internal/external/email/etc.)
        - external_links_analysis: Detailed analysis of external link status
        - link_results: Individual results for each checked external link
        - audit_info: Metadata about the audit
        - recommendations: Actionable recommendations for fixing issues
    
    Example:
        ```python
        # Basic external links check
        result = check_external_links("https://example.com")
        
        # Check with custom settings
        result = check_external_links(
            "https://mysite.com", 
            max_links=100,
            link_timeout=15
        )
        
        # Access results
        analysis = result['external_links_analysis']
        print(f"Working: {analysis['working_links']}, Broken: {analysis['broken_links']}")
        for broken in analysis['broken_link_details']:
            print(f"Broken link: {broken['url']} - {broken['error']}")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright is not installed. Install with: pip install playwright && playwright install"}
    
    # Check if requests is available
    if not REQUESTS_AVAILABLE:
        return {"error": "requests library is not installed. Install with: pip install requests"}
    
    start_time = time.time()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()
            page.set_default_timeout(timeout * 1000)
            
            try:
                # Navigate to the page
                response = await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                
                if not response or response.status >= 400:
                    return {
                        "error": f"Failed to load page. HTTP status: {response.status if response else 'unknown'}",
                        "audit_info": {
                            "url": url,
                            "audit_time": round(time.time() - start_time, 2)
                        }
                    }
                
                # Extract all links using helper function
                print(f"Extracting links from: {url}")
                links_data = await _fetch_all_links(page, url)
                
                # Get external links to check (limit to max_links)
                external_links = links_data["external_links"][:max_links]
                
                print(f"Found {len(external_links)} external links to check (limited to {max_links})")
                
                # Check each external link status
                link_results = []
                if external_links:
                    print("Checking external link status...")
                    
                    # Check links sequentially to avoid overwhelming servers
                    for i, link in enumerate(external_links):
                        print(f"Checking link {i+1}/{len(external_links)}: {link}")
                        result = await _check_link_status(link, timeout=link_timeout)
                        link_results.append(result)
                        
                        # Small delay between requests to be respectful
                        if i < len(external_links) - 1:
                            await asyncio.sleep(0.5)
                
                # Analyze the results
                analysis = _analyze_link_results(link_results)
                
                audit_time = round(time.time() - start_time, 2)
                
                return {
                    "links_summary": {
                        "total_links": sum(len(links) for links in links_data.values()),
                        "internal_links": len(links_data["internal_links"]),
                        "external_links": len(links_data["external_links"]),
                        "external_links_checked": len(external_links),
                        "email_links": len(links_data["email_links"]),
                        "tel_links": len(links_data["tel_links"]),
                        "other_links": len(links_data["other_links"])
                    },
                    "external_links_analysis": analysis,
                    "link_results": link_results,
                    "audit_info": {
                        "url": url,
                        "audit_time": audit_time,
                        "page_title": await page.title(),
                        "timestamp": time.time(),
                        "max_links_limit": max_links
                    }
                }
                
            finally:
                await browser.close()
                
    except Exception as e:
        return {
            "error": f"External links audit failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def audit_accessibility(
    url: str,
    headless: bool = True,
    timeout: int = 30
) -> Dict[str, Any]:
    """Perform a comprehensive accessibility audit of a webpage.
    
    This function uses Playwright and a simplified Axe-core implementation to check
    various accessibility aspects including alt text, color contrast, ARIA labels,
    and other WCAG guidelines to ensure the website is accessible to all users.
    
    Args:
        url (str): The URL to audit for accessibility (must include http:// or https://)
        headless (bool): Whether to run browser in headless mode (default: True)
        timeout (int): Page load timeout in seconds (default: 30)
    
    Returns:
        Dict containing:
        - accessibility_summary: Overall accessibility score and statistics
        - alt_text_audit: Results of image alt text checking
        - contrast_audit: Results of color contrast checking
        - aria_audit: Results of ARIA labels and semantic structure checking
        - audit_info: Metadata about the audit
        - recommendations: Actionable recommendations for improving accessibility
    
    The audit checks for:
        - Image alt text presence and quality
        - Color contrast ratios (WCAG AA standards)
        - Form element labeling and ARIA attributes
        - Heading structure and hierarchy
        - Skip navigation links
        - Interactive element accessibility
    
    Example:
        ```python
        # Basic accessibility audit
        result = audit_accessibility("https://example.com")
        
        # Audit with custom settings
        result = audit_accessibility("https://mysite.com", headless=False, timeout=60)
        
        # Access results
        summary = result['accessibility_summary']
        print(f"Accessibility Score: {summary['accessibility_score']}/100")
        print(f"Critical violations: {summary['violations_by_severity']['critical']}")
        
        # Get specific issues
        alt_issues = result['alt_text_audit']['violations']
        for issue in alt_issues:
            print(f"Alt text issue: {issue['description']} - {issue['src']}")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright is not installed. Install with: pip install playwright && playwright install"}
    
    start_time = time.time()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()
            page.set_default_timeout(timeout * 1000)
            
            try:
                # Navigate to the page
                response = await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                
                if not response or response.status >= 400:
                    return {
                        "error": f"Failed to load page. HTTP status: {response.status if response else 'unknown'}",
                        "audit_info": {
                            "url": url,
                            "audit_time": round(time.time() - start_time, 2)
                        }
                    }
                
                # Perform accessibility checks using helper functions
                print(f"Running accessibility audit for: {url}")
                
                # Run all accessibility checks concurrently for better performance
                alt_results, contrast_results, aria_results = await asyncio.gather(
                    _check_alt_text(page),
                    _check_contrast(page),
                    _check_aria_labels(page)
                )
                
                # Analyze combined results
                accessibility_summary = _analyze_accessibility_results(
                    alt_results, contrast_results, aria_results
                )
                
                audit_time = round(time.time() - start_time, 2)
                
                return {
                    "accessibility_summary": accessibility_summary,
                    "alt_text_audit": alt_results,
                    "contrast_audit": contrast_results,
                    "aria_audit": aria_results,
                    "audit_info": {
                        "url": url,
                        "audit_time": audit_time,
                        "page_title": await page.title(),
                        "timestamp": time.time(),
                        "wcag_level": "AA",  # Standards we're checking against
                        "checks_performed": [
                            "image_alt_text",
                            "color_contrast", 
                            "aria_labels",
                            "form_labeling",
                            "heading_structure",
                            "skip_links"
                        ]
                    }
                }
                
            finally:
                await browser.close()
                
    except Exception as e:
        return {
            "error": f"Accessibility audit failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def check_robots_txt(
    url: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """Check and validate a website's robots.txt file for crawling rules and SEO compliance.
    
    This function fetches the robots.txt file from the website root and analyzes it
    to understand crawling permissions, sitemap locations, and potential SEO impacts.
    It validates syntax, checks for common issues, and provides recommendations.
    
    Args:
        url (str): The base URL of the website to check (must include http:// or https://)
        timeout (int): Request timeout in seconds (default: 10)
    
    Returns:
        Dict containing:
        - robots_txt_status: Whether robots.txt was found and accessible
        - parsed_content: Structured breakdown of robots.txt rules
        - analysis: SEO and crawlability analysis
        - raw_content: Original robots.txt content
        - recommendations: Actionable suggestions for improvement
        - audit_info: Metadata about the check
    
    The analysis includes:
        - User-agent specific rules (Allow/Disallow directives)
        - Sitemap declarations
        - Crawl-delay settings
        - Syntax validation and error detection
        - SEO impact assessment
        - Crawlability evaluation
    
    Example:
        ```python
        # Basic robots.txt check
        result = check_robots_txt("https://example.com")
        
        # Check with custom timeout
        result = check_robots_txt("https://mysite.com", timeout=15)
        
        # Access results
        if result['robots_txt_status']['found']:
            analysis = result['analysis']
            print(f"Total rules: {analysis['summary']['total_rules']}")
            print(f"Sitemaps found: {analysis['summary']['total_sitemaps']}")
            
            for recommendation in analysis['recommendations']:
                print(f"Recommendation: {recommendation}")
        else:
            print("No robots.txt found")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if requests is available
    if not REQUESTS_AVAILABLE:
        return {"error": "requests library is not installed. Install with: pip install requests"}
    
    start_time = time.time()
    
    try:
        # Fetch robots.txt file
        print(f"Checking robots.txt for: {url}")
        fetch_result = await _fetch_robots_txt(url, timeout=timeout)
        
        robots_txt_status = {
            "found": fetch_result["success"] and fetch_result.get("status_code") == 200,
            "accessible": fetch_result["success"],
            "status_code": fetch_result.get("status_code", 0),
            "response_time": fetch_result.get("response_time", 0),
            "content_length": fetch_result.get("content_length", 0),
            "content_type": fetch_result.get("content_type", ""),
            "url": fetch_result.get("url", ""),
            "error": fetch_result.get("error") if not fetch_result["success"] else None
        }
        
        # Parse and analyze content if robots.txt was found
        parsed_content = None
        analysis = None
        raw_content = None
        
        if robots_txt_status["found"] and fetch_result.get("content"):
            raw_content = fetch_result["content"]
            parsed_content = _parse_robots_txt(raw_content)
            analysis = _analyze_robots_txt(parsed_content, url)
        elif robots_txt_status["accessible"]:
            # robots.txt exists but might be empty or have different status code
            parsed_content = _parse_robots_txt("")
            analysis = _analyze_robots_txt(parsed_content, url)
            if fetch_result.get("status_code") == 404:
                analysis["seo_impact"].append("No robots.txt found - search engines will crawl all accessible content")
                analysis["recommendations"].append("Consider creating a robots.txt file to control crawler behavior")
        else:
            # robots.txt not accessible due to error
            parsed_content = _parse_robots_txt("")
            analysis = _analyze_robots_txt(parsed_content, url)
            analysis["seo_impact"].append(f"robots.txt inaccessible: {fetch_result.get('error', 'Unknown error')}")
            analysis["recommendations"].append("Ensure robots.txt is accessible at the domain root")
        
        audit_time = round(time.time() - start_time, 2)
        
        return {
            "robots_txt_status": robots_txt_status,
            "parsed_content": parsed_content,
            "analysis": analysis,
            "raw_content": raw_content,
            "audit_info": {
                "url": url,
                "robots_txt_url": robots_txt_status["url"],
                "audit_time": audit_time,
                "timestamp": time.time(),
                "checks_performed": [
                    "accessibility_check",
                    "syntax_validation", 
                    "user_agent_rules",
                    "sitemap_detection",
                    "crawl_delay_analysis",
                    "seo_impact_assessment"
                ]
            }
        }
        
    except Exception as e:
        return {
            "error": f"robots.txt check failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def check_https_usage(
    url: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """Check HTTPS implementation and SSL certificate security for a website.
    
    This function performs a comprehensive security audit of a website's HTTPS
    configuration, including SSL certificate validation, TLS protocol checking,
    and HTTP to HTTPS redirection analysis to ensure secure connections.
    
    Args:
        url (str): The URL to check for HTTPS security (must include http:// or https://)
        timeout (int): Request timeout in seconds (default: 10)
    
    Returns:
        Dict containing:
        - https_status: HTTPS availability and redirection analysis
        - ssl_certificate: SSL certificate validation and details
        - security_analysis: Overall security assessment and scoring
        - audit_info: Metadata about the security check
        - recommendations: Actionable security improvements
    
    The check includes:
        - HTTPS availability and accessibility
        - HTTP to HTTPS automatic redirection
        - SSL certificate validity and expiration
        - Certificate domain matching and trust chain
        - TLS protocol version and cipher strength
        - Security best practices compliance
    
    Example:
        ```python
        # Basic HTTPS security check
        result = check_https_usage("https://example.com")
        
        # Check with custom timeout
        result = check_https_usage("http://mysite.com", timeout=15)
        
        # Access results
        analysis = result['security_analysis']
        print(f"Security Score: {analysis['security_score']}/100")
        
        if result['https_status']['https_available']:
            cert = result['ssl_certificate']['certificate_info']
            print(f"Certificate expires: {cert.get('not_after', 'Unknown')}")
            print(f"Days until expiry: {cert.get('days_until_expiry', 'Unknown')}")
        
        for issue in analysis['security_issues']:
            print(f"Security Issue: {issue}")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if required libraries are available
    if not REQUESTS_AVAILABLE:
        return {"error": "requests library is not installed. Install with: pip install requests"}
    
    if not SSL_AVAILABLE:
        return {"error": "SSL libraries are not available"}
    
    start_time = time.time()
    
    try:
        # Extract domain from URL for certificate checking
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        print(f"Checking HTTPS security for: {url}")
        
        # Perform HTTPS and SSL checks concurrently
        https_status, ssl_certificate = await asyncio.gather(
            _check_https_status(url, timeout=timeout),
            _check_ssl_certificate(domain, timeout=timeout)
        )
        
        # Analyze the security configuration
        security_analysis = _analyze_https_security(https_status, ssl_certificate)
        
        audit_time = round(time.time() - start_time, 2)
        
        return {
            "https_status": https_status,
            "ssl_certificate": ssl_certificate,
            "security_analysis": security_analysis,
            "audit_info": {
                "url": url,
                "domain": domain,
                "audit_time": audit_time,
                "timestamp": time.time(),
                "checks_performed": [
                    "https_availability",
                    "http_to_https_redirect",
                    "ssl_certificate_validation",
                    "certificate_expiry_check",
                    "domain_name_validation",
                    "tls_protocol_analysis",
                    "cipher_strength_evaluation",
                    "security_best_practices"
                ]
            }
        }
        
    except Exception as e:
        return {
            "error": f"HTTPS security check failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


@mcp.tool()
async def check_internal_linking(
    url: str,
    headless: bool = True,
    timeout: int = 30,
    link_timeout: int = 10,
    max_links: int = 100
) -> Dict[str, Any]:
    """Analyze internal linking structure and validate link functionality for SEO and UX.
    
    This function uses Playwright to extract all internal links from a webpage and then
    validates their functionality using HTTP requests. It provides comprehensive analysis
    of internal linking structure, navigation patterns, and technical health.
    
    Args:
        url (str): The URL to analyze for internal linking (must include http:// or https://)
        headless (bool): Whether to run browser in headless mode (default: True)
        timeout (int): Page load timeout in seconds (default: 30)
        link_timeout (int): Timeout for validating individual links in seconds (default: 10)
        max_links (int): Maximum number of internal links to validate (default: 100)
    
    Returns:
        Dict containing:
        - links_structure: Detailed breakdown of internal links found
        - validation_results: HTTP status validation for internal links
        - linking_analysis: SEO and UX analysis with scoring
        - audit_info: Metadata about the internal linking check
        - recommendations: Actionable improvements for internal linking
    
    The analysis includes:
        - Internal link discovery and categorization
        - Navigation structure evaluation (nav, breadcrumbs, footer)
        - Link functionality validation (HTTP status checking)
        - Anchor text quality assessment
        - SEO and user experience scoring
        - Performance analysis (response times, redirects)
    
    Example:
        ```python
        # Basic internal linking check
        result = check_internal_linking("https://example.com")
        
        # Check with custom settings
        result = check_internal_linking(
            "https://mysite.com", 
            max_links=150,
            link_timeout=15
        )
        
        # Access results
        analysis = result['linking_analysis']
        print(f"Internal Linking Score: {analysis['linking_score']}/100")
        print(f"Total internal links: {result['links_structure']['total_internal_links']}")
        
        validation = result['validation_results']['summary']
        print(f"Working links: {validation['working_links']}")
        print(f"Broken links: {validation['broken_links']}")
        
        for issue in analysis['issues']:
            print(f"Issue: {issue}")
        ```
    """
    
    # Validation
    if not _is_valid_url(url):
        return {"error": "Invalid URL provided. URL must include http:// or https://"}
    
    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright is not installed. Install with: pip install playwright && playwright install"}
    
    # Check if requests is available
    if not REQUESTS_AVAILABLE:
        return {"error": "requests library is not installed. Install with: pip install requests"}
    
    start_time = time.time()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()
            page.set_default_timeout(timeout * 1000)
            
            try:
                # Navigate to the page
                response = await page.goto(url)
                await page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                
                if not response or response.status >= 400:
                    return {
                        "error": f"Failed to load page. HTTP status: {response.status if response else 'unknown'}",
                        "audit_info": {
                            "url": url,
                            "audit_time": round(time.time() - start_time, 2)
                        }
                    }
                
                # Extract internal links structure
                print(f"Analyzing internal linking structure for: {url}")
                links_structure = await _get_internal_links(page, url)
                
                if "error" in links_structure:
                    return {
                        "error": links_structure["error"],
                        "audit_info": {
                            "url": url,
                            "audit_time": round(time.time() - start_time, 2)
                        }
                    }
                
                # Get unique internal links for validation
                unique_internal_links = links_structure.get("unique_internal_links", [])
                print(f"Found {len(unique_internal_links)} unique internal links to validate (limiting to {max_links})")
                
                # Validate internal link functionality
                validation_results = await _validate_internal_links(
                    unique_internal_links, 
                    url, 
                    timeout=link_timeout, 
                    max_links=max_links
                )
                
                # Analyze the internal linking structure
                linking_analysis = _analyze_internal_linking(links_structure, validation_results)
                
                audit_time = round(time.time() - start_time, 2)
                
                return {
                    "links_structure": links_structure,
                    "validation_results": validation_results,
                    "linking_analysis": linking_analysis,
                    "audit_info": {
                        "url": url,
                        "audit_time": audit_time,
                        "page_title": await page.title(),
                        "timestamp": time.time(),
                        "max_links_limit": max_links,
                        "checks_performed": [
                            "internal_link_extraction",
                            "navigation_structure_analysis",
                            "link_functionality_validation",
                            "anchor_text_evaluation",
                            "seo_scoring",
                            "technical_health_assessment"
                        ]
                    }
                }
                
            finally:
                await browser.close()
                
    except Exception as e:
        return {
            "error": f"Internal linking check failed: {str(e)}",
            "audit_info": {
                "url": url,
                "audit_time": round(time.time() - start_time, 2)
            }
        }


if __name__ == "__main__":
    mcp.run(transport='stdio')