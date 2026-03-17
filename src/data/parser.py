"""
Skill schema parser - extract JSON Schema from markdown using LLM.
"""
import re
import json
from typing import Dict, Optional


class SchemaParser:
    """Parse skill schema from markdown content"""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.llm_client = None
        if anthropic_api_key:
            from anthropic import Anthropic
            self.llm_client = Anthropic(api_key=anthropic_api_key)

    def parse_from_markdown(self, markdown: str) -> Dict:
        """Parse schema from markdown content"""

        # Method 1: Extract YAML/JSON code blocks
        schema = self._extract_yaml_schema(markdown)
        if schema:
            return schema

        # Method 2: Use LLM to extract (if available)
        if self.llm_client:
            return self._extract_with_llm(markdown)

        # Fallback: return empty schema
        return {"inputs": {}, "outputs": {}}

    def _extract_yaml_schema(self, markdown: str) -> Optional[Dict]:
        """Extract YAML/JSON Schema from code blocks"""
        import yaml

        # Match ```yaml or ```json code blocks
        code_block_pattern = r'```(?:yaml|json)\n(.*?)```'
        matches = re.findall(code_block_pattern, markdown, re.DOTALL)

        for match in matches:
            try:
                # Try YAML first
                schema = yaml.safe_load(match)
                if schema and isinstance(schema, dict):
                    if 'inputs' in schema or 'outputs' in schema:
                        return schema
            except yaml.YAMLError:
                pass

            try:
                # Try JSON
                schema = json.loads(match)
                if schema and isinstance(schema, dict):
                    if 'inputs' in schema or 'outputs' in schema:
                        return schema
            except json.JSONDecodeError:
                pass

        return None

    def _extract_with_llm(self, markdown: str) -> Dict:
        """Use LLM to extract schema"""

        if not self.llm_client:
            return {"inputs": {}, "outputs": {}}

        # Truncate to avoid token limits
        truncated = markdown[:8000]

        prompt = f"""从以下技能文档中提取 JSON Schema 格式的 inputs 和 outputs 定义。

技能文档:
{truncated}

请返回以下格式的 JSON (只返回 JSON，不要其他内容):
{{
    "inputs": {{"type": "object", "properties": {{...}}}},
    "outputs": {{"type": "object", "properties": {{...}}}},
    "permissions": ["gmail.read", "slack.write"]
}}"""

        try:
            response = self.llm_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON from response
            content = response.content[0].text

            # Extract JSON block
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            print(f"LLM extraction error: {e}")

        return {"inputs": {}, "outputs": {}}

    def extract_permissions_from_markdown(self, markdown: str) -> list:
        """Extract permissions from markdown"""

        # Method 1: Look for permission sections
        perm_section_pattern = r'##?\s*Permissions?[:\s]*\n(.*?)(?:\n##|\Z)'
        match = re.search(perm_section_pattern, markdown, re.DOTALL | re.IGNORECASE)

        if match:
            perm_text = match.group(1)
            # Extract permission-like strings
            perms = re.findall(r'[a-z][a-z0-9._]+', perm_text.lower())
            # Filter to likely permissions
            valid_perms = [p for p in perms if len(p) > 3]
            return list(set(valid_perms))

        # Method 2: Use LLM
        if self.llm_client:
            return self._extract_permissions_with_llm(markdown)

        return []

    def _extract_permissions_with_llm(self, markdown: str) -> list:
        """Extract permissions using LLM"""

        truncated = markdown[:5000]

        prompt = f"""从以下技能文档中提取所需权限列表。

技能文档:
{truncated}

请列出所有提到的权限 (如 gmail.read, slack.write, file.upload 等)。
只返回权限列表，格式: ["permission1", "permission2"]
"""

        try:
            response = self.llm_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Try to parse as JSON
            if '[' in content:
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())

        except Exception as e:
            print(f"LLM permission extraction error: {e}")

        return []


def parse_markdown_schema(markdown: str, api_key: Optional[str] = None) -> Dict:
    """Convenience function to parse schema"""
    parser = SchemaParser(api_key)
    return parser.parse_from_markdown(markdown)


if __name__ == "__main__":
    # Test parser
    test_markdown = '''
# Send Email

Send an email using Gmail.

## Inputs

```yaml
type: object
properties:
  to:
    type: string
    description: Recipient email
  subject:
    type: string
  body:
    type: string
required: [to, subject]
```

## Outputs

```json
{
  "success": true,
  "message_id": "abc123"
}
```

## Permissions

- gmail.send
- gmail.read
'''

    parser = SchemaParser()
    schema = parser.parse_from_markdown(test_markdown)
    print("Schema:", json.dumps(schema, indent=2))

    perms = parser.extract_permissions_from_markdown(test_markdown)
    print("Permissions:", perms)
