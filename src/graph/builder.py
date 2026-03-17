"""
Skill Dependency Graph Builder.

Builds a directed graph of skill dependencies using NetworkX.
"""
import re
import networkx as nx
import pickle
import json
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import numpy as np


class SkillGraphBuilder:
    """Build skill dependency graph"""

    def __init__(self, permission_mapping: Dict[str, int]):
        self.perm_mapping = permission_mapping
        self.perm_count = len(permission_mapping)
        self.graph = nx.DiGraph()

    def build(self, skills: List[Dict], max_nodes: int = 2000) -> nx.DiGraph:
        """Build complete dependency graph

        Args:
            skills: List of skill dictionaries
            max_nodes: Maximum number of nodes (use top-k by priority)

        Returns:
            NetworkX directed graph
        """

        # Select top-k skills
        skills = self._select_top_skills(skills, max_nodes)

        # Add nodes
        print(f"Adding {len(skills)} nodes...")
        for skill in skills:
            self._add_node(skill)

        # Build edges
        print("Building edges...")
        edge_count = self._build_edges(skills)
        print(f"  Total edges: {edge_count}")

        print(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        return self.graph

    def _select_top_skills(self, skills: List[Dict], max_nodes: int) -> List[Dict]:
        """Select top-k high-value skills"""

        def compute_priority(skill: Dict) -> float:
            # Weight: sensitivity * popularity
            sens_map = {'high': 3, 'medium': 2, 'low': 1}
            sensitivity = sens_map.get(skill.get('sensitivity', 'low'), 1)

            popularity = skill.get('popularity', {})
            downloads = popularity.get('downloads', 0)
            stars = popularity.get('stars', 0)

            # Permission count bonus
            perm_count = len(skill.get('permissions', []))

            return sensitivity * 10 + perm_count + stars * 0.1 + downloads * 0.001

        sorted_skills = sorted(skills, key=compute_priority, reverse=True)
        return sorted_skills[:max_nodes]

    def _add_node(self, skill: Dict):
        """Add a skill node to the graph"""
        skill_id = skill['skill_id']

        # Get permission vector
        permissions = skill.get('permissions', [])
        perm_vector = skill.get('perm_vector', [0] * self.perm_count)

        # If perm_vector not provided, compute it
        if not perm_vector or len(perm_vector) != self.perm_count:
            perm_vector = self._compute_perm_vector(permissions)

        self.graph.add_node(
            skill_id,
            name=skill.get('name', ''),
            description=skill.get('description', ''),
            markdown=skill.get('markdown_content', ''),
            category=skill.get('category', 'other'),
            sensitivity=skill.get('sensitivity', 'low'),
            permissions=permissions,
            perm_vector=perm_vector,
            inputs=skill.get('inputs', {}),
            outputs=skill.get('outputs', {}),
        )

    def _compute_perm_vector(self, permissions: List[str]) -> List[int]:
        """Compute permission vector"""
        vector = [0] * self.perm_count
        for perm in permissions:
            if perm in self.perm_mapping:
                vector[self.perm_mapping[perm]] = 1
        return vector

    def _build_edges(self, skills: List[Dict]) -> int:
        """Build all edges"""
        total_edges = 0

        # Build explicit edges
        explicit = self._build_explicit_edges(skills)
        print(f"  Explicit edges: {explicit}")
        total_edges += explicit

        # Build implicit edges
        implicit = self._build_implicit_edges(skills)
        print(f"  Implicit edges: {implicit}")
        total_edges += implicit

        return total_edges

    def _build_explicit_edges(self, skills: List[Dict]) -> int:
        """Build explicit dependency edges

        Uses the real dependencies field from skill.yaml
        """
        edge_count = 0

        # Build skill_id -> name mapping
        skill_ids = {s['skill_id'] for s in skills}
        name_to_id = {}
        for skill in skills:
            name = skill.get('name', '').lower().replace(' ', '_')
            if name:
                name_to_id[name] = skill['skill_id']

        # Also create a mapping from skill path to ID
        path_to_id = {}
        for skill in skills:
            url = skill.get('source_url', '')
            # Extract path from URL like https://github.com/openclaw/skills/tree/main/skills/author/name
            match = re.search(r'tree/main/(skills/[^\s]+)', url)
            if match:
                path_to_id[match.group(1)] = skill['skill_id']
                # Also map just the skill name
                path_to_id[match.group(1).split('/')[-1]] = skill['skill_id']

        for skill in skills:
            skill_id = skill['skill_id']

            # Get dependencies from skill.yaml
            dependencies = skill.get('dependencies', [])
            if not dependencies:
                dependencies = []

            for dep in dependencies:
                # Try to find the dependency skill ID
                target_id = None

                # Check if dep is a skill_id
                if dep in skill_ids:
                    target_id = dep
                # Check if dep is a name
                elif dep in name_to_id:
                    target_id = name_to_id[dep]
                # Check if dep is a path
                elif dep in path_to_id:
                    target_id = path_to_id[dep]

                if target_id and target_id != skill_id:
                    if not self.graph.has_edge(skill_id, target_id):
                        self.graph.add_edge(
                            skill_id, target_id,
                            edge_type='explicit',
                            weight=1.0  # Real dependencies have higher weight
                        )
                        edge_count += 1

        return edge_count

    def _build_implicit_edges(self, skills: List[Dict]) -> int:
        """Build implicit edges based on privilege escalation

        Build edges from lower-privilege skills to higher-privilege skills.
        This represents potential privilege escalation paths.
        """
        edge_count = 0

        # Define permission risk levels
        # Level 0 (lowest): read-only, query permissions
        # Level 1 (medium): write, send permissions
        # Level 2 (high): exec, credential, payment permissions
        perm_risk = {
            # Level 0: read-only
            'weather.query': 0, 'news.read': 0, 'search.query': 0,
            'calendar.read': 0, 'drive.read': 0, 'file.read': 0,
            'gmail.read': 0, 'slack.read': 0,
            # Level 1: write/send
            'calendar.write': 1, 'drive.write': 1, 'file.write': 1,
            'gmail.send': 1, 'slack.write': 1, 'slack.post': 1,
            'news.write': 1,
            # Level 2: highest risk
            'file.upload': 2, 'shell.exec': 2, 'http.request': 2,
            'credential.store': 2, 'oauth.token': 2, 'payment.process': 2,
        }

        def get_skill_risk_level(skill: Dict) -> int:
            """Get the highest risk level of a skill's permissions"""
            perms = skill.get('permissions', [])
            if not perms:
                return 0  # No permissions = lowest risk
            max_level = 0
            for perm in perms:
                level = perm_risk.get(perm, 0)
                max_level = max(max_level, level)
            return max_level

        # Assign risk levels to all skills
        for skill in skills:
            risk_level = get_skill_risk_level(skill)
            perms = skill.get('permissions', [])
            skill['_risk_level'] = risk_level
            skill['_has_permissions'] = len(perms) > 0

        # Get skills by risk level
        level_0 = [s for s in skills if s.get('_risk_level') == 0 and s.get('_has_permissions')]
        level_1 = [s for s in skills if s.get('_risk_level') == 1 and s.get('_has_permissions')]
        level_2 = [s for s in skills if s.get('_risk_level') == 2 and s.get('_has_permissions')]

        print(f"    Level 0 (read-only): {len(level_0)}")
        print(f"    Level 1 (write/send): {len(level_1)}")
        print(f"    Level 2 (exec/credential): {len(level_2)}")

        # Build edges: lower risk -> higher risk
        # Level 0 -> Level 1 -> Level 2
        # Only connect skills that actually have permissions

        # Level 0 -> Level 1
        for skill_a in level_0:
            for skill_b in level_1:
                if not self.graph.has_edge(skill_a['skill_id'], skill_b['skill_id']):
                    self.graph.add_edge(
                        skill_a['skill_id'], skill_b['skill_id'],
                        edge_type='privilege_escalation',
                        weight=0.6,
                        risk_level_a=0,
                        risk_level_b=1
                    )
                    edge_count += 1

        # Level 0 -> Level 2 (direct escalation)
        for skill_a in level_0:
            for skill_b in level_2:
                if not self.graph.has_edge(skill_a['skill_id'], skill_b['skill_id']):
                    self.graph.add_edge(
                        skill_a['skill_id'], skill_b['skill_id'],
                        edge_type='privilege_escalation',
                        weight=0.9,
                        risk_level_a=0,
                        risk_level_b=2
                    )
                    edge_count += 1

        # Level 1 -> Level 2
        for skill_a in level_1:
            for skill_b in level_2:
                if not self.graph.has_edge(skill_a['skill_id'], skill_b['skill_id']):
                    self.graph.add_edge(
                        skill_a['skill_id'], skill_b['skill_id'],
                        edge_type='privilege_escalation',
                        weight=0.8,
                        risk_level_a=1,
                        risk_level_b=2
                    )
                    edge_count += 1

        return edge_count

    def _build_output_index(self, skills: List[Dict]) -> Dict[str, List[str]]:
        """Build output type -> skill ID index"""
        index = {}

        for skill in skills:
            outputs = self._extract_types(skill.get('outputs', {}))
            for out_type in outputs:
                if out_type not in index:
                    index[out_type] = []
                index[out_type].append(skill['skill_id'])

        return index

    def _extract_types(self, schema: Dict) -> List[str]:
        """Extract types from JSON Schema"""
        types = []

        if not schema:
            return types

        # Direct type
        if 'type' in schema:
            types.append(schema['type'])

        # Properties
        if 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                if 'type' in prop_schema:
                    types.append(prop_schema['type'])

        return types

    def _is_compatible(self, output_type: str, input_types: List[str]) -> bool:
        """Check if output type is compatible with input types"""
        output_type = output_type.lower()
        input_types = [t.lower() for t in input_types]

        if output_type in input_types:
            return True

        # Type hierarchy
        compatibility = {
            'text': ['string', 'str', 'str'],
            'file': ['binary', 'buffer', 'bytes'],
            'json': ['object', 'dict', 'map'],
            'url': ['uri', 'link'],
        }

        for base, variants in compatibility.items():
            if output_type in [base] + variants:
                return any(t in [base] + variants for t in input_types)

        return False

    def get_sink_skills(self, permissions: Set[str] = None) -> List[str]:
        """Get high-risk sink skills"""

        sinks = []

        for node in self.graph.nodes():
            if permissions:
                node_perms = set(self.graph.nodes[node].get('permissions', []))
                if not (node_perms & permissions):
                    continue

            # Check if node has edges (is a sink)
            if self.graph.out_degree(node) > 0:
                sinks.append(node)

        return sinks

    def find_attack_paths(
        self,
        source: str,
        sink: str,
        max_length: int = 5
    ) -> List[List[str]]:
        """Find attack paths from source to sink"""

        try:
            paths = list(nx.all_simple_paths(
                self.graph,
                source,
                sink,
                cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []

    def find_paths_to_sink(
        self,
        sink: str,
        max_length: int = 5
    ) -> List[List[str]]:
        """Find all paths to a sink skill"""

        reversed_graph = self.graph.reverse()
        paths = []

        for source in self.graph.nodes():
            if source == sink:
                continue

            try:
                source_paths = list(nx.all_simple_paths(
                    reversed_graph,
                    sink,  # Reverse: from sink
                    source,
                    cutoff=max_length
                ))
                # Reverse paths back to source -> sink
                paths.extend([list(reversed(p)) for p in source_paths])
            except nx.NetworkXNoPath:
                continue

        return paths

    def compute_path_risk(self, path: List[str]) -> float:
        """Compute risk score for a path"""

        if len(path) < 2:
            return 0.0

        # Risk factors:
        # 1. Path length (longer = harder)
        # 2. Permission escalation
        # 3. High-sensitivity skills

        risk = 0.0
        prev_perms = set()

        for skill_id in path:
            node = self.graph.nodes[skill_id]
            perms = set(node.get('permissions', []))

            # Permission escalation
            new_perms = perms - prev_perms
            if new_perms:
                risk += len(new_perms) * 0.3

            # High sensitivity bonus
            if node.get('sensitivity') == 'high':
                risk += 0.5

            prev_perms = perms

        # Path length penalty (slightly)
        risk += len(path) * 0.1

        return risk

    def save(self, path: Path):
        """Save graph to file"""
        with open(path, 'wb') as f:
            pickle.dump(self.graph, f)
        print(f"Graph saved to {path}")

    def load(self, path: Path):
        """Load graph from file"""
        with open(path, 'rb') as f:
            self.graph = pickle.load(f)
        print(f"Graph loaded from {path}")


def build_skill_graph(
    skills: List[Dict],
    permission_mapping: Dict[str, int],
    max_nodes: int = 2000
) -> nx.DiGraph:
    """Convenience function to build skill graph"""
    builder = SkillGraphBuilder(permission_mapping)
    return builder.build(skills, max_nodes)


if __name__ == "__main__":
    # Test with sample data
    test_skills = [
        {
            'skill_id': 'skill_read_email',
            'name': 'Read Email',
            'description': 'Read emails from Gmail',
            'markdown_content': '# Read Email\n\nReads emails. Depends on skill_send_email.',
            'permissions': ['gmail.read'],
            'sensitivity': 'high',
            'inputs': {'type': 'object', 'properties': {'folder': {'type': 'string'}}},
            'outputs': {'type': 'object', 'properties': {'emails': {'type': 'array'}}},
            'category': 'communication',
        },
        {
            'skill_id': 'skill_send_email',
            'name': 'Send Email',
            'description': 'Send emails via Gmail',
            'markdown_content': '# Send Email\n\nSends emails.',
            'permissions': ['gmail.send'],
            'sensitivity': 'high',
            'inputs': {'type': 'object', 'properties': {'to': {'type': 'string'}}},
            'outputs': {'type': 'object', 'properties': {'success': {'type': 'boolean'}}},
            'category': 'communication',
        },
        {
            'skill_id': 'skill_weather',
            'name': 'Get Weather',
            'description': 'Get weather forecast',
            'markdown_content': '# Weather\n\nGets weather.',
            'permissions': ['weather.query'],
            'sensitivity': 'low',
            'inputs': {},
            'outputs': {'type': 'object'},
            'category': 'utility',
        }
    ]

    perm_mapping = {'gmail.read': 0, 'gmail.send': 1, 'weather.query': 2}

    builder = SkillGraphBuilder(perm_mapping)
    graph = builder.build(test_skills)

    print(f"\nGraph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print(f"Edges: {list(graph.edges())}")

    paths = builder.find_attack_paths('skill_weather', 'skill_send_email')
    print(f"\nPaths from weather to send_email: {paths}")
