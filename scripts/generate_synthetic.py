#!/usr/bin/env python3
"""
Generate synthetic skill data for testing when GitHub API is rate limited.
"""
import hashlib
import random
from pathlib import Path
from typing import List, Dict
from datetime import datetime


# Common skill categories
CATEGORIES = [
    'communication', 'productivity', 'developer', 'ai',
    'social', 'finance', 'health', 'shopping',
    'entertainment', 'utilities'
]

# Common permissions
PERMISSIONS = [
    'gmail.read', 'gmail.send', 'gmail.write',
    'slack.read', 'slack.write', 'slack.post',
    'calendar.read', 'calendar.write',
    'drive.read', 'drive.write', 'drive.upload',
    'file.read', 'file.write', 'file.upload',
    'http.request', 'http.proxy',
    'shell.exec', 'shell.read',
    'weather.query', 'news.read',
    'weather.location', 'weather.forecast',
]

# High risk permissions
HIGH_RISK = [
    'gmail.send', 'gmail.write', 'slack.write', 'slack.post',
    'file.upload', 'file.write', 'shell.exec', 'http.request',
    'credential.store', 'oauth.token', 'payment.process'
]

# Skill templates
SKILL_TEMPLATES = [
    {
        'name': 'Read Email',
        'description': 'Read emails from Gmail account',
        'permissions': ['gmail.read'],
        'category': 'communication',
        'inputs': {'type': 'object', 'properties': {'folder': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'emails': {'type': 'array'}}},
    },
    {
        'name': 'Send Email',
        'description': 'Send emails via Gmail',
        'permissions': ['gmail.send'],
        'category': 'communication',
        'inputs': {'type': 'object', 'properties': {'to': {'type': 'string'}, 'subject': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
    },
    {
        'name': 'Read Slack',
        'description': 'Read messages from Slack channels',
        'permissions': ['slack.read'],
        'category': 'communication',
        'inputs': {'type': 'object', 'properties': {'channel': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'messages': {'type': 'array'}}},
    },
    {
        'name': 'Post to Slack',
        'description': 'Post messages to Slack channels',
        'permissions': ['slack.write', 'slack.post'],
        'category': 'communication',
        'inputs': {'type': 'object', 'properties': {'channel': {'type': 'string'}, 'message': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
    },
    {
        'name': 'Read Calendar',
        'description': 'Read calendar events',
        'permissions': ['calendar.read'],
        'category': 'productivity',
        'inputs': {'type': 'object', 'properties': {'date': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'events': {'type': 'array'}}},
    },
    {
        'name': 'Write Calendar',
        'description': 'Create calendar events',
        'permissions': ['calendar.write'],
        'category': 'productivity',
        'inputs': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'time': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'event_id': {'type': 'string'}}},
    },
    {
        'name': 'Read Google Drive',
        'description': 'Read files from Google Drive',
        'permissions': ['drive.read'],
        'category': 'productivity',
        'inputs': {'type': 'object', 'properties': {'folder_id': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'files': {'type': 'array'}}},
    },
    {
        'name': 'Upload to Drive',
        'description': 'Upload files to Google Drive',
        'permissions': ['drive.write', 'drive.upload'],
        'category': 'productivity',
        'inputs': {'type': 'object', 'properties': {'filename': {'type': 'string'}, 'content': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'file_id': {'type': 'string'}}},
    },
    {
        'name': 'Read File',
        'description': 'Read files from filesystem',
        'permissions': ['file.read'],
        'category': 'developer',
        'inputs': {'type': 'object', 'properties': {'path': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'content': {'type': 'string'}}},
    },
    {
        'name': 'Write File',
        'description': 'Write files to filesystem',
        'permissions': ['file.write'],
        'category': 'developer',
        'inputs': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
    },
    {
        'name': 'Upload File',
        'description': 'Upload files to external servers',
        'permissions': ['file.upload'],
        'category': 'developer',
        'inputs': {'type': 'object', 'properties': {'file': {'type': 'string'}, 'url': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
    },
    {
        'name': 'HTTP Request',
        'description': 'Make HTTP requests',
        'permissions': ['http.request'],
        'category': 'developer',
        'inputs': {'type': 'object', 'properties': {'url': {'type': 'string'}, 'method': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'status': {'type': 'number'}, 'body': {'type': 'string'}}},
    },
    {
        'name': 'Execute Shell',
        'description': 'Execute shell commands',
        'permissions': ['shell.exec'],
        'category': 'developer',
        'inputs': {'type': 'object', 'properties': {'command': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'stdout': {'type': 'string'}, 'stderr': {'type': 'string'}}},
    },
    {
        'name': 'Get Weather',
        'description': 'Get weather forecast',
        'permissions': ['weather.query'],
        'category': 'utilities',
        'inputs': {'type': 'object', 'properties': {'location': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'temperature': {'type': 'number'}, 'condition': {'type': 'string'}}},
    },
    {
        'name': 'Read News',
        'description': 'Read latest news',
        'permissions': ['news.read'],
        'category': 'utilities',
        'inputs': {'type': 'object', 'properties': {'topic': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'articles': {'type': 'array'}}},
    },
    {
        'name': 'Store Credential',
        'description': 'Store credentials securely',
        'permissions': ['credential.store'],
        'category': 'security',
        'inputs': {'type': 'object', 'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
    },
    {
        'name': 'Get OAuth Token',
        'description': 'Get OAuth access tokens',
        'permissions': ['oauth.token'],
        'category': 'security',
        'inputs': {'type': 'object', 'properties': {'service': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'token': {'type': 'string'}}},
    },
    {
        'name': 'Process Payment',
        'description': 'Process payments',
        'permissions': ['payment.process'],
        'category': 'finance',
        'inputs': {'type': 'object', 'properties': {'amount': {'type': 'number'}, 'currency': {'type': 'string'}}},
        'outputs': {'type': 'object', 'properties': {'transaction_id': {'type': 'string'}}},
    },
]


def generate_synthetic_skills(count: int = 200) -> List[Dict]:
    """Generate synthetic skill data for testing"""
    skills = []
    used_names = set()

    for i in range(count):
        # Use template or generate random
        if i < len(SKILL_TEMPLATES):
            template = SKILL_TEMPLATES[i]
            name = template['name']
        else:
            # Generate random skill
            name = f"Skill_{i}"
            template = {
                'name': name,
                'description': f"Generated skill {i}",
                'permissions': random.sample(PERMISSIONS, random.randint(1, 3)),
                'category': random.choice(CATEGORIES),
                'inputs': {'type': 'object'},
                'outputs': {'type': 'object'},
            }

        # Add variation
        if name in used_names:
            name = f"{name}_{i}"
        used_names.add(name)

        # Generate ID
        skill_id = f"skill_{name.lower().replace(' ', '_')}_{hashlib.md5(name.encode()).hexdigest()[:6]}"

        # Determine sensitivity
        perms = template['permissions']
        if any(p in HIGH_RISK for p in perms):
            sensitivity = 'high'
        elif len(perms) > 2:
            sensitivity = 'medium'
        else:
            sensitivity = 'low'

        skill = {
            'skill_id': skill_id,
            'name': name,
            'description': template['description'],
            'category': template['category'],
            'permissions': perms,
            'sensitivity': sensitivity,
            'inputs': template.get('inputs', {}),
            'outputs': template.get('outputs', {}),
            'markdown_content': f"# {name}\n\n{template['description']}\n\nPermissions: {', '.join(perms)}",
            'source_url': f"https://example.com/skills/{skill_id}",
            'scraped_at': datetime.now().isoformat(),
            'popularity': {
                'downloads': random.randint(100, 10000),
                'stars': random.randint(0, 500),
            }
        }

        skills.append(skill)

    return skills


if __name__ == "__main__":
    skills = generate_synthetic_skills(200)
    print(f"Generated {len(skills)} synthetic skills")

    # Save to JSON
    import json
    with open('datasets/raw/synthetic_skills.json', 'w') as f:
        json.dump(skills, f, indent=2)

    print("Saved to datasets/raw/synthetic_skills.json")
