#!/usr/bin/env python3
"""
YouTube Audit MCP Server
A minimal MCP server for YouTube channel and video auditing using YouTube Data API.
"""

import os
import re
import asyncio
import ssl
import certifi
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiohttp
from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("YouTube Audit")

class YouTubeAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to YouTube API."""
        params['key'] = self.api_key
        
        # Create SSL context with proper certificate verification using certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(f"{self.base_url}/{endpoint}", params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"YouTube API error {response.status}: {error_text}")
    
    def extract_channel_id(self, channel_input: str) -> str:
        """Extract channel ID from various YouTube URL formats or handle."""
        # If it's already a channel ID (starts with UC)
        if channel_input.startswith('UC') and len(channel_input) == 24:
            return channel_input
        
        # Extract from YouTube URLs
        patterns = [
            r'youtube\.com/channel/([^/?]+)',
            r'youtube\.com/c/([^/?]+)',
            r'youtube\.com/user/([^/?]+)',
            r'youtube\.com/@([^/?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, channel_input)
            if match:
                return match.group(1)
        
        # If it's just a handle/username, return as is
        return channel_input
    
    def extract_video_id(self, video_input: str) -> str:
        """Extract video ID from YouTube URL or return if already an ID."""
        # If it's already a video ID
        if len(video_input) == 11 and not '/' in video_input:
            return video_input
        
        # Extract from YouTube URLs
        patterns = [
            r'youtube\.com/watch\?v=([^&]+)',
            r'youtu\.be/([^?]+)',
            r'youtube\.com/embed/([^?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_input)
            if match:
                return match.group(1)
        
        return video_input

def get_youtube_api():
    """Get YouTube API instance with API key from environment."""
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        raise Exception("YOUTUBE_API_KEY environment variable not set")
    return YouTubeAPI(api_key)

@mcp.tool()
async def get_channel_stats(channel_input: str) -> Dict[str, Any]:
    """
    Get comprehensive channel statistics and metadata.
    
    Args:
        channel_input: Channel ID, channel URL, or handle (e.g., @channelname)
        
    Returns:
        Dictionary containing channel statistics
    """
    try:
        youtube = get_youtube_api()
        channel_identifier = youtube.extract_channel_id(channel_input)
        
        # First, try to get channel by ID
        try:
            data = await youtube._make_request('channels', {
                'part': 'snippet,statistics,brandingSettings,status',
                'id': channel_identifier
            })
        except:
            # If that fails, try by username/handle
            data = await youtube._make_request('channels', {
                'part': 'snippet,statistics,brandingSettings,status',
                'forUsername': channel_identifier
            })
        
        if not data.get('items'):
            return {"error": f"Channel not found: {channel_input}"}
        
        channel = data['items'][0]
        snippet = channel['snippet']
        stats = channel['statistics']
        
        # Parse dates
        created_date = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
        days_active = (datetime.now() - created_date.replace(tzinfo=None)).days
        
        return {
            "channel_id": channel['id'],
            "title": snippet['title'],
            "description": snippet.get('description', '')[:500] + "..." if len(snippet.get('description', '')) > 500 else snippet.get('description', ''),
            "created_date": created_date.strftime('%Y-%m-%d'),
            "days_active": days_active,
            "country": snippet.get('country', 'Not specified'),
            "subscriber_count": int(stats.get('subscriberCount', 0)),
            "video_count": int(stats.get('videoCount', 0)),
            "view_count": int(stats.get('viewCount', 0)),
            "avg_views_per_video": round(int(stats.get('viewCount', 0)) / max(int(stats.get('videoCount', 1)), 1)),
            "uploads_per_month": round((int(stats.get('videoCount', 0)) / max(days_active, 1)) * 30, 1),
            "custom_url": snippet.get('customUrl', 'Not set'),
            "thumbnail_url": snippet['thumbnails'].get('high', {}).get('url', ''),
            "hidden_subscriber_count": not stats.get('hiddenSubscriberCount', True)
        }
        
    except Exception as e:
        return {"error": f"Error getting channel stats: {str(e)}"}

@mcp.tool()
async def get_recent_videos(channel_input: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Get recent videos from a channel with basic metadata.
    
    Args:
        channel_input: Channel ID, channel URL, or handle
        max_results: Number of recent videos to fetch (default: 10, max: 50)
        
    Returns:
        Dictionary containing recent videos data
    """
    try:
        youtube = get_youtube_api()
        channel_identifier = youtube.extract_channel_id(channel_input)
        
        # Get channel ID first
        try:
            channel_data = await youtube._make_request('channels', {
                'part': 'id',
                'id': channel_identifier
            })
        except:
            channel_data = await youtube._make_request('channels', {
                'part': 'id',
                'forUsername': channel_identifier
            })
        
        if not channel_data.get('items'):
            return {"error": f"Channel not found: {channel_input}"}
        
        channel_id = channel_data['items'][0]['id']
        
        # Get recent videos
        search_data = await youtube._make_request('search', {
            'part': 'id,snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'date',
            'maxResults': min(max_results, 50)
        })
        
        videos = []
        for item in search_data.get('items', []):
            video_info = {
                "video_id": item['id']['videoId'],
                "title": item['snippet']['title'],
                "description": item['snippet']['description'][:200] + "..." if len(item['snippet']['description']) > 200 else item['snippet']['description'],
                "published_at": item['snippet']['publishedAt'],
                "thumbnail_url": item['snippet']['thumbnails'].get('medium', {}).get('url', '')
            }
            videos.append(video_info)
        
        return {
            "channel_id": channel_id,
            "total_results": len(videos),
            "videos": videos
        }
        
    except Exception as e:
        return {"error": f"Error getting recent videos: {str(e)}"}

@mcp.tool()
async def evaluate_video_metadata(video_input: str) -> Dict[str, Any]:
    """
    Analyze video metadata for SEO optimization.
    
    Args:
        video_input: Video ID or YouTube video URL
        
    Returns:
        Dictionary containing video metadata analysis
    """
    try:
        youtube = get_youtube_api()
        video_id = youtube.extract_video_id(video_input)
        
        # Get video details
        data = await youtube._make_request('videos', {
            'part': 'snippet,statistics,contentDetails,status',
            'id': video_id
        })
        
        if not data.get('items'):
            return {"error": f"Video not found: {video_input}"}
        
        video = data['items'][0]
        snippet = video['snippet']
        stats = video['statistics']
        content_details = video['contentDetails']
        
        # Analyze title
        title = snippet['title']
        title_analysis = {
            "length": len(title),
            "optimal_length": 60 <= len(title) <= 70,
            "has_keywords": bool(re.search(r'\b(how to|tutorial|review|vs|best)\b', title.lower())),
            "has_numbers": bool(re.search(r'\d+', title)),
            "has_caps": any(c.isupper() for c in title)
        }
        
        # Analyze description
        description = snippet.get('description', '')
        desc_analysis = {
            "length": len(description),
            "optimal_length": len(description) >= 200,
            "has_links": bool(re.search(r'http[s]?://', description)),
            "has_timestamps": bool(re.search(r'\d{1,2}:\d{2}', description)),
            "has_hashtags": bool(re.search(r'#\w+', description))
        }
        
        # Parse duration
        duration = content_details.get('duration', 'PT0S')
        duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if duration_match:
            hours = int(duration_match.group(1) or 0)
            minutes = int(duration_match.group(2) or 0)
            seconds = int(duration_match.group(3) or 0)
            total_seconds = hours * 3600 + minutes * 60 + seconds
            duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
        else:
            total_seconds = 0
            duration_formatted = "00:00"
        
        return {
            "video_id": video_id,
            "title": title,
            "title_analysis": title_analysis,
            "description_analysis": desc_analysis,
            "tags": snippet.get('tags', []),
            "tag_count": len(snippet.get('tags', [])),
            "category_id": snippet.get('categoryId'),
            "duration": duration_formatted,
            "duration_seconds": total_seconds,
            "published_at": snippet['publishedAt'],
            "view_count": int(stats.get('viewCount', 0)),
            "like_count": int(stats.get('likeCount', 0)),
            "comment_count": int(stats.get('commentCount', 0)),
            "engagement_rate": round((int(stats.get('likeCount', 0)) + int(stats.get('commentCount', 0))) / max(int(stats.get('viewCount', 1)), 1) * 100, 3),
            "thumbnail_url": snippet['thumbnails'].get('maxres', snippet['thumbnails'].get('high', {})).get('url', ''),
            "is_live": content_details.get('duration') == 'PT0S'
        }
        
    except Exception as e:
        return {"error": f"Error evaluating video metadata: {str(e)}"}

@mcp.tool()
async def analyze_channel_performance(channel_input: str, days_back: int = 30) -> Dict[str, Any]:
    """
    Analyze channel performance trends over a specified period.
    
    Args:
        channel_input: Channel ID, channel URL, or handle
        days_back: Number of days to analyze (default: 30)
        
    Returns:
        Dictionary containing performance analysis
    """
    try:
        youtube = get_youtube_api()
        channel_identifier = youtube.extract_channel_id(channel_input)
        
        # Get channel ID
        try:
            channel_data = await youtube._make_request('channels', {
                'part': 'id',
                'id': channel_identifier
            })
        except:
            channel_data = await youtube._make_request('channels', {
                'part': 'id',
                'forUsername': channel_identifier
            })
        
        if not channel_data.get('items'):
            return {"error": f"Channel not found: {channel_input}"}
        
        channel_id = channel_data['items'][0]['id']
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Get videos from the specified period
        search_data = await youtube._make_request('search', {
            'part': 'id,snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'date',
            'maxResults': 50,
            'publishedAfter': start_date.isoformat() + 'Z'
        })
        
        if not search_data.get('items'):
            return {
                "channel_id": channel_id,
                "period_days": days_back,
                "videos_published": 0,
                "avg_upload_frequency": 0,
                "message": "No videos found in the specified period"
            }
        
        # Get detailed stats for these videos
        video_ids = [item['id']['videoId'] for item in search_data['items']]
        video_stats_data = await youtube._make_request('videos', {
            'part': 'statistics,contentDetails',
            'id': ','.join(video_ids)
        })
        
        # Analyze performance
        total_views = 0
        total_likes = 0
        total_comments = 0
        video_count = len(video_stats_data.get('items', []))
        
        for video in video_stats_data.get('items', []):
            stats = video['statistics']
            total_views += int(stats.get('viewCount', 0))
            total_likes += int(stats.get('likeCount', 0))
            total_comments += int(stats.get('commentCount', 0))
        
        avg_views = total_views / video_count if video_count > 0 else 0
        avg_likes = total_likes / video_count if video_count > 0 else 0
        avg_comments = total_comments / video_count if video_count > 0 else 0
        avg_engagement = ((total_likes + total_comments) / max(total_views, 1)) * 100
        
        upload_frequency = video_count / days_back * 7  # Videos per week
        
        return {
            "channel_id": channel_id,
            "period_days": days_back,
            "videos_published": video_count,
            "avg_upload_frequency_per_week": round(upload_frequency, 1),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_views_per_video": round(avg_views),
            "avg_likes_per_video": round(avg_likes),
            "avg_comments_per_video": round(avg_comments),
            "avg_engagement_rate": round(avg_engagement, 3),
            "performance_rating": _rate_performance(avg_views, avg_engagement, upload_frequency)
        }
        
    except Exception as e:
        return {"error": f"Error analyzing channel performance: {str(e)}"}

@mcp.tool()
async def get_video_seo_score(video_input: str) -> Dict[str, Any]:
    """
    Calculate SEO score for a YouTube video based on optimization factors.
    
    Args:
        video_input: Video ID or YouTube video URL
        
    Returns:
        Dictionary containing SEO analysis and score
    """
    try:
        # Get video metadata first
        video_data = await evaluate_video_metadata(video_input)
        
        if 'error' in video_data:
            return video_data
        
        score_factors = {}
        total_score = 0
        max_score = 0
        
        # Title optimization (25 points)
        title_analysis = video_data['title_analysis']
        title_score = 0
        if title_analysis['optimal_length']:
            title_score += 10
        if title_analysis['has_keywords']:
            title_score += 8
        if title_analysis['has_numbers']:
            title_score += 4
        if title_analysis['has_caps']:
            title_score += 3
        
        score_factors['title_score'] = title_score
        total_score += title_score
        max_score += 25
        
        # Description optimization (20 points)
        desc_analysis = video_data['description_analysis']
        desc_score = 0
        if desc_analysis['optimal_length']:
            desc_score += 8
        if desc_analysis['has_links']:
            desc_score += 4
        if desc_analysis['has_timestamps']:
            desc_score += 4
        if desc_analysis['has_hashtags']:
            desc_score += 4
        
        score_factors['description_score'] = desc_score
        total_score += desc_score
        max_score += 20
        
        # Tags optimization (15 points)
        tag_count = video_data['tag_count']
        if tag_count >= 5:
            tag_score = 15
        elif tag_count >= 3:
            tag_score = 10
        elif tag_count >= 1:
            tag_score = 5
        else:
            tag_score = 0
        
        score_factors['tags_score'] = tag_score
        total_score += tag_score
        max_score += 15
        
        # Engagement optimization (20 points)
        engagement_rate = video_data['engagement_rate']
        if engagement_rate >= 5:
            engagement_score = 20
        elif engagement_rate >= 2:
            engagement_score = 15
        elif engagement_rate >= 1:
            engagement_score = 10
        elif engagement_rate >= 0.5:
            engagement_score = 5
        else:
            engagement_score = 0
        
        score_factors['engagement_score'] = engagement_score
        total_score += engagement_score
        max_score += 20
        
        # Duration optimization (10 points)
        duration_seconds = video_data['duration_seconds']
        if 300 <= duration_seconds <= 600:  # 5-10 minutes
            duration_score = 10
        elif 180 <= duration_seconds <= 900:  # 3-15 minutes
            duration_score = 8
        elif 60 <= duration_seconds <= 1200:  # 1-20 minutes
            duration_score = 5
        else:
            duration_score = 2
        
        score_factors['duration_score'] = duration_score
        total_score += duration_score
        max_score += 10
        
        # Thumbnail (10 points - we can only check if it exists)
        thumbnail_score = 10 if video_data['thumbnail_url'] else 0
        score_factors['thumbnail_score'] = thumbnail_score
        total_score += thumbnail_score
        max_score += 10
        
        final_score = (total_score / max_score) * 100
        
        return {
            "video_id": video_data['video_id'],
            "title": video_data['title'],
            "seo_score": round(final_score, 1),
            "score_breakdown": score_factors,
            "recommendations": _generate_video_recommendations(video_data, score_factors),
            "max_possible_score": max_score,
            "achieved_score": total_score
        }
        
    except Exception as e:
        return {"error": f"Error calculating SEO score: {str(e)}"}

@mcp.tool()
async def compare_channels(channel_inputs: List[str]) -> Dict[str, Any]:
    """
    Compare multiple YouTube channels side by side.
    
    Args:
        channel_inputs: List of channel IDs, URLs, or handles to compare
        
    Returns:
        Dictionary containing channel comparison
    """
    try:
        if len(channel_inputs) > 5:
            return {"error": "Maximum 5 channels can be compared at once"}
        
        # Get stats for all channels
        tasks = [get_channel_stats(channel) for channel in channel_inputs]
        results = await asyncio.gather(*tasks)
        
        # Filter out errors
        valid_channels = [result for result in results if 'error' not in result]
        errors = [result for result in results if 'error' in result]
        
        if not valid_channels:
            return {"error": "No valid channels found", "individual_errors": errors}
        
        # Create comparison
        comparison = {
            "channels_compared": len(valid_channels),
            "channels": valid_channels,
            "comparison_metrics": {
                "highest_subscribers": max(valid_channels, key=lambda x: x['subscriber_count']),
                "most_videos": max(valid_channels, key=lambda x: x['video_count']),
                "highest_total_views": max(valid_channels, key=lambda x: x['view_count']),
                "best_avg_views": max(valid_channels, key=lambda x: x['avg_views_per_video']),
                "most_active": max(valid_channels, key=lambda x: x['uploads_per_month'])
            },
            "ranking_by_subscribers": sorted(valid_channels, key=lambda x: x['subscriber_count'], reverse=True)
        }
        
        if errors:
            comparison["errors"] = errors
        
        return comparison
        
    except Exception as e:
        return {"error": f"Error comparing channels: {str(e)}"}

def _rate_performance(avg_views: float, engagement_rate: float, upload_frequency: float) -> str:
    """Rate overall channel performance."""
    score = 0
    
    # Views score
    if avg_views >= 100000:
        score += 3
    elif avg_views >= 10000:
        score += 2
    elif avg_views >= 1000:
        score += 1
    
    # Engagement score
    if engagement_rate >= 3:
        score += 3
    elif engagement_rate >= 1:
        score += 2
    elif engagement_rate >= 0.5:
        score += 1
    
    # Consistency score
    if upload_frequency >= 2:
        score += 2
    elif upload_frequency >= 1:
        score += 1
    
    if score >= 7:
        return "Excellent"
    elif score >= 5:
        return "Good"
    elif score >= 3:
        return "Average"
    else:
        return "Needs Improvement"

def _generate_video_recommendations(video_data: Dict, score_factors: Dict) -> List[str]:
    """Generate optimization recommendations for a video."""
    recommendations = []
    
    # Title recommendations
    if score_factors['title_score'] < 20:
        title_analysis = video_data['title_analysis']
        if not title_analysis['optimal_length']:
            recommendations.append("Optimize title length to 60-70 characters for better visibility.")
        if not title_analysis['has_keywords']:
            recommendations.append("Include relevant keywords like 'how to', 'tutorial', 'review' in title.")
        if not title_analysis['has_numbers']:
            recommendations.append("Consider adding numbers to title for higher click-through rates.")
    
    # Description recommendations
    if score_factors['description_score'] < 15:
        desc_analysis = video_data['description_analysis']
        if not desc_analysis['optimal_length']:
            recommendations.append("Expand description to at least 200 characters for better SEO.")
        if not desc_analysis['has_timestamps']:
            recommendations.append("Add timestamps to improve user experience and retention.")
        if not desc_analysis['has_links']:
            recommendations.append("Include relevant links in description (social media, website, related videos).")
    
    # Tags recommendations
    if score_factors['tags_score'] < 10:
        recommendations.append(f"Add more tags (currently {video_data['tag_count']}, aim for 5-10 relevant tags).")
    
    # Engagement recommendations
    if score_factors['engagement_score'] < 15:
        recommendations.append("Improve engagement by asking questions, adding call-to-actions, and encouraging comments.")
    
    # Duration recommendations
    if score_factors['duration_score'] < 8:
        duration = video_data['duration_seconds']
        if duration < 180:
            recommendations.append("Consider longer content (5-10 minutes) for better algorithm performance.")
        elif duration > 1200:
            recommendations.append("Consider shorter, more focused content for better retention.")
    
    return recommendations

if __name__ == "__main__":
    mcp.run()