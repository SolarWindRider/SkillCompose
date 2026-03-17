"""
Skill collector - fetch skills from ClawHub/awesome-openclaw-skills.
"""
import asyncio
import hashlib
import re
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from github import Github


# Try to get token from environment
DEFAULT_TOKEN = os.environ.get('GITHUB_TOKEN')


class SkillCollector:
    """Skill data collector from ClawHub"""

    def __init__(self, output_dir: Path, github_token: Optional[str] = None):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use provided token, or fall back to environment variable
        token = github_token or DEFAULT_TOKEN
        self.has_token = bool(token)
        if token:
            self.github = Github(token)
            print(f"  Using authenticated GitHub API (5000 requests/hour)")
        else:
            self.github = Github()
            print(f"  Using unauthenticated GitHub API (60 requests/hour)")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SkillCompose/1.0'
        })

    def collect_from_awesome_repo(
        self,
        repo: str = "VoltAgent/awesome-openclaw-skills"
    ) -> List[Dict]:
        """Collect skills from openclaw/skills repository"""
        print(f"Fetching skills from openclaw/skills...")

        # Check if we have a token
        if not self.has_token:
            print("  Warning: No GitHub token. Rate limit will be 60/hour")
            print("  Set GITHUB_TOKEN for better rate limits")

        try:
            # Get the openclaw/skills repo directly
            skills_repo = self.github.get_repo("openclaw/skills")

            # Get all skill directories
            print("  Getting list of all skills...")
            skill_dirs = self._list_all_skills(skills_repo)

            print(f"  Found {len(skill_dirs)} skills")

            # Fetch all skill definitions
            print("  Fetching skill definitions from GitHub...")
            skills = self._fetch_all_skills(skills_repo, skill_dirs)

            print(f"  Successfully fetched {len(skills)} skills")
            return skills

        except Exception as e:
            print(f"Error collecting skills: {e}")
            return []
            return []

    def _list_all_skills(self, repo) -> List[str]:
        """List all skills in the openclaw/skills repository"""
        skills = []

        try:
            # List skills/ directory
            authors = repo.get_contents("skills")
            print(f"    Found {len(authors)} author directories")

            for author in authors:
                if author.type != "dir":
                    continue

                try:
                    # List skills in each author directory
                    author_skills = repo.get_contents(author.path)

                    for skill in author_skills:
                        if skill.type == "dir":
                            skills.append(skill.path)

                except Exception:
                    continue

        except Exception as e:
            print(f"    Error listing skills: {e}")

        return skills

    def _fetch_all_skills(self, repo, skill_paths: List[str]) -> List[Dict]:
        """Fetch all skill definitions from GitHub"""
        skills = []
        total = len(skill_paths)

        print(f"    Fetching {total} skills (this may take a while)...")

        # Use thread pool to fetch in parallel
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {
                executor.submit(self._fetch_skill_def, repo, path): path
                for path in skill_paths
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 200 == 0:
                    print(f"      Progress: {completed}/{total}")

                try:
                    skill = future.result(timeout=30)
                    if skill:
                        skills.append(skill)
                except Exception:
                    pass

        return skills

    def _fetch_skill_def(self, repo, skill_path: str) -> Optional[Dict]:
        """Fetch a single skill definition"""
        try:
            # Try SKILL.md
            skill_md_path = f"{skill_path}/SKILL.md"
            content = repo.get_contents(skill_md_path)
            content_str = content.decoded_content.decode('utf-8')

            # Parse the skill
            skill_data = self._parse_skill_md(content_str, skill_path)

            return skill_data

        except Exception:
            return None

    def _parse_skill_md(self, content: str, path: str) -> Dict:
        """Parse SKILL.md content"""
        import yaml

        skill_id = self._generate_skill_id(path)

        # Extract YAML front-matter
        dependencies = []
        permissions = []
        inputs = {}
        outputs = {}
        name = path.split('/')[-1]
        description = ""
        category = "general"

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                front_matter = parts[1]

                try:
                    data = yaml.safe_load(front_matter)
                    if data:
                        name = data.get('name', name)
                        description = data.get('description', '')
                        permissions = data.get('permissions', [])
                        dependencies = data.get('dependencies', [])
                        inputs = data.get('inputs', {})
                        outputs = data.get('outputs', {})
                        category = data.get('category', 'general')
                except:
                    pass

        # Also extract skill references from content
        content_dependencies = self._extract_skill_references(content, path)

        # Merge dependencies
        all_dependencies = list(set(dependencies + content_dependencies))

        return {
            'skill_id': skill_id,
            'name': name,
            'description': description[:500] if description else "",
            'permissions': permissions,
            'dependencies': all_dependencies,
            'inputs': inputs,
            'outputs': outputs,
            'category': category,
            'markdown_content': content[:5000],
            'source_url': f"https://github.com/openclaw/skills/tree/main/{path}",
            'scraped_at': datetime.now().isoformat(),
        }

    def _extract_skill_references(self, content: str, current_path: str) -> List[str]:
        """Extract skill references from content"""
        refs = []

        # Patterns for referencing other skills
        patterns = [
            r'uses?\s+([a-zA-Z0-9_-]+)\s+skill',
            r'depends?\s+on\s+([a-zA-Z0-9_-]+)',
            r'calls?\s+([a-zA-Z0-9_-]+)',
            r'requires?\s+([a-zA-Z0-9_-]+)',
            r'skill[:\s]+([a-zA-Z0-9_-]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            refs.extend(matches)

        return refs


    def _fetch_skill_from_github(self, repo, path: str) -> Optional[Dict]:
        """Fetch a single skill definition from GitHub"""
        try:
            # Try to get skill.yaml first
            try:
                yaml_file = repo.get_contents(f"{path}/skill.yaml")
                content = yaml_file.decoded_content.decode('utf-8')
                return self._parse_skill_yaml(content, path)
            except:
                pass

            # Try skill.md
            try:
                md_file = repo.get_contents(f"{path}/skill.md")
                content = md_file.decoded_content.decode('utf-8')
                return self._parse_skill_markdown(content, path)
            except:
                pass

            return None

        except Exception:
            return None

    def _parse_skill_yaml(self, content: str, path: str) -> Optional[Dict]:
        """Parse skill.yaml definition"""
        try:
            import yaml
            data = yaml.safe_load(content)

            if not data:
                return None

            # Extract fields
            skill_id = self._generate_skill_id(path)

            return {
                'skill_id': skill_id,
                'name': data.get('name', path.split('/')[-1]),
                'description': data.get('description', ''),
                'permissions': data.get('permissions', []),
                'dependencies': data.get('dependencies', []),
                'inputs': data.get('inputs', {}),
                'outputs': data.get('outputs', {}),
                'category': data.get('category', 'general'),
                'markdown_content': content,
                'source_url': f"https://github.com/openclaw/skills/tree/main/{path}",
                'scraped_at': datetime.now().isoformat(),
            }

        except Exception as e:
            return None

    def _parse_skill_markdown(self, content: str, path: str) -> Optional[Dict]:
        """Parse skill.md definition"""
        skill_id = self._generate_skill_id(path)

        return {
            'skill_id': skill_id,
            'name': path.split('/')[-1],
            'description': content[:200],
            'permissions': [],
            'dependencies': [],
            'inputs': {},
            'outputs': {},
            'category': 'general',
            'markdown_content': content,
            'source_url': f"https://github.com/openclaw/skills/tree/main/{path}",
            'scraped_at': datetime.now().isoformat(),
        }

    def _fetch_skills_parallel(self, links: List[str], max_workers: int = 20) -> List[Dict]:
        """Fetch skills in parallel using thread pool"""
        skills = []
        total = len(links)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._fetch_skill_from_url, link): link for link in links}

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 100 == 0:
                    print(f"    Progress: {completed}/{total}")

                try:
                    skill = future.result(timeout=15)
                    if skill:
                        skills.append(skill)
                except Exception:
                    pass

        return skills

    def _extract_skill_links(self, repo) -> List[str]:
        """Extract skill URLs from README files in the repo"""
        import time

        links = []
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Get README.md
                readme = repo.get_contents("README.md")
                content = readme.decoded_content.decode('utf-8')

                # Extract clawskills.sh links
                pattern = r'https://clawskills\.sh/skills/[\w-]+'
                found_links = re.findall(pattern, content)

                # Also check other markdown files
                try:
                    contents = repo.get_contents("")
                    for c in contents:
                        if c.name.endswith('.md') and c.name != 'README.md':
                            try:
                                content = c.decoded_content.decode('utf-8')
                                found_links.extend(re.findall(pattern, content))
                            except:
                                pass
                except:
                    pass

                # Success - return links
                links = list(set(found_links))
                print(f"    Found {len(links)} unique skill URLs")
                return links

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"    Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Error extracting links: {e}")

        return links

    def _fetch_skill_from_url(self, url: str) -> Optional[Dict]:
        """Fetch skill definition from clawskills.sh"""
        try:
            # Convert clawskills.sh URL to API or raw format
            # Example: https://clawskills.sh/skills/xxx-yyy -> try to get skill data
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None

            html = response.text

            # Extract skill info from the page
            skill_data = self._parse_skill_page(html, url)
            return skill_data

        except Exception as e:
            return None

    def _parse_skill_page(self, html: str, url: str) -> Optional[Dict]:
        """Parse skill definition from HTML page"""
        try:
            # Try to extract embedded JSON first
            json_data = self._extract_json_from_html(html)

            if json_data:
                # Use JSON data if found
                name = json_data.get('name', 'Unknown')
                description = json_data.get('description', '')
                permissions = json_data.get('permissions', [])
                inputs = json_data.get('inputs', {})
                outputs = json_data.get('outputs', {})
            else:
                # Fall back to HTML parsing
                name = self._extract_from_html(html, r'<h1[^>]*>([^<]+)</h1>')
                description = self._extract_from_html(html, r'<p[^>]*>([^<]+)</p>')
                permissions = self._extract_permissions(html)
                inputs = {}
                outputs = {}

            # Extract category from URL
            category = self._extract_category_from_url(url)

            # Generate skill_id
            skill_id = self._generate_skill_id(url)

            return {
                'name': name,
                'description': description,
                'markdown_content': html[:5000],
                'permissions': list(set(permissions)) if permissions else [],
                'inputs': inputs,
                'outputs': outputs,
                'category': category,
                'skill_id': skill_id,
                'source_url': url,
                'scraped_at': datetime.now().isoformat(),
            }

        except Exception as e:
            return None

    def _extract_json_from_html(self, html: str) -> Optional[Dict]:
        """Extract JSON data from HTML (JSON-LD, script tags, etc)"""
        # Try JSON-LD
        json_ld_match = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([^<]+)</script>', html)
        if json_ld_match:
            try:
                return json.loads(json_ld_match.group(1))
            except:
                pass

        # Try to find skill data in script
        script_match = re.search(r'window\.__SKILL_DATA__\s*=\s*({[^;]+});', html)
        if script_match:
            try:
                return json.loads(script_match.group(1))
            except:
                pass

        # Try to find any JSON object
        json_match = re.search(r'{[^{}]*"(name|description|permissions|inputs|outputs)"[^{}]*}', html)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass

        return None

    def _extract_from_html(self, html: str, pattern: str) -> str:
        """Extract text using regex pattern"""
        match = re.search(pattern, html)
        return match.group(1).strip() if match else ""

    def _extract_permissions(self, html: str) -> List[str]:
        """Extract permissions from HTML"""
        permissions = []

        # Common permission patterns
        perm_patterns = [
            r'["\']permissions["\']\s*:\s*\[([^\]]+)\]',
            r'permission[s]?["\']\s*:\s*["\']([^"\']+)["\']',
            r'requires?\s+["\']([^"\']+)["\']',
            r'capability["\']\s*:\s*["\']([^"\']+)["\']',
            r'gmail\.[a-z]+',
            r'slack\.[a-z]+',
            r'drive\.[a-z]+',
            r'calendar\.[a-z]+',
            r'file\.[a-z]+',
            r'http\.[a-z]+',
            r'shell\.[a-z]+',
        ]

        for pattern in perm_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            permissions.extend(matches)

        # Deduplicate and clean
        permissions = list(set(permissions))
        return [p.strip() for p in permissions if p]

    def _extract_category_from_url(self, url: str) -> str:
        """Extract category from URL"""
        # Pattern: skills/{author}-{name}-{category} or skills/{name}
        match = re.search(r'skills/[^/]+-([^/]+)$', url)
        if match:
            category = match.group(1).lower()
            # Map common categories
            category_map = {
                'communication': 'communication', 'slack': 'communication', 'gmail': 'communication',
                'productivity': 'productivity', 'calendar': 'productivity', 'drive': 'productivity',
                'developer': 'developer', 'code': 'developer', 'git': 'developer',
                'ai': 'ai', 'llm': 'ai', 'openai': 'ai',
                'social': 'social', 'twitter': 'social', 'discord': 'social',
                'finance': 'finance', 'payment': 'finance',
                'health': 'health', 'fitness': 'health',
                'shopping': 'shopping', 'amazon': 'shopping',
                'utilities': 'utilities', 'weather': 'utilities',
            }
            return category_map.get(category, category)

        return "general"

    def _generate_skill_id(self, filename: str) -> str:
        """Generate skill_id from filename or URL"""
        # Extract last part of URL
        match = re.search(r'skills/([\w-]+)$', filename)
        if match:
            name = match.group(1)
        else:
            name = filename.replace('.md', '').replace('.yaml', '').replace('.yml', '').replace('.json', '')

        # Hash to get consistent ID
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:6]
        return f"skill_{name[:30]}_{hash_suffix}"

    def _is_skill_file(self, filename: str) -> bool:
        """Check if file is a skill file"""
        return filename.endswith(('.md', '.yaml', '.yml', '.json'))

    def _parse_skill_file(self, content, repo) -> Optional[Dict]:
        """Parse a single skill file"""
        try:
            # Get raw content (PyGithub uses decoded_content)
            file_content = content.decoded_content.decode('utf-8')

            # Generate skill_id from filename
            skill_id = self._generate_skill_id(content.name)

            # Parse markdown with front-matter
            skill_data = self._parse_markdown_with_frontmatter(file_content)

            # Add metadata
            skill_data['skill_id'] = skill_id
            skill_data['source_url'] = content.html_url
            skill_data['scraped_at'] = datetime.now().isoformat()

            return skill_data

        except Exception as e:
            print(f"Error parsing {content.name}: {e}")
            return None

    def _parse_markdown_with_frontmatter(self, content: str) -> Dict:
        """Parse markdown file with YAML front-matter"""
        data = {
            'name': '',
            'description': '',
            'markdown_content': content,
            'permissions': [],
            'category': 'general',
        }

        # Check for front-matter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                front_matter = parts[1]
                content = parts[2]

                # Parse YAML front-matter (simple parsing)
                for line in front_matter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()

                        if key == 'name':
                            data['name'] = value
                        elif key == 'description':
                            data['description'] = value
                        elif key in ['permissions', 'capabilities']:
                            # Parse list
                            data['permissions'] = [x.strip().strip('-').strip() for x in value.split(',')]
                        elif key == 'category':
                            data['category'] = value

        # If no name from front-matter, try to get from first heading
        if not data['name']:
            heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if heading_match:
                data['name'] = heading_match.group(1).strip()

        # Try to extract description from content
        if not data['description']:
            para_match = re.search(r'^[^#\n]+(?:\n[^#\n]+)*', content)
            if para_match:
                data['description'] = para_match.group(0).strip()[:200]

        return data


def collect_skills(
    output_dir: Path,
    github_token: Optional[str] = None,
    repo: str = "VoltAgent/awesome-openclaw-skills"
) -> List[Dict]:
    """Convenience function to collect skills"""
    collector = SkillCollector(output_dir, github_token)
    return collector.collect_from_awesome_repo(repo)
