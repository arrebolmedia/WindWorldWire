"""Enhanced RSS/Atom feed fetching with proper ETag and If-Modified-Since handling."""

import asyncio
import feedparser
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, NamedTuple
from urllib.parse import urljoin, urlparse
from email.utils import formatdate, parsedate_to_datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from newsbot.core.logging import get_logger

logger = get_logger(__name__)


class FetchResult(NamedTuple):
    """Result of RSS feed fetch operation."""
    status_code: int
    feed: Optional[Any] = None  # feedparser.FeedParserDict
    etag: Optional[str] = None
    last_modified: Optional[datetime] = None
    error: Optional[str] = None


class RSSFetcher:
    """Enhanced RSS/Atom fetcher with proper conditional caching, concurrency, and retry logic."""
    
    def __init__(self, timeout: float = 10.0, max_retries: int = 4, max_concurrent: int = 8):
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "NewsBot/1.0 (WindWorldWire RSS Reader; +https://windworldwire.com/bot)"
            },
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0
            )
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _build_conditional_headers(
        self, 
        etag: Optional[str] = None, 
        last_modified: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Build conditional headers for caching according to HTTP specifications.
        
        Args:
            etag: ETag value from previous response
            last_modified: Last-Modified datetime from previous response
            
        Returns:
            Dictionary of conditional headers
        """
        headers = {}
        
        # Add If-None-Match header if ETag exists
        if etag:
            headers["If-None-Match"] = etag
            logger.debug(f"Added If-None-Match: {etag}")
        
        # Add If-Modified-Since header if Last-Modified exists
        if last_modified:
            # Convert datetime to RFC1123 format as required by HTTP spec
            if isinstance(last_modified, datetime):
                rfc1123_date = formatdate(last_modified.timestamp(), usegmt=True)
            else:
                # Handle string format (should be rare)
                rfc1123_date = str(last_modified)
            
            headers["If-Modified-Since"] = rfc1123_date
            logger.debug(f"Added If-Modified-Since: {rfc1123_date}")
        
        return headers
    
    def _parse_last_modified_header(self, header_value: str) -> Optional[datetime]:
        """
        Parse Last-Modified header with clock skew protection.
        
        If server time is in the future, clamp to current time to handle clock skew.
        
        Args:
            header_value: Last-Modified header value
            
        Returns:
            Parsed datetime in UTC, or None if parsing fails
        """
        try:
            # Parse the RFC1123 date
            dt = parsedate_to_datetime(header_value)
            
            # Ensure it's in UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            
            # Handle clock skew: if server time > now, use now
            now = datetime.now(timezone.utc)
            if dt > now:
                logger.warning(
                    f"Server Last-Modified is in future ({dt}), clamping to now ({now})"
                )
                dt = now
            
            return dt
            
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Failed to parse Last-Modified header '{header_value}': {e}")
            return None
    
    def _extract_response_headers(self, response: httpx.Response) -> tuple[Optional[str], Optional[datetime]]:
        """
        Extract ETag and Last-Modified from response headers.
        
        Args:
            response: HTTP response object
            
        Returns:
            Tuple of (etag, last_modified_datetime)
        """
        # Extract ETag (can be quoted or unquoted)
        etag = response.headers.get("ETag")
        if etag:
            etag = etag.strip()
        
        # Extract and parse Last-Modified
        last_modified = None
        last_modified_header = response.headers.get("Last-Modified")
        if last_modified_header:
            last_modified = self._parse_last_modified_header(last_modified_header)
        
        return etag, last_modified
    
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)),
        reraise=True
    )
    async def _fetch_with_retry(self, url: str, headers: Dict[str, str]) -> httpx.Response:
        """
        Fetch URL with exponential backoff retry and Retry-After header support.
        
        Args:
            url: URL to fetch
            headers: Request headers including conditional headers
            
        Returns:
            HTTP response object
        """
        try:
            logger.debug(f"Fetching {url} with headers: {list(headers.keys())}")
            response = await self.client.get(url, headers=headers)
            
            # Handle rate limiting with Retry-After header
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                        if wait_time > 0 and wait_time <= 60:  # Cap at 60 seconds
                            logger.info(f"Rate limited (429), waiting {wait_time}s as per Retry-After header")
                            await asyncio.sleep(wait_time)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid Retry-After header value: {retry_after}")
                
                logger.warning(f"Rate limited (429) for {url}, will retry with exponential backoff")
                response.raise_for_status()
            
            # Retry on server errors
            if response.status_code in (500, 502, 503, 504):
                logger.warning(f"Server error {response.status_code} for {url}, will retry")
                response.raise_for_status()
            
            return response
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 500, 502, 503, 504):
                logger.warning(f"Retryable HTTP error {e.response.status_code} for {url}")
                raise
            else:
                logger.error(f"Non-retryable HTTP error {e.response.status_code} for {url}")
                raise
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            logger.warning(f"Network/timeout error for {url}: {type(e).__name__}, will retry")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise
    
    async def fetch(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[datetime] = None
    ) -> FetchResult:
        """
        Fetch RSS feed with conditional caching support and concurrency control.
        
        Implements proper ETag and If-Modified-Since handling:
        - Sends If-None-Match if ETag provided
        - Sends If-Modified-Since if Last-Modified provided  
        - Handles 304 responses (no re-parsing)
        - Handles 200 responses (parse and update headers)
        - Manages clock skew for Last-Modified dates
        - Uses semaphore to limit concurrent requests
        - Implements retry with exponential backoff
        
        Args:
            url: RSS feed URL
            etag: Previous ETag value for conditional request
            last_modified: Previous Last-Modified datetime for conditional request
            
        Returns:
            FetchResult with status code, parsed feed, and updated headers
        """
        async with self.semaphore:  # Limit concurrent requests
            return await self._fetch_internal(url, etag, last_modified)
    
    async def _fetch_internal(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[datetime] = None
    ) -> FetchResult:
        """
        Internal fetch implementation with retry logic.
        """
        try:
            logger.info(f"Fetching RSS feed: {url}")
            
            # Build conditional headers for caching
            conditional_headers = self._build_conditional_headers(etag, last_modified)
            
            # Fetch with retry logic
            response = await self._fetch_with_retry(url, conditional_headers)
            
            # Handle 304 Not Modified - no re-parsing needed
            if response.status_code == 304:
                logger.info(f"Feed not modified (304): {url}")
                return FetchResult(
                    status_code=304,
                    feed=None,  # No content to parse
                    etag=etag,  # Keep existing ETag
                    last_modified=last_modified,  # Keep existing Last-Modified
                    error=None
                )
            
            # Handle 200 OK - parse content and update headers
            elif response.status_code == 200:
                logger.debug(f"Feed content received (200): {url}")
                
                # Extract caching headers from response
                response_etag, response_last_modified = self._extract_response_headers(response)
                
                # Parse feed content using feedparser
                feed_content = response.text
                
                if not feed_content.strip():
                    logger.warning(f"Empty feed content from {url}")
                    return FetchResult(
                        status_code=200,
                        feed=None,
                        etag=response_etag,
                        last_modified=response_last_modified,
                        error="Empty feed content"
                    )
                
                # Parse with feedparser
                try:
                    feed = feedparser.parse(feed_content)
                    
                    if feed.bozo and feed.bozo_exception:
                        logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")
                    
                    logger.info(f"Successfully parsed {len(feed.entries)} entries from {url}")
                    
                    return FetchResult(
                        status_code=200,
                        feed=feed,
                        etag=response_etag,
                        last_modified=response_last_modified,
                        error=None
                    )
                    
                except Exception as e:
                    logger.error(f"Feed parsing error for {url}: {e}")
                    return FetchResult(
                        status_code=200,
                        feed=None,
                        etag=response_etag,
                        last_modified=response_last_modified,
                        error=f"Feed parsing error: {str(e)}"
                    )
            
            # Handle other HTTP status codes
            else:
                error_msg = f"HTTP {response.status_code}"
                logger.error(f"HTTP error {response.status_code} for {url}")
                return FetchResult(
                    status_code=response.status_code,
                    feed=None,
                    etag=None,
                    last_modified=None,
                    error=error_msg
                )
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'No content'}"
            logger.error(f"HTTP error fetching {url}: {error_msg}")
            return FetchResult(
                status_code=e.response.status_code,
                feed=None,
                etag=None,
                last_modified=None,
                error=error_msg
            )
            
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(f"Request error fetching {url}: {error_msg}")
            return FetchResult(
                status_code=0,  # No HTTP status for network errors
                feed=None,
                etag=None,
                last_modified=None,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error fetching {url}: {error_msg}")
            return FetchResult(
                status_code=0,
                feed=None,
                etag=None,
                last_modified=None,
                error=error_msg
            )
            result.error = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error fetching {url}: {error_msg}")
            return FetchResult(
                status_code=0,
                feed=None,
                etag=None,
                last_modified=None,
                error=error_msg
            )