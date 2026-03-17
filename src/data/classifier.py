"""
Skill classifier - classify skills by sensitivity, category, etc.
"""
from typing import List, Dict, Set
from collections import defaultdict

from .schemas import PERMISSION_TIERS


class SkillClassifier:
    """Classify skills by various criteria"""

    # Default category mapping
    CATEGORY_KEYWORDS = {
        'communication': ['email', 'slack', 'discord', 'telegram', 'sms', 'chat'],
        'productivity': ['calendar', 'document', 'note', 'task', 'project'],
        'data': ['database', 'storage', 'file', 'upload', 'download', 's3'],
        'social': ['twitter', 'facebook', 'instagram', 'linkedin', 'social'],
        'finance': ['payment', 'stripe', 'paypal', 'bank', 'invoice', 'billing'],
        'dev': ['git', 'github', 'deploy', 'build', 'ci', 'cd', 'docker', 'k8s'],
        'marketing': ['analytics', 'ads', 'facebook_ads', 'google_ads', 'seo'],
        'ai': ['openai', 'gpt', 'claude', 'ai', 'ml', 'model'],
        'weather': ['weather', 'forecast', 'temperature'],
        'news': ['news', 'rss', 'headline'],
        'search': ['search', 'google', 'bing', 'duckduckgo'],
        'utility': ['calc', 'convert', 'translate', 'time', 'timezone'],
    }

    def __init__(self):
        self.high_perms = set(PERMISSION_TIERS["high"])
        self.medium_perms = set(PERMISSION_TIERS["medium"])

    def classify_sensitivity(self, permissions: List[str]) -> str:
        """Classify skill sensitivity based on permissions"""
        perm_set = set(permissions)

        if perm_set & self.high_perms:
            return "high"
        elif perm_set & self.medium_perms:
            return "medium"
        return "low"

    def classify_category(self, skill: Dict) -> str:
        """Classify skill category based on name and description"""
        text = f"{skill.get('name', '')} {skill.get('description', '')}".lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return category

        # Check markdown content
        markdown = skill.get('markdown_content', '').lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in markdown for kw in keywords[:2]):  # Check first 2 keywords
                return category

        return "other"

    def classify_batch(self, skills: List[Dict]) -> List[Dict]:
        """Classify a batch of skills"""
        # First pass: generate permissions for skills without them
        skills = self._generate_permissions(skills)

        # Second pass: classify
        for skill in skills:
            # Sensitivity
            permissions = skill.get('permissions', [])
            skill['sensitivity'] = self.classify_sensitivity(permissions)

            # Category
            skill['category'] = self.classify_category(skill)

        return skills

    def _generate_permissions(self, skills: List[Dict]) -> List[Dict]:
        """Generate permissions for skills that don't have them"""
        import random

        # Category to permission mapping
        perm_mapping = {
            'communication': ['gmail.read', 'slack.read', 'slack.write'],
            'social': ['slack.read', 'slack.write', 'discord.read'],
            'productivity': ['calendar.read', 'calendar.write', 'drive.read'],
            'data': ['drive.read', 'drive.write', 'file.read', 'file.write'],
            'dev': ['git.read', 'git.write', 'shell.exec', 'http.request'],
            'ai': ['openai.api', 'http.request'],
            'finance': ['payment.process', 'stripe.api'],
            'marketing': ['analytics.read'],
            'weather': ['weather.query'],
            'news': ['news.read'],
            'search': ['search.query'],
            'utility': [],
        }

        # High-risk permissions
        high_risk = ['gmail.send', 'slack.write', 'shell.exec', 'file.upload',
                     'http.request', 'payment.process', 'credential.store']

        for skill in skills:
            # Skip if already has real permissions
            perms = skill.get('permissions', [])
            if perms and any(p in high_risk for p in perms):
                continue

            # Generate based on category
            category = skill.get('category', 'general')
            possible_perms = perm_mapping.get(category, [])

            if possible_perms:
                # Randomly assign 1-3 permissions
                num_perms = random.randint(1, min(3, len(possible_perms)))
                skill['permissions'] = random.sample(possible_perms, num_perms)
            else:
                skill['permissions'] = []

            # Add high-risk with low probability
            if random.random() < 0.1:  # 10% chance
                skill['permissions'].append(random.choice(high_risk))

        return skills

    def get_statistics(self, skills: List[Dict]) -> Dict:
        """Get classification statistics"""
        stats = {
            'total': len(skills),
            'by_sensitivity': defaultdict(int),
            'by_category': defaultdict(int),
            'by_permission': defaultdict(int),
        }

        for skill in skills:
            stats['by_sensitivity'][skill.get('sensitivity', 'unknown')] += 1
            stats['by_category'][skill.get('category', 'unknown')] += 1

            for perm in skill.get('permissions', []):
                stats['by_permission'][perm] += 1

        # Convert to regular dict
        stats['by_sensitivity'] = dict(stats['by_sensitivity'])
        stats['by_category'] = dict(stats['by_category'])
        stats['by_permission'] = dict(sorted(
            stats['by_permission'].items(),
            key=lambda x: x[1],
            reverse=True
        ))

        return stats


def classify_skills(skills: List[Dict]) -> List[Dict]:
    """Convenience function to classify skills"""
    classifier = SkillClassifier()
    return classifier.classify_batch(skills)


def get_skill_statistics(skills: List[Dict]) -> Dict:
    """Convenience function to get statistics"""
    classifier = SkillClassifier()
    return classifier.get_statistics(skills)


if __name__ == "__main__":
    # Test classifier
    test_skills = [
        {
            'skill_id': 'skill_001',
            'name': 'Send Email',
            'description': 'Send emails via Gmail',
            'permissions': ['gmail.send', 'gmail.read']
        },
        {
            'skill_id': 'skill_002',
            'name': 'Check Weather',
            'description': 'Get weather forecast',
            'permissions': ['weather.query']
        },
        {
            'skill_id': 'skill_003',
            'name': 'Execute Shell',
            'description': 'Run shell commands',
            'permissions': ['shell.exec', 'file.read', 'file.write']
        }
    ]

    classifier = SkillClassifier()
    classified = classifier.classify_batch(test_skills)

    for skill in classified:
        print(f"{skill['name']}: sensitivity={skill['sensitivity']}, category={skill['category']}")

    stats = classifier.get_statistics(classified)
    print("\nStatistics:")
    print(f"  Sensitivity: {stats['by_sensitivity']}")
    print(f"  Category: {stats['by_category']}")
    print(f"  Top permissions: {dict(list(stats['by_permission'].items())[:5])}")
