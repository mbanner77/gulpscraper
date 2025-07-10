"""
Cloud-compatible GULP scraper using requests instead of Playwright
================================================================
This module provides a lightweight alternative to Playwright-based scraping
for cloud environments where browser automation is not available.
"""

import requests
import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CloudGulpScraper:
    """
    Lightweight GULP scraper using HTTP requests instead of browser automation
    """
    
    def __init__(self):
        self.base_url = "https://www.gulp.de"
        self.api_url = f"{self.base_url}/gulp2/rest/internal/projects/search"
        self.session = requests.Session()
        
        # Set up realistic headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'{self.base_url}/gulp2/g/projekte',
            'Origin': self.base_url,
            'Content-Type': 'application/json',
        })
    
    async def scrape_projects(self, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        Scrape GULP projects using the REST API
        
        Args:
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of project dictionaries
        """
        all_projects = []
        
        try:
            for page in range(max_pages):
                logger.info(f"Scraping page {page + 1}/{max_pages}")
                
                # Request payload for the API (based on working GULP API structure)
                payload = {
                    "filter": {
                        "keywords": "",
                        "locations": [],
                        "skills": [],
                        "projectTypes": [],
                        "workload": [],
                        "duration": [],
                        "homeOffice": False,
                        "travel": False
                    },
                    "pagination": {
                        "page": page,
                        "size": 40
                    },
                    "sort": {
                        "field": "startDate",
                        "direction": "DESC"
                    }
                }
                
                try:
                    # Make the API request
                    response = self.session.post(
                        self.api_url,
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        logger.warning(f"API returned status {response.status_code} for page {page + 1}")
                        continue
                    
                    # Parse the JSON response
                    data = response.json()
                    
                    if not isinstance(data, dict) or 'projects' not in data:
                        logger.warning(f"Unexpected API response format on page {page + 1}")
                        continue
                    
                    projects = data.get('projects', [])
                    total_count = data.get('totalCount', 0)
                    
                    logger.info(f"Found {len(projects)} projects on page {page + 1}, total: {total_count}")
                    
                    if not projects:
                        logger.info("No more projects found, stopping pagination")
                        break
                    
                    # Process and add projects
                    for project in projects:
                        processed_project = self._process_project(project)
                        if processed_project:
                            all_projects.append(processed_project)
                    
                    # If we got fewer projects than expected, we might be at the end
                    if len(projects) < 40:
                        logger.info("Got fewer than 40 projects, likely at end of results")
                        break
                        
                    # Be nice to the server
                    await self._sleep_random(1, 3)
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout on page {page + 1}")
                    continue
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request error on page {page + 1}: {e}")
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error on page {page + 1}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")
        
        logger.info(f"Scraping completed. Total projects found: {len(all_projects)}")
        return all_projects
    
    def _process_project(self, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single project from the API response
        
        Args:
            project: Raw project data from API
            
        Returns:
            Processed project dictionary or None if invalid
        """
        try:
            # Extract basic fields
            project_id = project.get('id', '')
            title = project.get('title', '').strip()
            
            if not project_id or not title:
                return None
            
            # Build processed project
            processed = {
                'id': project_id,
                'title': title,
                'location': project.get('location', ''),
                'type': project.get('type', ''),
                'client': project.get('client', ''),
                'description': project.get('description', ''),
                'skills': project.get('skills', []),
                'start_date': project.get('startDate', ''),
                'duration': project.get('duration', ''),
                'remote_work': project.get('remoteWork', False),
                'url': f"{self.base_url}/gulp2/g/projekte/{project_id}",
                'scraped_at': time.time(),
                'scraper_version': 'cloud_v1.0'
            }
            
            return processed
            
        except Exception as e:
            logger.warning(f"Error processing project {project.get('id', 'unknown')}: {e}")
            return None
    
    async def _sleep_random(self, min_seconds: float, max_seconds: float):
        """Sleep for a random amount of time"""
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)
    
    def test_connection(self) -> bool:
        """
        Test if the GULP API is accessible
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try a simple request to get one project
            payload = {
                "filter": {
                    "keywords": "",
                    "locations": [],
                    "skills": [],
                    "projectTypes": [],
                    "workload": [],
                    "duration": [],
                    "homeOffice": False,
                    "travel": False
                },
                "pagination": {
                    "page": 0,
                    "size": 1
                },
                "sort": {
                    "field": "startDate",
                    "direction": "DESC"
                }
            }
            
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'projects' in data:
                    logger.info("Cloud scraper connection test successful")
                    return True
            
            logger.warning(f"Connection test failed: status {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False

# Factory function for creating the appropriate scraper
def create_scraper() -> CloudGulpScraper:
    """Create and return a cloud-compatible scraper instance"""
    return CloudGulpScraper()

# Async wrapper for backward compatibility
async def scrape_gulp_cloud(max_pages: int = 5) -> List[Dict[str, Any]]:
    """
    Cloud-compatible scraper function
    
    Args:
        max_pages: Maximum pages to scrape
        
    Returns:
        List of scraped projects
    """
    scraper = create_scraper()
    
    # Test connection first
    if not scraper.test_connection():
        logger.error("Unable to connect to GULP API")
        return []
    
    return await scraper.scrape_projects(max_pages)
