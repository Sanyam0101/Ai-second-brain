import asyncpg
import uuid
import requests
import asyncio
import re
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Optional
from app.schemas.integrations import IntegrationResponse
from app.schemas.notes import NoteCreate
from app.services.notes import NotesService

class IntegrationsService:
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean up raw text from scraper"""
        # Remove multiple newlines/spaces
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        # Remove boilerplate common in web pages
        boilerplate = [
            r'Cookie Policy', r'Privacy Policy', r'Terms of Service', 
            r'All rights reserved', r'Contact Us', r'Login / Signup'
        ]
        for p in boilerplate:
            text = re.sub(p, '', text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def _extract_tags(text: str, existing_tags: List[str] = None) -> List[str]:
        """Extract meaningful tags from content using heuristics"""
        tags = set(existing_tags or [])
        lower_text = text.lower()
        
        # Simple but effective keyword mapping
        keyword_map = {
            "research": ["research", "study", "analysis", "paper", "investigation"],
            "development": ["code", "programming", "software", "dev", "git", "api"],
            "marketing": ["marketing", "sales", "brand", "advertising", "customer"],
            "project": ["project", "roadmap", "milestone", "planning"],
            "meeting": ["meeting", "sync", "discussion", "agenda", "call"],
            "personal": ["journal", "thought", "idea", "diary"],
            "tech": ["ai", "machine learning", "cloud", "data", "infrastructure"],
            "finance": ["budget", "finance", "cost", "investment", "revenue"]
        }
        
        for tag, keywords in keyword_map.items():
            if any(k in lower_text for k in keywords):
                tags.add(tag)
        
        # Extract specific capitalized terms as potential tags
        found_entities = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
        for entity in found_entities[:5]:
            if entity.lower() not in ["the", "this", "that", "from", "with"]:
                tags.add(entity.lower())
                
        return list(tags)

    @staticmethod
    async def connect_integration(conn: asyncpg.Connection, user_id: uuid.UUID, platform: str, token: str) -> None:
        query = '''
            INSERT INTO integrations (user_id, platform, access_token)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, platform) DO UPDATE 
            SET access_token = $3
        '''
        await conn.execute(query, user_id, platform, token)

    @staticmethod
    async def get_user_integrations(conn: asyncpg.Connection, user_id: uuid.UUID) -> List[IntegrationResponse]:
        query = '''
            SELECT id, platform, last_synced
            FROM integrations
            WHERE user_id = $1
        '''
        rows = await conn.fetch(query, user_id)
        return [
            IntegrationResponse(
                id=str(row['id']),
                platform=row['platform'],
                last_synced=row['last_synced'],
                connected=True
            )
            for row in rows
        ]

    @staticmethod
    async def disconnect_integration(conn: asyncpg.Connection, user_id: uuid.UUID, platform: str) -> None:
        query = '''
            DELETE FROM integrations
            WHERE user_id = $1 AND platform = $2
        '''
        await conn.execute(query, user_id, platform)

    @staticmethod
    async def get_token(conn: asyncpg.Connection, user_id: uuid.UUID, platform: str) -> Optional[str]:
        query = '''
            SELECT access_token
            FROM integrations
            WHERE user_id = $1 AND platform = $2
        '''
        row = await conn.fetchrow(query, user_id, platform)
        return row['access_token'] if row else None

    @staticmethod
    async def update_sync_time(conn: asyncpg.Connection, user_id: uuid.UUID, platform: str) -> None:
        query = '''
            UPDATE integrations
            SET last_synced = now()
            WHERE user_id = $1 AND platform = $2
        '''
        await conn.execute(query, user_id, platform)

    @staticmethod
    def _is_github_url(value: str) -> bool:
        return value.startswith('https://github.com/') or value.startswith('http://github.com/')

    @staticmethod
    def _parse_github_repo_url(url: str):
        """Extract owner/repo from a GitHub URL"""
        match = re.match(r'https?://github\.com/([^/]+)/([^/\s\.]+)', url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    @staticmethod
    def _fetch_github_repo_by_url(url: str) -> List[NoteCreate]:
        """Fetch repo info + README from a GitHub URL (no auth needed for public repos)"""
        owner, repo = IntegrationsService._parse_github_repo_url(url)
        if not owner or not repo:
            return []
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        notes = []
        
        # Fetch repo info
        repo_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if repo_res.status_code == 200:
            data = repo_res.json()
            desc = data.get("description") or "No description"
            lang = data.get("language") or "Unknown"
            stars = data.get("stargazers_count", 0)
            content = f"🐙 GitHub Repo: {data['full_name']}\nURL: {data['html_url']}\nDescription: {desc}\nLanguage: {lang}\nStars: {stars}"
            tags = ["github", "repository", lang.lower()]
            notes.append(NoteCreate(content=content, tags=tags))
        
        # Fetch README
        readme_res = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers)
        if readme_res.status_code == 200:
            import base64
            readme_data = readme_res.json()
            readme_content = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="replace")
            # Truncate very long READMEs
            if len(readme_content) > 5000:
                readme_content = readme_content[:5000] + "\n\n... [truncated]"
            notes.append(NoteCreate(
                content=f"📄 README from {owner}/{repo}\n\n{readme_content}",
                tags=["github", "readme", repo.lower()]
            ))
        
        return notes

    @staticmethod
    def _fetch_github_repos_by_token(token: str) -> List[NoteCreate]:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get("https://api.github.com/user/repos?sort=updated&per_page=5", headers=headers)
        if res.status_code != 200:
            return []
        notes = []
        for repo in res.json():
            desc = repo.get("description") or "No description"
            content = f"🐙 GitHub Repo: {repo['name']}\nURL: {repo['html_url']}\nDescription: {desc}"
            tags = ["github", "repository"]
            if repo.get("language"):
                tags.append(repo["language"].lower())
            notes.append(NoteCreate(content=content, tags=tags))
        return notes

    @staticmethod
    def _fetch_github_gists_by_token(token: str) -> List[NoteCreate]:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get("https://api.github.com/gists", headers=headers)
        if res.status_code != 200:
            return []
        notes = []
        for gist in res.json()[:5]:  # Limit to 5 gists
            for filename, file_info in gist.get("files", {}).items():
                content_res = requests.get(file_info['raw_url'], headers=headers)
                if content_res.status_code == 200:
                    text = content_res.text[:3000]
                    notes.append(NoteCreate(
                        content=f"📝 GitHub Gist: {filename}\n\n{text}",
                        tags=["github", "gist"]
                    ))
        return notes

    @staticmethod
    def _fetch_gdrive_content(link: str) -> List[NoteCreate]:
        """Try to fetch content from a Google Drive/Docs shareable link"""
        # Extract file ID from various Google link formats
        file_id = None
        patterns = [
            r'/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/folders/([a-zA-Z0-9_-]+)',
        ]
        for p in patterns:
            m = re.search(p, link)
            if m:
                file_id = m.group(1)
                break
        
        if not file_id:
            return [NoteCreate(
                content=f"📁 Google Drive Link: {link}\n\n[Connected — link saved for reference]",
                tags=["gdrive", "integration"]
            )]
        
        # Try to export as text (works for Google Docs that are publicly shared)
        export_url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"
        try:
            res = requests.get(export_url, timeout=10)
            if res.status_code == 200 and len(res.text) > 50:
                # Extract first line as title if possible
                content = res.text[:5000]
                first_line = content.split('\n')[0].strip()[:100]
                return [NoteCreate(
                    content=f"📄 Google Doc: {first_line}\n\n{content}",
                    tags=["gdrive", "document", "imported"]
                )]
        except Exception:
            pass
            
        # Fallback: Try to scrape the public Drive URL with better headers
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            res = requests.get(link, headers=headers, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "Google Drive File"
                title = title.replace(" - Google Drive", "").replace(" - Google Docs", "")
                
                # Try to find the main content div or just get all text
                text = soup.get_text(separator=' ', strip=True)
                text = IntegrationsService._clean_text(text)[:5000]
                
                if len(text) > 50:
                    tags = IntegrationsService._extract_tags(text, ["gdrive", "imported"])
                    return [NoteCreate(
                        content=f"📁 Google Drive: {title}\nURL: {link}\n\n{text}",
                        tags=tags
                    )]
        except Exception:
            pass
        
        return [NoteCreate(
            content=f"📁 Google Drive: {link}\n\nFile ID: {file_id}\n[Link saved — make sure the document is publicly shared to enable content import]",
            tags=["gdrive", "integration"]
        )]

    @staticmethod
    async def sync_github(conn: asyncpg.Connection, user_id: uuid.UUID, token: str) -> int:
        loop = asyncio.get_event_loop()
        
        if IntegrationsService._is_github_url(token):
            # User provided a repo URL
            notes = await loop.run_in_executor(None, IntegrationsService._fetch_github_repo_by_url, token)
            # Fallback for generic github URLs
            if not notes:
                notes = await loop.run_in_executor(None, IntegrationsService._fetch_generic_web_content, token, "github")
        else:
            # User provided a PAT token
            repos_notes = await loop.run_in_executor(None, IntegrationsService._fetch_github_repos_by_token, token)
            gists_notes = await loop.run_in_executor(None, IntegrationsService._fetch_github_gists_by_token, token)
            notes = repos_notes + gists_notes
        
        for note in notes:
            await NotesService.create_note(conn, user_id, note)
            
        await IntegrationsService.update_sync_time(conn, user_id, "github")
        return len(notes)

    @staticmethod
    async def sync_gdrive(conn: asyncpg.Connection, user_id: uuid.UUID, link: str) -> int:
        loop = asyncio.get_event_loop()
        notes = await loop.run_in_executor(None, IntegrationsService._fetch_gdrive_content, link)
        for note in notes:
            await NotesService.create_note(conn, user_id, note)
        await IntegrationsService.update_sync_time(conn, user_id, "gdrive")
        return len(notes)

    @staticmethod
    def _fetch_notion_content(link: str) -> List[NoteCreate]:
        """Fetch content from a public Notion page by scraping the HTML"""
        # Try fetching the page content
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            res = requests.get(link, headers=headers, timeout=15)
            if res.status_code != 200:
                return [NoteCreate(
                    content=f"📝 Notion page: {link}\n\n[Page could not be fetched — make sure it's publicly shared]",
                    tags=["notion", "integration"]
                )]
            
            html = res.text
            
            # Extract title from <title> tag
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Notion Page"
            title = re.sub(r'\s*\|.*$', '', title)  # Remove "| Notion" suffix
            
            # Extract text content - strip all HTML tags
            # Remove script and style blocks first
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'&[a-zA-Z]+;', ' ', text)  # HTML entities
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Get meaningful content (skip very short or empty results)
            if len(text) < 100:
                return [NoteCreate(
                    content=f"📝 Notion page: {title}\nURL: {link}\n\n[Content could not be extracted — the page may require JavaScript rendering. Link saved for reference.]",
                    tags=["notion", "integration"]
                )]
            
            # Truncate very long content
            if len(text) > 5000:
                text = text[:5000] + "\n\n... [truncated]"
            
            return [NoteCreate(
                content=f"📝 Notion: {title}\nSource: {link}\n\n{text}",
                tags=IntegrationsService._extract_tags(text, ["notion", "imported", "document"])
            )]
        except Exception as e:
            return [NoteCreate(
                content=f"📝 Notion page: {link}\n\n[Import failed: {str(e)[:100]}]\n[Link saved for reference]",
                tags=["notion", "integration"]
            )]

    @staticmethod
    async def sync_notion(conn: asyncpg.Connection, user_id: uuid.UUID, link: str) -> int:
        loop = asyncio.get_event_loop()
        notes = await loop.run_in_executor(None, IntegrationsService._fetch_notion_content, link)
        for note in notes:
            await NotesService.create_note(conn, user_id, note)
        await IntegrationsService.update_sync_time(conn, user_id, "notion")
        return len(notes)

    @staticmethod
    def _fetch_generic_web_content(link: str, tag: str = "web") -> List[NoteCreate]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            res = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Better content extraction: remove junk
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()
                
                title = soup.title.string.strip() if soup.title and soup.title.string else "Web Page"
                
                # Try to get meta description as well
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                desc_text = meta_desc['content'] if meta_desc and meta_desc.get('content') else ""
                
                text = soup.get_text(separator='\n', strip=True)
                text = IntegrationsService._clean_text(text)[:6000]
                
                if len(text) > 100:
                    full_content = f"🌐 Scraped Page: {title}\nURL: {link}\n\nDescription: {desc_text}\n\n{text}"
                    tags = IntegrationsService._extract_tags(text, [tag, "scraped"])
                    return [NoteCreate(content=full_content, tags=tags)]
        except Exception as e:
            return [NoteCreate(
                content=f"🌐 Web Link: {link}\n\n[Import failed: {str(e)[:100]}]\n[Link saved for reference]",
                tags=[tag, "integration"]
            )]
        return []

    @staticmethod
    async def trigger_sync(conn: asyncpg.Connection, user_id: uuid.UUID, platform: str) -> int:
        token = await IntegrationsService.get_token(conn, user_id, platform)
        if not token:
            raise ValueError(f"No integration found for {platform}")

        if platform == "github":
            return await IntegrationsService.sync_github(conn, user_id, token)
        elif platform == "gdrive":
            return await IntegrationsService.sync_gdrive(conn, user_id, token)
        elif platform == "notion":
            return await IntegrationsService.sync_notion(conn, user_id, token)
        else:
            # Try generic web scraper for any other platform URLs
            if token.startswith("http://") or token.startswith("https://"):
                loop = asyncio.get_event_loop()
                notes = await loop.run_in_executor(None, IntegrationsService._fetch_generic_web_content, token, platform)
                if notes:
                    for note in notes:
                        await NotesService.create_note(conn, user_id, note)
                    await IntegrationsService.update_sync_time(conn, user_id, platform)
                    return len(notes)

            # Slack and future platforms generic fallback
            note = NoteCreate(
                content=f"📎 Connected to {platform}.\n\nSource: {token}\n\n[Integration active — content sync available for supported platforms]",
                tags=[platform, "integration"]
            )
            await NotesService.create_note(conn, user_id, note)
            await IntegrationsService.update_sync_time(conn, user_id, platform)
            return 1

