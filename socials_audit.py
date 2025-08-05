#!/usr/bin/env python3
"""
Instagram Audit MCP Server
A minimal MCP server for Instagram profile and post auditing using web scraping.
"""

import asyncio
import json
import re
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Browser, Page
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Instagram Audit")

class InstagramScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # Create context with realistic user agent
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def get_page(self, url: str) -> Page:
        """Create a new page and navigate to URL."""
        page = await self.context.new_page()
        
        # Set reasonable timeouts
        page.set_default_timeout(30000)  # 30 seconds
        
        # Add some headers to look more like a real browser
        await page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        
        # Navigate to the page
        response = await page.goto(url, wait_until='networkidle')
        
        # Wait for content to load
        await page.wait_for_timeout(3000)
        
        return page, response
    
    def clean_username(self, username: str) -> str:
        """Clean and validate Instagram username."""
        # Remove @ symbol and clean
        username = username.replace('@', '').strip()
        
        # Remove instagram.com URL if provided
        if 'instagram.com' in username:
            match = re.search(r'instagram\.com/([^/?]+)', username)
            if match:
                username = match.group(1)
        
        return username

@mcp.tool()
async def get_profile_info(username: str) -> Dict[str, Any]:
    """
    Get Instagram profile information and basic stats.
    
    Args:
        username: Instagram username or profile URL
        
    Returns:
        Dictionary containing profile information
    """
    try:
        async with InstagramScraper() as scraper:
            clean_username = scraper.clean_username(username)
            url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"Fetching profile: {url}", file=sys.stderr)
            page, response = await scraper.get_page(url)
            
            # Check if profile exists
            if response.status == 404:
                await page.close()
                return {"error": f"Profile not found: {username}"}
            
            # Wait for profile data to load
            try:
                await page.wait_for_selector('header section', timeout=10000)
            except:
                await page.close()
                return {"error": "Could not load profile data - profile might be private"}
            
            # Extract profile information
            profile_data = await page.evaluate("""
                () => {
                    try {
                        // Try to get data from meta tags first
                        const metaDescription = document.querySelector('meta[property="og:description"]');
                        let followers = 0, following = 0, posts = 0;
                        
                        if (metaDescription) {
                            const desc = metaDescription.content;
                            const followersMatch = desc.match(/([\\d,]+)\\s+Followers/);
                            const followingMatch = desc.match(/([\\d,]+)\\s+Following/);
                            const postsMatch = desc.match(/([\\d,]+)\\s+Posts/);
                            
                            if (followersMatch) followers = parseInt(followersMatch[1].replace(/,/g, ''));
                            if (followingMatch) following = parseInt(followingMatch[1].replace(/,/g, ''));
                            if (postsMatch) posts = parseInt(postsMatch[1].replace(/,/g, ''));
                        }
                        
                        // Try to get stats from the page elements
                        const statsElements = document.querySelectorAll('header section ul li');
                        if (statsElements.length >= 3) {
                            const postsEl = statsElements[0]?.textContent || '0';
                            const followersEl = statsElements[1]?.textContent || '0';
                            const followingEl = statsElements[2]?.textContent || '0';
                            
                            posts = parseInt(postsEl.replace(/[^\\d]/g, '')) || posts;
                            followers = parseInt(followersEl.replace(/[^\\d]/g, '')) || followers;
                            following = parseInt(followingEl.replace(/[^\\d]/g, '')) || following;
                        }
                        
                        // Get profile info
                        const profileName = document.querySelector('header section h2')?.textContent?.trim() || '';
                        const bio = document.querySelector('header section div:-webkit-any-link + div')?.textContent?.trim() || '';
                        const isVerified = document.querySelector('header section svg[aria-label*="Verified"]') !== null;
                        const isPrivate = document.querySelector('article h2')?.textContent?.includes('private') || false;
                        
                        // Get profile picture
                        const profilePic = document.querySelector('header img')?.src || '';
                        
                        return {
                            posts,
                            followers,
                            following,
                            profile_name: profileName,
                            bio,
                            is_verified: isVerified,
                            is_private: isPrivate,
                            profile_picture: profilePic
                        };
                    } catch (error) {
                        return { error: error.message };
                    }
                }
            """)
            
            await page.close()
            
            if 'error' in profile_data:
                return {"error": f"Could not extract profile data: {profile_data['error']}"}
            
            # Calculate engagement metrics
            engagement_rate = 0
            if profile_data['followers'] > 0 and profile_data['posts'] > 0:
                # This is a rough estimate since we can't get actual engagement without post data
                engagement_rate = round((profile_data['posts'] / profile_data['followers']) * 100, 3)
            
            return {
                "username": clean_username,
                "url": url,
                "profile_name": profile_data['profile_name'],
                "bio": profile_data['bio'],
                "posts_count": profile_data['posts'],
                "followers_count": profile_data['followers'],
                "following_count": profile_data['following'],
                "is_verified": profile_data['is_verified'],
                "is_private": profile_data['is_private'],
                "profile_picture_url": profile_data['profile_picture'],
                "follower_following_ratio": round(profile_data['followers'] / max(profile_data['following'], 1), 2),
                "estimated_engagement_rate": engagement_rate
            }
            
    except Exception as e:
        print(f"Error in get_profile_info: {str(e)}", file=sys.stderr)
        return {"error": f"Error getting profile info: {str(e)}"}

@mcp.tool()
async def get_social_posts(username: str, limit: int = 12) -> Dict[str, Any]:
    """
    Get recent Instagram posts from a profile.
    
    Args:
        username: Instagram username or profile URL
        limit: Number of recent posts to fetch (default: 12, max: 24)
        
    Returns:
        Dictionary containing recent posts data
    """
    try:
        async with InstagramScraper() as scraper:
            clean_username = scraper.clean_username(username)
            url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"Fetching posts from: {url}", file=sys.stderr)
            page, response = await scraper.get_page(url)
            
            if response.status == 404:
                await page.close()
                return {"error": f"Profile not found: {username}"}
            
            # Check if account is private
            is_private = await page.evaluate("""
                () => {
                    const privateText = document.querySelector('article h2');
                    return privateText && privateText.textContent.includes('private');
                }
            """)
            
            if is_private:
                await page.close()
                return {"error": "Profile is private - cannot access posts"}
            
            # Wait for posts to load
            try:
                await page.wait_for_selector('article a[href*="/p/"]', timeout=10000)
            except:
                await page.close()
                return {"error": "Could not load posts - profile might have no posts"}
            
            # Extract post data
            posts_data = await page.evaluate(f"""
                (limit) => {{
                    try {{
                        const postLinks = document.querySelectorAll('article a[href*="/p/"]');
                        const posts = [];
                        
                        for (let i = 0; i < Math.min(postLinks.length, limit); i++) {{
                            const link = postLinks[i];
                            const img = link.querySelector('img');
                            const postUrl = link.href;
                            const postId = postUrl.match(/\\/p\\/([^/]+)/)?.[1] || '';
                            
                            posts.push({{
                                post_id: postId,
                                post_url: postUrl,
                                image_url: img?.src || '',
                                alt_text: img?.alt || '',
                                timestamp: null // We can't easily get timestamp from grid view
                            }});
                        }}
                        
                        return posts;
                    }} catch (error) {{
                        return {{ error: error.message }};
                    }}
                }}
            """, min(limit, 24))
            
            await page.close()
            
            if isinstance(posts_data, dict) and 'error' in posts_data:
                return {"error": f"Could not extract posts: {posts_data['error']}"}
            
            return {
                "username": clean_username,
                "total_posts_found": len(posts_data),
                "posts": posts_data
            }
            
    except Exception as e:
        print(f"Error in get_social_posts: {str(e)}", file=sys.stderr)
        return {"error": f"Error getting posts: {str(e)}"}

@mcp.tool()
async def analyze_engagement_score(username: str, sample_size: int = 6) -> Dict[str, Any]:
    """
    Analyze engagement metrics for recent posts.
    
    Args:
        username: Instagram username or profile URL
        sample_size: Number of recent posts to analyze (default: 6, max: 12)
        
    Returns:
        Dictionary containing engagement analysis
    """
    try:
        async with InstagramScraper() as scraper:
            clean_username = scraper.clean_username(username)
            
            # First get profile info for follower count
            profile_info = await get_profile_info(username)
            if 'error' in profile_info:
                return profile_info
            
            if profile_info['is_private']:
                return {"error": "Cannot analyze engagement for private profiles"}
            
            followers = profile_info['followers_count']
            if followers == 0:
                return {"error": "Cannot calculate engagement rate - no followers data"}
            
            # Get recent posts
            posts_data = await get_social_posts(username, sample_size)
            if 'error' in posts_data:
                return posts_data
            
            if not posts_data['posts']:
                return {"error": "No posts found to analyze"}
            
            # Analyze individual posts for engagement (this is limited without direct post access)
            post_analysis = []
            total_estimated_engagement = 0
            
            # Since we can't get actual likes/comments from the grid view,
            # we'll provide analysis based on available data
            for i, post in enumerate(posts_data['posts'][:sample_size]):
                # Estimate engagement based on image quality and alt text
                estimated_quality_score = 0
                
                if post['alt_text']:
                    # Posts with alt text might indicate more engagement
                    estimated_quality_score += 2
                    
                if 'photo by' in post['alt_text'].lower():
                    estimated_quality_score += 1
                
                post_analysis.append({
                    "post_id": post['post_id'],
                    "post_url": post['post_url'],
                    "estimated_quality_score": estimated_quality_score,
                    "has_alt_text": bool(post['alt_text']),
                    "alt_text_length": len(post['alt_text'])
                })
                
                total_estimated_engagement += estimated_quality_score
            
            avg_quality_score = total_estimated_engagement / len(post_analysis) if post_analysis else 0
            
            # Calculate basic metrics
            posts_per_engagement = followers / max(profile_info['posts_count'], 1)
            
            return {
                "username": clean_username,
                "followers_count": followers,
                "posts_analyzed": len(post_analysis),
                "avg_estimated_quality_score": round(avg_quality_score, 2),
                "follower_to_posts_ratio": round(posts_per_engagement, 2),
                "posting_frequency_rating": _rate_posting_frequency(profile_info['posts_count']),
                "profile_optimization_score": _calculate_profile_score(profile_info),
                "post_analysis": post_analysis,
                "recommendations": _generate_instagram_recommendations(profile_info, post_analysis)
            }
            
    except Exception as e:
        print(f"Error in analyze_engagement_score: {str(e)}", file=sys.stderr)
        return {"error": f"Error analyzing engagement: {str(e)}"}

@mcp.tool()
async def get_hashtag_analysis(username: str) -> Dict[str, Any]:
    """
    Analyze hashtag usage and strategy (limited analysis from public data).
    
    Args:
        username: Instagram username or profile URL
        
    Returns:
        Dictionary containing hashtag analysis
    """
    try:
        # Get profile info first
        profile_info = await get_profile_info(username)
        if 'error' in profile_info:
            return profile_info
        
        # Analyze bio for hashtags
        bio = profile_info.get('bio', '')
        bio_hashtags = re.findall(r'#\w+', bio)
        
        # Basic analysis
        has_branded_hashtag = any('#' + profile_info['username'].lower() in tag.lower() for tag in bio_hashtags)
        
        return {
            "username": profile_info['username'],
            "bio_hashtags": bio_hashtags,
            "bio_hashtag_count": len(bio_hashtags),
            "has_branded_hashtag_in_bio": has_branded_hashtag,
            "bio_optimization_score": _calculate_bio_score(bio, bio_hashtags),
            "recommendations": _generate_hashtag_recommendations(bio_hashtags, profile_info)
        }
        
    except Exception as e:
        return {"error": f"Error analyzing hashtags: {str(e)}"}

@mcp.tool()
async def compare_instagram_profiles(usernames: List[str]) -> Dict[str, Any]:
    """
    Compare multiple Instagram profiles side by side.
    
    Args:
        usernames: List of Instagram usernames to compare (max 5)
        
    Returns:
        Dictionary containing profile comparison
    """
    try:
        if len(usernames) > 5:
            return {"error": "Maximum 5 profiles can be compared at once"}
        
        # Get profile info for all users
        tasks = [get_profile_info(username) for username in usernames]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors and exceptions
        valid_profiles = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({"username": usernames[i], "error": str(result)})
            elif isinstance(result, dict) and 'error' not in result:
                valid_profiles.append(result)
            else:
                errors.append({"username": usernames[i], "error": result.get('error', 'Unknown error')})
        
        if not valid_profiles:
            return {"error": "No valid profiles found", "individual_errors": errors}
        
        # Create comparison
        comparison = {
            "profiles_compared": len(valid_profiles),
            "profiles": valid_profiles,
            "comparison_metrics": {
                "highest_followers": max(valid_profiles, key=lambda x: x['followers_count']),
                "most_posts": max(valid_profiles, key=lambda x: x['posts_count']),
                "best_follower_ratio": max(valid_profiles, key=lambda x: x['follower_following_ratio']),
                "most_verified": len([p for p in valid_profiles if p['is_verified']]),
                "private_accounts": len([p for p in valid_profiles if p['is_private']])
            },
            "ranking_by_followers": sorted(valid_profiles, key=lambda x: x['followers_count'], reverse=True),
            "avg_metrics": {
                "avg_followers": round(sum(p['followers_count'] for p in valid_profiles) / len(valid_profiles)),
                "avg_posts": round(sum(p['posts_count'] for p in valid_profiles) / len(valid_profiles)),
                "avg_following": round(sum(p['following_count'] for p in valid_profiles) / len(valid_profiles))
            }
        }
        
        if errors:
            comparison["errors"] = errors
        
        return comparison
        
    except Exception as e:
        return {"error": f"Error comparing profiles: {str(e)}"}

def _rate_posting_frequency(posts_count: int) -> str:
    """Rate posting frequency based on total posts."""
    if posts_count >= 1000:
        return "Very High"
    elif posts_count >= 500:
        return "High"
    elif posts_count >= 100:
        return "Moderate"
    elif posts_count >= 50:
        return "Low"
    else:
        return "Very Low"

def _calculate_profile_score(profile_info: Dict) -> int:
    """Calculate profile optimization score."""
    score = 0
    max_score = 100
    
    # Profile picture (10 points)
    if profile_info.get('profile_picture_url'):
        score += 10
    
    # Bio (20 points)
    bio = profile_info.get('bio', '')
    if bio:
        score += 10
        if len(bio) > 50:  # Detailed bio
            score += 10
    
    # Verification (15 points)
    if profile_info.get('is_verified'):
        score += 15
    
    # Post count (20 points)
    posts = profile_info.get('posts_count', 0)
    if posts >= 100:
        score += 20
    elif posts >= 50:
        score += 15
    elif posts >= 20:
        score += 10
    elif posts >= 5:
        score += 5
    
    # Follower ratio (20 points)
    ratio = profile_info.get('follower_following_ratio', 0)
    if ratio >= 10:
        score += 20
    elif ratio >= 5:
        score += 15
    elif ratio >= 2:
        score += 10
    elif ratio >= 1:
        score += 5
    
    # Profile name (15 points)
    if profile_info.get('profile_name'):
        score += 15
    
    return min(score, max_score)

def _calculate_bio_score(bio: str, hashtags: List[str]) -> int:
    """Calculate bio optimization score."""
    score = 0
    
    if not bio:
        return 0
    
    # Length score
    if 50 <= len(bio) <= 150:
        score += 30
    elif len(bio) > 0:
        score += 15
    
    # Has hashtags
    if hashtags:
        score += 25
    
    # Has link (basic check for common patterns)
    if any(pattern in bio.lower() for pattern in ['link', 'bio', '.com', 'www']):
        score += 25
    
    # Has contact info
    if any(pattern in bio.lower() for pattern in ['email', '@', 'contact', 'dm']):
        score += 20
    
    return min(score, 100)

def _generate_instagram_recommendations(profile_info: Dict, post_analysis: List[Dict]) -> List[str]:
    """Generate Instagram optimization recommendations."""
    recommendations = []
    
    # Profile optimization
    if not profile_info.get('profile_picture_url'):
        recommendations.append("Add a profile picture to improve recognition and trust.")
    
    bio = profile_info.get('bio', '')
    if not bio:
        recommendations.append("Add a bio to tell visitors about yourself or your brand.")
    elif len(bio) < 50:
        recommendations.append("Expand your bio with more details about what you do.")
    
    # Posting frequency
    posts_count = profile_info.get('posts_count', 0)
    if posts_count < 20:
        recommendations.append("Post more content regularly to keep your audience engaged.")
    
    # Follower strategy
    ratio = profile_info.get('follower_following_ratio', 0)
    if ratio < 0.5:
        recommendations.append("Consider following fewer accounts to improve your follower-to-following ratio.")
    
    # Post quality
    if post_analysis:
        avg_quality = sum(p['estimated_quality_score'] for p in post_analysis) / len(post_analysis)
        if avg_quality < 2:
            recommendations.append("Focus on higher quality content and add descriptive alt text to posts.")
    
    # Engagement
    followers = profile_info.get('followers_count', 0)
    if followers > 1000 and posts_count > 0:
        posts_per_follower = posts_count / followers
        if posts_per_follower < 0.01:
            recommendations.append("Increase posting frequency to maintain audience engagement.")
    
    return recommendations

def _generate_hashtag_recommendations(bio_hashtags: List[str], profile_info: Dict) -> List[str]:
    """Generate hashtag strategy recommendations."""
    recommendations = []
    
    if not bio_hashtags:
        recommendations.append("Add relevant hashtags to your bio to improve discoverability.")
    elif len(bio_hashtags) > 5:
        recommendations.append("Consider reducing bio hashtags to 3-5 most relevant ones.")
    
    # Check for branded hashtag
    username = profile_info.get('username', '').lower()
    has_branded = any(username in tag.lower() for tag in bio_hashtags)
    if not has_branded and profile_info.get('followers_count', 0) > 1000:
        recommendations.append("Consider creating and using a branded hashtag in your bio.")
    
    return recommendations

if __name__ == "__main__":
    mcp.run()