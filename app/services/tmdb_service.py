import requests
import time
from typing import Dict, Optional, List
from app.services.logging_service import LoggingService
from app.models.logs import TMDBLog, LogLevel

class TMDBService:
    def __init__(self):
        from app import current_app
        self.api_key = current_app.config['TMDB_API_KEY']
        self.base_url = 'https://api.themoviedb.org/3'
        self.language = current_app.config['TMDB_LANGUAGE']
        self.logger = LoggingService()
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.last_request_time = 0
        self.rate_limit_delay = 0.25  # 250ms between requests
    
    def search_content(self, title: str, content_type: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for content in TMDB"""
        start_time = time.time()
        
        # Check cache first
        cache_key = f"{title}_{content_type}_{year}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                self.logger.log_tmdb(
                    LogLevel.INFO,
                    f"Cache hit for: {title}",
                    search_query=title,
                    tmdb_id=cached_data['data'].get('id'),
                    match_type='cache',
                    cache_hit=True,
                    api_response_time=0.001
                )
                return cached_data['data']
        
        # Rate limiting
        self._rate_limit()
        
        try:
            if content_type == 'movie':
                result = self._search_movie(title, year)
            elif content_type in ['series', 'novela']:
                result = self._search_tv_show(title, year)
            else:
                result = None
            
            response_time = time.time() - start_time
            
            if result:
                # Cache the result
                self.cache[cache_key] = {
                    'data': result,
                    'timestamp': time.time()
                }
                
                self.logger.log_tmdb(
                    LogLevel.INFO,
                    f"Found TMDB match for: {title}",
                    search_query=title,
                    tmdb_id=result.get('id'),
                    match_type='exact' if self._is_exact_match(title, result) else 'fuzzy',
                    cache_hit=False,
                    api_response_time=response_time
                )
            else:
                self.logger.log_tmdb(
                    LogLevel.WARNING,
                    f"No TMDB match found for: {title}",
                    search_query=title,
                    match_type='failed',
                    cache_hit=False,
                    api_response_time=response_time
                )
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.log_tmdb(
                LogLevel.ERROR,
                f"TMDB API error for {title}: {str(e)}",
                search_query=title,
                match_type='error',
                cache_hit=False,
                api_response_time=response_time
            )
            return None
    
    def _search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for movies in TMDB"""
        params = {
            'api_key': self.api_key,
            'language': self.language,
            'query': title,
            'include_adult': False
        }
        
        if year:
            params['year'] = year
        
        response = requests.get(f"{self.base_url}/search/movie", params=params)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        if results:
            # Return the first (most relevant) result
            movie = results[0]
            return {
                'id': movie.get('id'),
                'title': movie.get('title'),
                'original_title': movie.get('original_title'),
                'overview': movie.get('overview'),
                'poster_path': movie.get('poster_path'),
                'release_date': movie.get('release_date'),
                'genre_ids': movie.get('genre_ids', []),
                'vote_average': movie.get('vote_average'),
                'vote_count': movie.get('vote_count'),
                'type': 'movie'
            }
        
        return None
    
    def _search_tv_show(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for TV shows in TMDB"""
        params = {
            'api_key': self.api_key,
            'language': self.language,
            'query': title,
            'include_adult': False
        }
        
        if year:
            params['first_air_date_year'] = year
        
        response = requests.get(f"{self.base_url}/search/tv", params=params)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        if results:
            # Return the first (most relevant) result
            show = results[0]
            return {
                'id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'overview': show.get('overview'),
                'poster_path': show.get('poster_path'),
                'first_air_date': show.get('first_air_date'),
                'genre_ids': show.get('genre_ids', []),
                'vote_average': show.get('vote_average'),
                'vote_count': show.get('vote_count'),
                'type': 'tv'
            }
        
        return None
    
    def get_genres(self, content_type: str = 'movie') -> List[Dict]:
        """Get list of genres for content type"""
        cache_key = f"genres_{content_type}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]['data']
        
        self._rate_limit()
        
        try:
            endpoint = 'genre/movie/list' if content_type == 'movie' else 'genre/tv/list'
            params = {
                'api_key': self.api_key,
                'language': self.language
            }
            
            response = requests.get(f"{self.base_url}/{endpoint}", params=params)
            response.raise_for_status()
            
            data = response.json()
            genres = data.get('genres', [])
            
            # Cache for longer (genres don't change often)
            self.cache[cache_key] = {
                'data': genres,
                'timestamp': time.time()
            }
            
            return genres
            
        except Exception as e:
            self.logger.log_tmdb(
                LogLevel.ERROR,
                f"Error fetching genres: {str(e)}",
                match_type='error'
            )
            return []
    
    def get_content_details(self, tmdb_id: int, content_type: str) -> Optional[Dict]:
        """Get detailed information about content"""
        cache_key = f"details_{content_type}_{tmdb_id}"
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['data']
        
        self._rate_limit()
        
        try:
            endpoint = 'movie' if content_type == 'movie' else 'tv'
            params = {
                'api_key': self.api_key,
                'language': self.language,
                'append_to_response': 'credits,images,videos'
            }
            
            response = requests.get(f"{self.base_url}/{endpoint}/{tmdb_id}", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Cache the result
            self.cache[cache_key] = {
                'data': data,
                'timestamp': time.time()
            }
            
            return data
            
        except Exception as e:
            self.logger.log_tmdb(
                LogLevel.ERROR,
                f"Error fetching details for {content_type} {tmdb_id}: {str(e)}",
                tmdb_id=tmdb_id,
                match_type='error'
            )
            return None
    
    def get_poster_url(self, poster_path: str, size: str = 'w500') -> str:
        """Get full poster URL"""
        if not poster_path:
            return ''
        
        base_url = 'https://image.tmdb.org/t/p'
        return f"{base_url}/{size}{poster_path}"
    
    def _is_exact_match(self, search_title: str, tmdb_result: Dict) -> bool:
        """Check if search result is an exact match"""
        tmdb_title = tmdb_result.get('title', '').lower()
        search_title = search_title.lower()
        
        # Simple exact match check
        return search_title == tmdb_title
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache),
            'cache_ttl': self.cache_ttl,
            'last_request_time': self.last_request_time
        }

