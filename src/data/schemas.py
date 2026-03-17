"""
Skill data schemas and type definitions.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime
import json


@dataclass
class Skill:
    """Skill data structure"""
    skill_id: str
    name: str
    description: str = ""
    markdown_content: str = ""

    # I/O Schema (JSON Schema format)
    inputs: Dict = field(default_factory=dict)
    outputs: Dict = field(default_factory=dict)

    # Permissions
    permissions: List[str] = field(default_factory=list)

    # Dependencies
    dependencies: List[str] = field(default_factory=list)

    # Metadata
    popularity: Dict = field(default_factory=dict)
    category: str = ""
    tags: List[str] = field(default_factory=list)
    source_url: str = ""
    scraped_at: str = ""

    # Computed fields
    sensitivity: str = "low"
    perm_vector: List[int] = field(default_factory=list)

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Skill':
        return cls(**data)


# Permission tiers for sensitivity classification
PERMISSION_TIERS = {
    "high": [
        "gmail.read", "gmail.readonly", "gmail.send", "gmail.write",
        "slack.write", "slack.post", "slack.chat",
        "file.read", "file.write", "file.upload", "file.delete",
        "shell.exec", "shell.exec.root", "bash",
        "http.request", "network.connect", "network.request",
        "database.read", "database.write", "database.admin",
        "oauth.token", "credential.store", "credential.read",
        "aws.access", "aws.secret", "ssh.key",
    ],
    "medium": [
        "calendar.read", "calendar.write", "calendar.delete",
        "contacts.read", "contacts.write",
        "drive.read", "drive.write",
        "weather.query",
        "sms.send", "sms.read",
    ],
    "low": [
        "search.query",
        "calc.compute",
        "translate.text",
        "image.generate", "image.read",
        "audio.transcribe",
        "notes.read", "notes.write",
    ]
}

# Build permission to index mapping
ALL_PERMISSIONS = []
for tier in ["high", "medium", "low"]:
    ALL_PERMISSIONS.extend(PERMISSION_TIERS[tier])
ALL_PERMISSIONS = sorted(set(ALL_PERMISSIONS))

PERMISSION_TO_IDX = {perm: i for i, perm in enumerate(ALL_PERMISSIONS)}
IDX_TO_PERMISSION = {i: perm for i, perm in enumerate(ALL_PERMISSIONS)}


def get_sensitivity(permissions: List[str]) -> str:
    """Classify sensitivity based on permissions"""
    perm_set = set(permissions)

    if perm_set & set(PERMISSION_TIERS["high"]):
        return "high"
    elif perm_set & set(PERMISSION_TIERS["medium"]):
        return "medium"
    return "low"


def permissions_to_vector(permissions: List[str]) -> List[int]:
    """Convert permissions list to one-hot vector"""
    vector = [0] * len(PERMISSION_TO_IDX)
    for perm in permissions:
        if perm in PERMISSION_TO_IDX:
            vector[PERMISSION_TO_IDX[perm]] = 1
    return vector
