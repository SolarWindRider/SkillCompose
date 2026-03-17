"""
Skill data cleaner - remove malicious/deprecated skills.
"""
import re
import hashlib
from typing import List, Dict, Set, Optional
from pathlib import Path


class SkillCleaner:
    """Skill data cleaner"""

    def __init__(self, malicious_hashes: Optional[Set[str]] = None):
        # Known malicious skill hashes (from VirusTotal reports)
        self.malicious_hashes = malicious_hashes or set()
        self.removed_skills = []

    def clean(self, skill: Dict) -> Optional[Dict]:
        """Clean a single skill"""

        # 1. Check if deprecated/archived
        if skill.get('deprecated') or skill.get('archived'):
            self._record_removal(skill, "deprecated/archived")
            return None

        # 2. Check if malicious
        skill_hash = self._compute_hash(skill)
        if skill_hash in self.malicious_hashes:
            self._record_removal(skill, "malicious")
            return None

        # 3. Clean markdown content
        if 'markdown_content' in skill:
            skill['markdown_content'] = self._clean_markdown(
                skill['markdown_content']
            )

        # 4. Normalize permissions
        if 'permissions' in skill:
            skill['permissions'] = self._normalize_permissions(
                skill['permissions']
            )

        # 5. Validate required fields
        if not self._validate_required_fields(skill):
            self._record_removal(skill, "missing required fields")
            return None

        # 6. Add content hash
        skill['content_hash'] = skill_hash

        return skill

    def clean_batch(self, skills: List[Dict]) -> List[Dict]:
        """Clean a batch of skills"""
        cleaned = []

        for skill in skills:
            cleaned_skill = self.clean(skill)
            if cleaned_skill:
                cleaned.append(cleaned_skill)

        print(f"Cleaned {len(skills)} skills -> {len(cleaned)} (removed {len(skills) - len(cleaned)})")
        return cleaned

    def _clean_markdown(self, content: str) -> str:
        """Clean markdown content"""

        if not content:
            return ""

        # Remove script tags
        content = re.sub(
            r'<script[^>]*>.*?</script>',
            '',
            content,
            flags=re.DOTALL | re.IGNORECASE
        )

        # Remove eval/exec calls (comment them out)
        content = re.sub(r'\beval\s*\(', '// eval(', content)
        content = re.sub(r'\bexec\s*\(', '// exec(', content)

        # Remove external image references (potential tracking)
        content = re.sub(
            r'!\[[^\]]*\]\([^http|https].*?\)',
            '',
            content
        )

        # Normalize whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    def _normalize_permissions(self, permissions) -> List[str]:
        """Normalize permission format"""
        normalized = []

        # Handle different input types
        if isinstance(permissions, str):
            permissions = [permissions]
        elif not isinstance(permissions, list):
            return []

        for perm in permissions:
            # Convert to string
            perm = str(perm).lower().strip()

            # Remove whitespace
            perm = re.sub(r'\s+', '', perm)

            # Validate format: alphanumeric with dots and underscores
            if re.match(r'^[a-z][a-z0-9._]*$', perm):
                normalized.append(perm)

        return list(set(normalized))

    def _validate_required_fields(self, skill: Dict) -> bool:
        """Validate required fields"""
        required_fields = ['skill_id', 'name']

        for field in required_fields:
            if not skill.get(field):
                return False

        # Name must be non-empty after stripping
        if not skill.get('name', '').strip():
            return False

        return True

    def _compute_hash(self, skill: Dict) -> str:
        """Compute content hash for deduplication"""
        content = f"{skill.get('name', '')}{skill.get('markdown_content', '')}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _record_removal(self, skill: Dict, reason: str):
        """Record removed skill for debugging"""
        self.removed_skills.append({
            'skill_id': skill.get('skill_id', 'unknown'),
            'name': skill.get('name', 'unknown'),
            'reason': reason
        })

    def get_removal_report(self) -> Dict:
        """Get removal statistics"""
        reasons = {}
        for item in self.removed_skills:
            reason = item['reason']
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            'total_removed': len(self.removed_skills),
            'by_reason': reasons
        }


def load_malicious_hashes(filepath: Path) -> Set[str]:
    """Load malicious hashes from file"""
    if not filepath.exists():
        return set()

    hashes = set()
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                hashes.add(line)

    return hashes


def clean_skills(
    skills: List[Dict],
    malicious_file: Optional[Path] = None
) -> List[Dict]:
    """Convenience function to clean skills"""
    malicious_hashes = load_malicious_hashes(malicious_file) if malicious_file else None
    cleaner = SkillCleaner(malicious_hashes)
    return cleaner.clean_batch(skills)


if __name__ == "__main__":
    import json
    from pathlib import Path

    # Test with sample data
    test_skills = [
        {
            'skill_id': 'skill_test_001',
            'name': 'Test Skill',
            'description': 'A test skill',
            'markdown_content': '# Test\n\nSome content',
            'permissions': ['gmail.read', 'SLACK.WRITE'],
            'deprecated': False
        },
        {
            'skill_id': 'skill_test_002',
            'name': '',  # Invalid - empty name
            'description': 'Missing name',
            'markdown_content': '',
            'permissions': [],
        },
        {
            'skill_id': 'skill_test_003',
            'name': 'Deprecated Skill',
            'description': 'This skill is deprecated',
            'markdown_content': '# Deprecated',
            'permissions': ['file.read'],
            'deprecated': True
        }
    ]

    cleaner = SkillCleaner()
    cleaned = cleaner.clean_batch(test_skills)

    print(f"\nCleaned: {len(cleaned)} skills")
    print(f"Removed: {cleaner.get_removal_report()}")
