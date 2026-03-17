#!/usr/bin/env python3
"""
SkillCompose - Main Entry Point

Usage:
    python -m src.main --help
    python -m src.main --collect                    # Collect skills
    python -m src.main --build-graph              # Build dependency graph
    python -m src.main --generate-attacks          # Generate attack samples
    python -m src.main --evaluate                  # Evaluate attacks
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data import (
    SkillStorage,
    collect_skills,
    clean_skills,
    classify_skills,
    get_skill_statistics,
    PERMISSION_TO_IDX
)
from src.graph import build_skill_graph
from src.attack import AttackGenerator, AttackType
from src.eval import compute_attack_metrics


def main():
    parser = argparse.ArgumentParser(
        description="SkillCompose - Compositional Attack Benchmark"
    )

    parser.add_argument(
        '--collect',
        action='store_true',
        help='Collect skills from ClawHub'
    )

    parser.add_argument(
        '--synthetic',
        action='store_true',
        help='Use synthetic data (for testing when API is rate limited)'
    )

    parser.add_argument(
        '--reprocess',
        action='store_true',
        help='Reprocess existing data in database'
    )

    parser.add_argument(
        '--build-graph',
        action='store_true',
        help='Build skill dependency graph'
    )

    parser.add_argument(
        '--generate-attacks',
        action='store_true',
        help='Generate attack samples'
    )

    parser.add_argument(
        '--evaluate',
        action='store_true',
        help='Evaluate attack samples'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='datasets/skills.db',
        help='SQLite database path'
    )

    parser.add_argument(
        '--graph',
        type=str,
        default='datasets/graph.pkl',
        help='Graph output path'
    )

    parser.add_argument(
        '--attacks',
        type=str,
        default='datasets/attack_samples.jsonl',
        help='Attack samples output path'
    )

    parser.add_argument(
        '--github-token',
        type=str,
        default=None,
        help='GitHub token'
    )

    parser.add_argument(
        '--max-nodes',
        type=int,
        default=2000,
        help='Max graph nodes'
    )

    parser.add_argument(
        '--attack-count',
        type=int,
        default=1000,
        help='Number of attacks to generate'
    )

    args = parser.parse_args()

    # If no action specified, show help
    if not any([args.collect, args.reprocess, args.build_graph, args.generate_attacks, args.evaluate]):
        parser.print_help()
        return 0

    print("=" * 60)
    print("SkillCompose")
    print("=" * 60)

    if args.collect:
        print("\n[1] Collecting skills...")

        if args.synthetic:
            # Load synthetic data
            print("  Using synthetic data (for testing)...")
            import json
            synthetic_path = project_root / "datasets" / "syn" / "synthetic_skills.json"
            if synthetic_path.exists():
                with open(synthetic_path, 'r') as f:
                    skills = json.load(f)
                print(f"  Loaded: {len(skills)} synthetic skills")
            else:
                print("  Generating synthetic skills...")
                import sys
                sys.path.insert(0, str(project_root / "scripts"))
                from generate_synthetic import generate_synthetic_skills
                skills = generate_synthetic_skills(200)
        else:
            output_dir = Path("datasets/syn")
            output_dir.mkdir(parents=True, exist_ok=True)

            skills = collect_skills(
                output_dir,
                args.github_token,
                "VoltAgent/awesome-openclaw-skills"
            )
            print(f"  Collected: {len(skills)} skills")

        # Clean
        print("\n[2] Cleaning skills...")
        skills = clean_skills(skills)
        print(f"  After cleaning: {len(skills)}")

        # Classify (this now generates permissions for skills without them)
        print("\n[3] Classifying skills...")
        skills = classify_skills(skills)
        stats = get_skill_statistics(skills)
        print(f"  High sensitivity: {stats['by_sensitivity'].get('high', 0)}")
        print(f"  Medium sensitivity: {stats['by_sensitivity'].get('medium', 0)}")
        print(f"  Low sensitivity: {stats['by_sensitivity'].get('low', 0)}")

        # Save
        print("\n[4] Saving to database...")
        storage = SkillStorage(args.db)
        storage.save(skills)
        print(f"  Total in DB: {storage.count()}")

    if args.reprocess:
        # Reprocess existing data in database
        print("\n[1] Loading existing skills from database...")
        storage = SkillStorage(args.db)
        skills = storage.load()
        print(f"  Loaded: {len(skills)} skills")

        # Re-classify (generates permissions)
        print("\n[2] Re-classifying skills...")
        skills = classify_skills(skills)
        stats = get_skill_statistics(skills)
        print(f"  High sensitivity: {stats['by_sensitivity'].get('high', 0)}")
        print(f"  Medium sensitivity: {stats['by_sensitivity'].get('medium', 0)}")
        print(f"  Low sensitivity: {stats['by_sensitivity'].get('low', 0)}")

        # Save
        print("\n[3] Saving to database...")
        storage = SkillStorage(args.db)
        storage.save(skills)
        print(f"  Total in DB: {storage.count()}")

    if args.build_graph:
        print("\n[1] Loading skills from database...")
        storage = SkillStorage(args.db)
        skills = storage.load()
        print(f"  Loaded: {len(skills)} skills")

        print("\n[2] Building dependency graph...")
        graph = build_skill_graph(skills, PERMISSION_TO_IDX, args.max_nodes)
        print(f"  Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

        print("\n[3] Saving graph...")
        graph_path = Path(args.graph)
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        import pickle
        with open(graph_path, 'wb') as f:
            pickle.dump(graph, f)
        print(f"  Saved to: {graph_path}")

    if args.generate_attacks:
        print("\n[1] Loading graph...")
        import pickle
        graph_path = Path(args.graph)
        with open(graph_path, 'rb') as f:
            graph = pickle.load(f)
        print(f"  Loaded: {graph.number_of_nodes()} nodes")

        print("\n[2] Loading skills...")
        storage = SkillStorage(args.db)
        skills = storage.load()
        skills_dict = {s['skill_id']: s for s in skills}
        print(f"  Loaded: {len(skills_dict)} skills")

        print("\n[3] Generating attacks...")
        generator = AttackGenerator(graph, skills_dict)
        samples = generator.generate(target_count=args.attack_count)
        print(f"  Generated: {len(samples)} attacks")

        print("\n[4] Saving attacks...")
        attacks_path = Path(args.attacks)
        attacks_path.parent.mkdir(parents=True, exist_ok=True)
        generator.save_samples(samples, attacks_path)
        print(f"  Saved to: {attacks_path}")

    if args.evaluate:
        print("\n[1] Loading attack samples...")
        attacks_path = Path(args.attacks)
        generator = AttackGenerator(None, {})
        samples = generator.load_samples(attacks_path)
        print(f"  Loaded: {len(samples)} samples")

        print("\n[2] Computing metrics...")
        # Convert to dict format for metrics
        samples_dict = [s.to_dict() for s in samples]
        results = compute_attack_metrics(samples_dict)

        print(f"\nResults:")
        print(f"  Total samples: {results.total_samples}")
        print(f"  Baseline ASR: {results.end_to_end_asr:.2%}")
        print(f"  Complexity curve: {results.complexity_curve}")
        print(f"  By attack type: {results.by_attack_type}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
