import asyncio
import json
import logging
import os
import re
import time
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HttpError(Exception):
    def __init__(self, status, message=None):
        super().__init__(message or f"HTTP {status}")
        self.status = status

class MxmApiError(Exception):
    def __init__(self, code, hint=None):
        super().__init__(hint or f"Musixmatch API error {code}")
        self.code = code
        self.hint = hint

APP_ID = 'web-desktop-app-v1.0'
TOKEN_TTL = 55000
TOKEN_PERSIST_INTERVAL = 5000

ENDPOINTS = {
    'TOKEN': 'https://apic-desktop.musixmatch.com/ws/1.1/token.get',
    'SEARCH': 'https://apic-desktop.musixmatch.com/ws/1.1/track.search',
    'LYRICS': 'https://apic-desktop.musixmatch.com/ws/1.1/track.subtitle.get',
    'ALT_LYRICS': 'https://apic-desktop.musixmatch.com/ws/1.1/macro.subtitles.get'
}

TIMESTAMP_REGEX = re.compile(r'\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]')
BRACKET_JUNK = re.compile(r'\s*\[([^\]]*(?:official|lyrics?|video|audio|mv|visualizer|color\s*coded|hd|4k)[^\]]*)\]', re.IGNORECASE)
SEPARATORS = [' - ', ' – ', ' — ', ' ~ ', '-']

DEFAULT_HEADERS = {
    'accept': 'application/json',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

default_client = httpx.AsyncClient(follow_redirects=True)
cookie_client = None

async def get_client(with_cookies=True):
    global cookie_client
    if with_cookies:
        if not cookie_client:
            cookie_client = httpx.AsyncClient(cookies={}, follow_redirects=True)
        return cookie_client
    return default_client

def reset_cookie_client():
    global cookie_client
    if cookie_client:
        cookie_client.cookies.clear()

class Musixmatch:
    def __init__(self, opts=None):
        if opts is None:
            opts = {}
        self.token_data = None
        self.token_promise = None
        self.last_token_persist = 0
        self.cache = {}
        self.request_timeout_ms = opts.get('requestTimeoutMs', 8000)
        self.cache_ttl = opts.get('cacheTTL', 300000)
        self.max_cache_entries = max(10, opts.get('maxCacheEntries', 100))
        self.token_file = opts.get('tokenFile', os.path.join(os.path.expanduser('~'), 'mxm_token.json'))

    def build_url(self, base, params):
        parsed_url = urlparse(base)
        query_params = urlencode({k: v for k, v in params.items() if v is not None})
        return urlunparse(parsed_url._replace(query=query_params))

    async def read_token_from_file(self):
        try:
            async with asyncio.Lock():
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    data = f.read()
            parsed = json.loads(data)
            if parsed and parsed.get('value') and isinstance(parsed.get('expires'), int) and parsed['expires'] > time.time() * 1000:
                return parsed
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return None

    async def save_token_to_file(self, token, expires):
        try:
            async with asyncio.Lock():
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    json.dump({'value': token, 'expires': expires}, f)
        except IOError:
            pass

    async def api_get(self, url):
        client = await get_client(True)
        logger.debug(f"API Request: GET {url}")
        try:
            response = await client.get(url, headers=DEFAULT_HEADERS, timeout=self.request_timeout_ms / 1000)
            logger.debug(f"API Response: {response.status_code} {response.url}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Status Error for {url}: {e.response.status_code} - {e.response.text}")
            raise HttpError(e.response.status_code) from e
        except httpx.RequestError as e:
            logger.error(f"Request Error for {url}: {e}")
            raise HttpError(0, f"Request error: {e}") from e

        data = response.json()
        header = data.get('message', {}).get('header', {})

        if header.get('status_code') != 200:
            raise MxmApiError(header.get('status_code', 0), header.get('hint'))

        return data['message']['body']

    async def fetch_token(self, with_cookies=True):
        url = self.build_url(ENDPOINTS['TOKEN'], {'app_id': APP_ID})
        body = await self.api_get(url)
        return body['user_token']

    async def reset_token(self, hard=False):
        self.token_data = None
        self.token_promise = None
        if hard:
            try:
                os.remove(self.token_file)
            except OSError:
                pass

    async def get_token(self, force=False):
        now = time.time() * 1000

        if not force and self.token_data and now < self.token_data['expires']:
            self.token_data['expires'] = now + TOKEN_TTL
            if now - self.last_token_persist > TOKEN_PERSIST_INTERVAL:
                self.last_token_persist = now
                asyncio.create_task(self.save_token_to_file(self.token_data['value'], self.token_data['expires']))
            return self.token_data['value']

        if not self.token_data and not force:
            self.token_data = await self.read_token_from_file()
            if self.token_data and now < self.token_data['expires']:
                return self.token_data['value']

        if self.token_promise:
            return await self.token_promise

        self.token_promise = asyncio.create_task(self.acquire_new_token())
        try:
            return await self.token_promise
        finally:
            self.token_promise = None

    async def acquire_new_token(self):
        try:
            token = await self.fetch_token(False)
            expires = time.time() * 1000 + TOKEN_TTL
            self.token_data = {'value': token, 'expires': expires}
            await self.save_token_to_file(token, expires)
            return token
        except MxmApiError as err:
            if err.code in (401, 403):
                await self.reset_token(True)
                reset_cookie_client()
                token = await self.fetch_token(True)
                expires = time.time() * 1000 + TOKEN_TTL
                self.token_data = {'value': token, 'expires': expires}
                await self.save_token_to_file(token, expires)
                return token
            raise

    async def call_mxm(self, endpoint, params):
        try:
            token = await self.get_token()
            url = self.build_url(endpoint, {**params, 'app_id': APP_ID, 'usertoken': token})
            return await self.api_get(url)
        except MxmApiError as err:
            if err.code in (401, 403):
                is_captcha = err.hint and 'captcha' in err.hint.lower()
                await self.reset_token(is_captcha)
                if is_captcha:
                    reset_cookie_client()
                new_token = await self.get_token(True)
                url = self.build_url(endpoint, {**params, 'app_id': APP_ID, 'usertoken': new_token})
                return await self.api_get(url)
            raise

    def clean_lyrics(self, lyrics):
        lines = TIMESTAMP_REGEX.sub('', lyrics).split('\n')
        cleaned = []
        for line in lines:
            trimmed = line.strip()
            if trimmed:
                cleaned.append(trimmed)
        return '\n'.join(cleaned)

    def parse_subtitles(self, subtitle_body):
        try:
            parsed = json.loads(subtitle_body)
            arr = None
            if isinstance(parsed, list):
                arr = parsed
            elif isinstance(parsed, dict) and isinstance(parsed.get('subtitle'), list):
                arr = parsed['subtitle']

            if not isinstance(arr, list) or not arr:
                return None
            return [{'range': {'start': round((item.get('time', {}).get('total', 0)) * 1000)}, 'line': str(item.get('text', ''))} for item in arr]
        except json.JSONDecodeError:
            return None

    def parse_query(self, query):
        cleaned = BRACKET_JUNK.sub('', query).strip()
        for separator in SEPARATORS:
            index = cleaned.find(separator)
            if 0 < index < len(cleaned) - len(separator):
                artist = cleaned[:index].strip()
                title = cleaned[index + len(separator):].strip()
                if artist and title:
                    return {'artist': artist, 'title': title}
        return {'title': cleaned}

    def format_result(self, subtitles, lyrics, track):
        lines = self.parse_subtitles(subtitles) if subtitles else None
        text = self.clean_lyrics(lyrics) if lyrics else (
            '\n'.join([l['line'] for l in lines]) if lines else None
        )

        return {
            'text': text,
            'lines': lines,
            'track': {
                'title': track.get('track_name', ''),
                'author': track.get('artist_name', ''),
                'albumArt': track.get('album_coverart_800x800') or track.get('album_coverart_350x350') or track.get('album_coverart_100x100')
            },
            'source': 'Musixmatch'
        }

    def cache_key(self, artist, title):
        normalized_artist = artist.lower().strip() if artist else ''
        normalized_title = title.lower().strip()
        return f"{normalized_artist}|{normalized_title}"

    def get_cached(self, key):
        entry = self.cache.get(key)
        if not entry:
            return None
        if entry['expires'] > time.time() * 1000:
            return entry['value']
        del self.cache[key]
        return None

    def set_cached(self, key, value):
        if len(self.cache) >= self.max_cache_entries:
            if self.cache:
                first_key = next(iter(self.cache))
                del self.cache[first_key]
        self.cache[key] = {'value': value, 'expires': time.time() * 1000 + self.cache_ttl}

    async def race_for_first(self, promises):
        if not promises:
            logger.debug("race_for_first called with no promises.")
            return None
        
        logger.debug(f"race_for_first called with {len(promises)} promises.")
        done, pending = await asyncio.wait(promises, return_when=asyncio.FIRST_COMPLETED)
        
        for task in pending:
            task.cancel()
            logger.debug(f"Cancelled pending task: {task}")

        for task in done:
            try:
                result = task.result()
                if result:
                    logger.debug(f"race_for_first found a result: {result}")
                    return result
            except Exception as e:
                logger.error(f"Error in raced task: {e}")
        logger.debug("race_for_first found no successful result.")
        return None

    async def find_lyrics(self, query):
        logger.info(f"Attempting to find lyrics for query: '{query}'")
        parsed = self.parse_query(query)
        logger.debug(f"Parsed query: {parsed}")
        key = self.cache_key(parsed.get('artist'), parsed['title'])
        cached = self.get_cached(key)
        if cached is not None:
            logger.info(f"Returning cached result for key: {key}")
            return cached

        result = None

        try:
            if parsed.get('artist'):
                logger.debug(f"Artist found, racing macro_promise_func and search_promise_func for artist: {parsed['artist']}, title: {parsed['title']}")
                async def macro_promise_func():
                    logger.debug("macro_promise_func started.")
                    body = await self.call_mxm(ENDPOINTS['ALT_LYRICS'], {
                        'format': 'json',
                        'namespace': 'lyrics_richsynched',
                        'subtitle_format': 'mxm',
                        'q_artist': parsed['artist'],
                        'q_track': parsed['title']
                    })
                    calls = body.get('macro_calls', {})
                    lyrics = calls.get('track.lyrics.get', {}).get('message', {}).get('body', {}).get('lyrics', {}).get('lyrics_body')
                    track = calls.get('matcher.track.get', {}).get('message', {}).get('body', {}).get('track')
                    subtitles = calls.get('track.subtitles.get', {}).get('message', {}).get('body', {}).get('subtitle_list', [{}])[0].get('subtitle', {}).get('subtitle_body')
                    macro_result = self.format_result(subtitles or None, lyrics or None, track or {}) if lyrics or subtitles else None
                    logger.debug(f"macro_promise_func finished with result: {bool(macro_result)}")
                    return macro_result

                async def search_promise_func():
                    logger.debug("search_promise_func started.")
                    body = await self.call_mxm(ENDPOINTS['SEARCH'], {
                        'page_size': '1',
                        'page': '1',
                        's_track_rating': 'desc',
                        'q_track': parsed['title'],
                        'q_artist': parsed['artist']
                    })
                    track = body.get('track_list', [{}])[0].get('track')
                    if not track:
                        logger.debug("search_promise_func found no track.")
                        return None
                    lyrics_body = await self.call_mxm(ENDPOINTS['LYRICS'], {
                        'subtitle_format': 'mxm',
                        'track_id': str(track['track_id'])
                    })
                    subtitles = lyrics_body.get('subtitle', {}).get('subtitle_body')
                    search_result = self.format_result(subtitles, None, track) if subtitles else None
                    logger.debug(f"search_promise_func finished with result: {bool(search_result)}")
                    return search_result

                result = await self.race_for_first([
                    asyncio.create_task(macro_promise_func()),
                    asyncio.create_task(search_promise_func())
                ])
            else:
                logger.debug(f"No artist found, performing direct search for title: {parsed['title']}")
                search_body = await self.call_mxm(ENDPOINTS['SEARCH'], {
                    'page_size': '1',
                    'page': '1',
                    's_track_rating': 'desc',
                    'q_track': parsed['title']
                })
                track = search_body.get('track_list', [{}])[0].get('track')
                if track:
                    logger.debug(f"Track found via direct search: {track.get('track_name')}")
                    lyrics_body = await self.call_mxm(ENDPOINTS['LYRICS'], {
                        'subtitle_format': 'mxm',
                        'track_id': str(track['track_id'])
                    })
                    subtitles = lyrics_body.get('subtitle', {}).get('subtitle_body')
                    if subtitles:
                        result = self.format_result(subtitles, None, track)
                        logger.debug("Direct search found subtitles.")
                else:
                    logger.debug("Direct search found no track.")

            if not result:
                logger.debug(f"No result yet, trying fallback for title: {parsed['title']}")
                fallback_body = await self.call_mxm(ENDPOINTS['ALT_LYRICS'], {
                    'format': 'json',
                    'namespace': 'lyrics_richsynched',
                    'subtitle_format': 'mxm',
                    'q_track': parsed['title']
                })
                calls = fallback_body.get('macro_calls', {})
                lyrics = calls.get('track.lyrics.get', {}).get('message', {}).get('body', {}).get('lyrics', {}).get('lyrics_body')
                track = calls.get('matcher.track.get', {}).get('message', {}).get('body', {}).get('track')
                subtitles = calls.get('track.subtitles.get', {}).get('message', {}).get('body', {}).get('subtitle_list', [{}])[0].get('subtitle', {}).get('subtitle_body')
                if lyrics or subtitles:
                    result = self.format_result(subtitles or None, lyrics or None, track or {})
                    logger.debug("Fallback search found lyrics or subtitles.")
                else:
                    logger.debug("Fallback search found no lyrics or subtitles.")
        except Exception as e:
            logger.error(f"An error occurred in find_lyrics: {e}", exc_info=True)
            result = None

        self.set_cached(key, result)
        logger.info(f"find_lyrics finished for query: '{query}', result found: {bool(result)}")
        return result