"""
Skill data storage using SQLite.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .schemas import Skill, get_sensitivity, permissions_to_vector


class SkillStorage:
    """Skill data storage using SQLite"""

    def __init__(self, db_path: str = "datasets/skills.db"):
        self.db_path = db_path
        self.output_dir = Path(db_path).parent
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Skills table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                markdown_content TEXT,
                inputs TEXT,
                outputs TEXT,
                permissions TEXT,
                dependencies TEXT,
                popularity TEXT,
                category TEXT,
                tags TEXT,
                source_url TEXT,
                scraped_at TEXT,
                content_hash TEXT,
                sensitivity TEXT DEFAULT 'low',
                perm_vector TEXT
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensitivity ON skills(sensitivity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON skills(category)')

        conn.commit()
        conn.close()

    def save(self, skills: List[Dict], replace: bool = True):
        """Save skills to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for skill in skills:
            # Serialize JSON fields
            inputs_json = json.dumps(skill.get('inputs', {}))
            outputs_json = json.dumps(skill.get('outputs', {}))
            permissions_json = json.dumps(skill.get('permissions', []))
            dependencies_json = json.dumps(skill.get('dependencies', []))
            popularity_json = json.dumps(skill.get('popularity', {}))
            tags_json = json.dumps(skill.get('tags', []))

            # Compute sensitivity and permission vector
            permissions = skill.get('permissions', [])
            sensitivity = get_sensitivity(permissions)
            perm_vector = permissions_to_vector(permissions)

            if replace:
                sql = '''
                    INSERT OR REPLACE INTO skills
                    (skill_id, name, description, markdown_content, inputs, outputs,
                     permissions, dependencies, popularity, category, tags, source_url,
                     scraped_at, content_hash, sensitivity, perm_vector)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            else:
                sql = '''
                    INSERT INTO skills
                    (skill_id, name, description, markdown_content, inputs, outputs,
                     permissions, dependencies, popularity, category, tags, source_url,
                     scraped_at, content_hash, sensitivity, perm_vector)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''

            cursor.execute(sql, (
                skill.get('skill_id'),
                skill.get('name', ''),
                skill.get('description', ''),
                skill.get('markdown_content', ''),
                inputs_json,
                outputs_json,
                permissions_json,
                dependencies_json,
                popularity_json,
                skill.get('category', ''),
                tags_json,
                skill.get('source_url', ''),
                skill.get('scraped_at', datetime.now().isoformat()),
                skill.get('content_hash', ''),
                sensitivity,
                json.dumps(perm_vector)
            ))

        conn.commit()
        conn.close()

        print(f"Saved {len(skills)} skills to {self.db_path}")

    def load(
        self,
        sensitivity: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Load skills from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        conditions = []
        params = []

        if sensitivity:
            conditions.append("sensitivity = ?")
            params.append(sensitivity)

        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        limit_clause = f"LIMIT {limit}" if limit else ""

        sql = f"SELECT * FROM skills WHERE {where_clause} {limit_clause}"

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # Convert to dicts
        skills = []
        for row in rows:
            skill = dict(row)

            # Parse JSON fields
            for field in ['inputs', 'outputs', 'permissions', 'dependencies',
                         'popularity', 'tags', 'perm_vector']:
                if skill.get(field):
                    try:
                        skill[field] = json.loads(skill[field])
                    except json.JSONDecodeError:
                        skill[field] = []
                else:
                    if field == 'perm_vector':
                        skill[field] = []
                    else:
                        skill[field] = []

            skills.append(skill)

        return skills

    def get_skill(self, skill_id: str) -> Optional[Dict]:
        """Get a single skill by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        skill = dict(row)

        # Parse JSON fields
        for field in ['inputs', 'outputs', 'permissions', 'dependencies',
                     'popularity', 'tags', 'perm_vector']:
            if skill.get(field):
                try:
                    skill[field] = json.loads(skill[field])
                except json.JSONDecodeError:
                    skill[field] = []
            else:
                if field == 'perm_vector':
                    skill[field] = []
                else:
                    skill[field] = []

        return skill

    def count(self, sensitivity: Optional[str] = None) -> int:
        """Count skills in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if sensitivity:
            cursor.execute(
                "SELECT COUNT(*) FROM skills WHERE sensitivity = ?",
                (sensitivity,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM skills")

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_categories(self) -> List[str]:
        """Get all categories"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT category FROM skills WHERE category != ''")
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()

        return categories

    def get_permission_mapping(self) -> Dict[str, int]:
        """Get permission to index mapping"""
        from .schemas import PERMISSION_TO_IDX
        return PERMISSION_TO_IDX

    def query_by_permissions(self, permissions: List[str]) -> List[Dict]:
        """Query skills by permissions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build JSON query
        conditions = []
        for perm in permissions:
            conditions.append(f"permissions LIKE '%\"{perm}\"%'")

        where_clause = " OR ".join(conditions)
        sql = f"SELECT * FROM skills WHERE {where_clause}"

        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()

        # Convert to dicts
        skills = []
        for row in rows:
            skill = dict(row)
            for field in ['inputs', 'outputs', 'permissions', 'dependencies',
                         'popularity', 'tags', 'perm_vector']:
                if skill.get(field):
                    try:
                        skill[field] = json.loads(skill[field])
                    except json.JSONDecodeError:
                        skill[field] = []
                else:
                    skill[field] = []
            skills.append(skill)

        return skills

    def export_to_parquet_format(self, output_path: Path):
        """Export to format compatible with parquet"""
        skills = self.load()

        # Convert to DataFrame-friendly format
        export_data = []
        for skill in skills:
            export_data.append({
                'skill_id': skill['skill_id'],
                'name': skill['name'],
                'description': skill['description'],
                'markdown_content': skill['markdown_content'],
                'inputs': json.dumps(skill.get('inputs', {})),
                'outputs': json.dumps(skill.get('outputs', {})),
                'permissions': json.dumps(skill.get('permissions', [])),
                'category': skill.get('category', ''),
                'sensitivity': skill.get('sensitivity', 'low'),
                'perm_vector': json.dumps(skill.get('perm_vector', [])),
            })

        return export_data


def create_storage(db_path: str = "datasets/skills.db") -> SkillStorage:
    """Convenience function to create storage"""
    return SkillStorage(db_path)


if __name__ == "__main__":
    # Test storage
    storage = SkillStorage("test_skills.db")

    # Save test data
    test_skills = [
        {
            'skill_id': 'skill_test_001',
            'name': 'Test Skill',
            'description': 'A test skill',
            'markdown_content': '# Test\n\nSome content',
            'permissions': ['gmail.read', 'slack.write'],
            'category': 'productivity',
            'scraped_at': datetime.now().isoformat()
        },
        {
            'skill_id': 'skill_test_002',
            'name': 'Another Skill',
            'description': 'Another test',
            'markdown_content': '# Another\n\nContent',
            'permissions': ['search.query'],
            'category': 'utility',
            'scraped_at': datetime.now().isoformat()
        }
    ]

    storage.save(test_skills)
    print(f"Total skills: {storage.count()}")
    print(f"High sensitivity: {storage.count('high')}")

    loaded = storage.load()
    print(f"Loaded: {len(loaded)} skills")
