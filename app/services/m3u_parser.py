import re
import os
from typing import List, Dict, Set, Optional
from datetime import datetime
from app.models.downloads import Download, DownloadPriority
from app.models.servers import Server
from app.services.tmdb_service import TMDBService
from app.services.logging_service import LoggingService

class M3UParser:
    def __init__(self):
        self.tmdb_service = TMDBService()
        self.logger = LoggingService()
    
    def parse_m3u_file(self, file_path: str) -> List[Dict]:
        """Parse M3U file and extract content information"""
        content_items = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            current_item = {}
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('#EXTINF:'):
                    # Parse EXTINF line
                    current_item = self._parse_extinf_line(line)
                elif line.startswith('http'):
                    # URL line
                    if current_item:
                        current_item['url'] = line
                        content_items.append(current_item)
                        current_item = {}
        
        except Exception as e:
            self.logger.log_system('error', f'Error parsing M3U file: {str(e)}', 
                                 details={'file_path': file_path})
            raise
        
        return content_items
    
    def _parse_extinf_line(self, line: str) -> Dict:
        """Parse EXTINF line to extract metadata"""
        # Remove #EXTINF: prefix
        line = line.replace('#EXTINF:', '')
        
        # Extract duration and title
        duration_match = re.match(r'-?\d+', line)
        duration = int(duration_match.group()) if duration_match else 0
        
        # Extract title (everything after duration and comma)
        title_part = line.split(',', 1)[1] if ',' in line else line
        
        # Parse additional attributes
        attributes = {}
        attr_pattern = r'(\w+)="([^"]*)"'
        for match in re.finditer(attr_pattern, line):
            attributes[match.group(1)] = match.group(2)
        
        # Extract content information
        content_info = self._extract_content_info(title_part)
        
        return {
            'duration': duration,
            'title': content_info['title'],
            'original_title': title_part,
            'content_type': content_info['content_type'],
            'season': content_info['season'],
            'episode': content_info['episode'],
            'episode_title': content_info['episode_title'],
            'year': content_info['year'],
            'quality': content_info['quality'],
            'attributes': attributes
        }
    
    def _extract_content_info(self, title: str) -> Dict:
        """Extract content information from title"""
        # Remove common prefixes/suffixes
        title = re.sub(r'^\d+\.\s*', '', title)  # Remove numbering
        title = re.sub(r'\[.*?\]', '', title)    # Remove brackets
        title = re.sub(r'\(.*?\)', '', title)    # Remove parentheses
        title = title.strip()
        
        # Extract year
        year_match = re.search(r'\((\d{4})\)', title)
        year = int(year_match.group(1)) if year_match else None
        
        # Extract quality
        quality_patterns = [
            r'(\d{3,4}p)',  # 480p, 720p, 1080p, 4K
            r'(HD|SD|FHD|UHD)',
            r'(720|1080|2160)'
        ]
        
        quality = '480p'  # Default quality
        for pattern in quality_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                quality = match.group(1).upper()
                break
        
        # Determine content type and extract season/episode
        content_type = 'movie'
        season = None
        episode = None
        episode_title = None
        
        # Series patterns
        series_patterns = [
            r'S(\d{1,2})E(\d{1,2})',  # S01E01
            r'(\d{1,2})x(\d{1,2})',   # 1x01
            r'Temporada\s*(\d{1,2})\s*Episódio\s*(\d{1,2})',  # Temporada 1 Episódio 1
        ]
        
        for pattern in series_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                content_type = 'series'
                season = int(match.group(1))
                episode = int(match.group(2))
                
                # Extract episode title
                episode_title_match = re.search(r'-\s*(.+?)(?:\s*-\s*|$)', title)
                if episode_title_match:
                    episode_title = episode_title_match.group(1).strip()
                break
        
        # Novela patterns
        novela_patterns = [
            r'Capítulo\s*(\d{1,3})',
            r'Episódio\s*(\d{1,3})',
        ]
        
        for pattern in novela_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                content_type = 'novela'
                episode = int(match.group(1))
                break
        
        # Clean title
        clean_title = re.sub(r'S\d{1,2}E\d{1,2}|\d{1,2}x\d{1,2}', '', title)
        clean_title = re.sub(r'Capítulo\s*\d{1,3}|Episódio\s*\d{1,3}', '', clean_title)
        clean_title = re.sub(r'\(.*?\)', '', clean_title)
        clean_title = re.sub(r'\[.*?\]', '', clean_title)
        clean_title = re.sub(r'-\s*.*$', '', clean_title)
        clean_title = clean_title.strip()
        
        return {
            'title': clean_title,
            'content_type': content_type,
            'season': season,
            'episode': episode,
            'episode_title': episode_title,
            'year': year,
            'quality': quality
        }
    
    def compare_m3u_lists(self, main_list_path: str, new_list_path: str) -> List[Dict]:
        """Compare two M3U lists and return items not in main list"""
        main_items = self.parse_m3u_file(main_list_path)
        new_items = self.parse_m3u_file(new_list_path)
        
        # Create set of main list items for fast lookup
        main_set = set()
        for item in main_items:
            key = self._create_item_key(item)
            main_set.add(key)
        
        # Find items not in main list
        new_items_only = []
        for item in new_items:
            key = self._create_item_key(item)
            if key not in main_set:
                # Apply quality filter
                if self._is_acceptable_quality(item['quality']):
                    new_items_only.append(item)
                else:
                    self.logger.log_system('info', f'Item filtered out due to quality: {item["title"]} ({item["quality"]})')
        
        return new_items_only
    
    def _create_item_key(self, item: Dict) -> str:
        """Create a unique key for item comparison"""
        if item['content_type'] == 'series':
            return f"{item['title']}_{item['season']}_{item['episode']}"
        elif item['content_type'] == 'novela':
            return f"{item['title']}_{item['episode']}"
        else:
            return f"{item['title']}_{item['year']}"
    
    def _is_acceptable_quality(self, quality: str) -> bool:
        """Check if quality is acceptable"""
        from app import current_app
        accepted_qualities = current_app.config['ACCEPTED_QUALITIES']
        
        # Normalize quality
        quality = quality.upper()
        if quality.endswith('P'):
            quality = quality.lower()
        
        return quality in accepted_qualities
    
    def suggest_server_and_directory(self, content_item: Dict, servers: List[Server]) -> Dict:
        """Suggest appropriate server and directory for content"""
        content_type = content_item['content_type']
        
        # Find servers that support this content type
        suitable_servers = [s for s in servers if s.supports_content_type(content_type)]
        
        if not suitable_servers:
            return {'server': None, 'directory': None, 'error': 'No suitable server found'}
        
        # Get TMDB data for better suggestions
        tmdb_data = self.tmdb_service.search_content(
            content_item['title'], 
            content_type, 
            content_item.get('year')
        )
        
        # Select best server (for now, just pick the first suitable one)
        selected_server = suitable_servers[0]
        
        # Get directory suggestion
        directory = selected_server.get_directory_for_content(
            content_type,
            content_item['title'],
            content_item.get('season'),
            content_item.get('episode')
        )
        
        return {
            'server': selected_server,
            'directory': directory,
            'tmdb_data': tmdb_data
        }
    
    def create_download_objects(self, content_items: List[Dict], user_id: int) -> List[Download]:
        """Create Download objects from content items"""
        downloads = []
        
        for item in content_items:
            # Determine priority based on content type and year
            priority = self._determine_priority(item)
            
            # Create download object (server and destination will be set later)
            download = Download(
                title=item['title'],
                content_type=item['content_type'],
                quality=item['quality'],
                url=item['url'],
                server_id=1,  # Will be updated when server is selected
                destination_path='',  # Will be updated when directory is selected
                user_id=user_id,
                season=item.get('season'),
                episode=item.get('episode'),
                episode_title=item.get('episode_title'),
                year=item.get('year'),
                priority=priority
            )
            
            downloads.append(download)
        
        return downloads
    
    def _determine_priority(self, item: Dict) -> DownloadPriority:
        """Determine download priority based on content characteristics"""
        current_year = datetime.now().year
        
        # High priority: Recent movies (last 2 years)
        if item['content_type'] == 'movie' and item.get('year'):
            if current_year - item['year'] <= 2:
                return DownloadPriority.HIGH
        
        # Medium priority: Series and older movies
        if item['content_type'] in ['series', 'novela']:
            return DownloadPriority.MEDIUM
        
        # Low priority: Old content
        if item.get('year') and current_year - item['year'] > 5:
            return DownloadPriority.LOW
        
        return DownloadPriority.MEDIUM

