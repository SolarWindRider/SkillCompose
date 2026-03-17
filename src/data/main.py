#!/usr/bin/env python3
"""
Data collection main entry point.

Usage:
    python -m src.data.main                    # Use default settings
    python -m src.data.main --github-token TOKEN  # With GitHub token
    python -m src.data.main --repo OWNER/REPO      # Custom repo
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.collector import collect_skills
from src.data.cleaner import clean_skills
from src.data.classifier import classify_skills, get_skill_statistics
from src.data.storage import SkillStorage


def main():
    parser = argparse.ArgumentParser(description="Collect and process skills from ClawHub")

    parser.add_argument(
        '--output', '-o',
        type=str,
        default='datasets',
        help='Output directory'
    )

    parser.add_argument(
        '--db', '-d',
        type=str,
        default='datasets/skills.db',
        help='SQLite database path'
    )

    parser.add_argument(
        '--github-token', '-t',
        type=str,
        default=None,
        help='GitHub token for API access'
    )

    parser.add_argument(
        '--repo', '-r',
        type=str,
        default='VoltAgent/awesome-openclaw-skills',
        help='GitHub repository to collect from'
    )

    parser.add_argument(
        '--skip-clean',
        action='store_true',
        help='Skip cleaning step'
    )

    parser.add_argument(
        '--skip-classify',
        action='store_true',
        help='Skip classification step'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SkillCompose Data Collection")
    print("=" * 60)

    # Step 1: Collect skills
    print("\n[1/4] Collecting skills...")
    print(f"  Repository: {args.repo}")
    print(f"  Output: {output_dir}")

    try:
        skills = collect_skills(output_dir, args.github_token, args.repo)
        print(f"  Collected: {len(skills)} raw skills")
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    if not skills:
        print("  No skills collected!")
        return 1

    # Step 2: Clean skills
    if not args.skip_clean:
        print("\n[2/4] Cleaning skills...")

        try:
            skills = clean_skills(skills)
            print(f"  After cleaning: {len(skills)} skills")
        except Exception as e:
            print(f"  ERROR: {e}")
            return 1
    else:
        print("\n[2/4] Skipping cleaning")

    # Step 3: Classify skills
    if not args.skip_classify:
        print("\n[3/4] Classifying skills...")

        try:
            skills = classify_skills(skills)
            stats = get_skill_statistics(skills)

            print(f"  By sensitivity:")
            for sens, count in stats['by_sensitivity'].items():
                print(f"    {sens}: {count}")

            print(f"  By category:")
            for cat, count in sorted(stats['by_category'].items(), key=lambda x: -x[1])[:5]:
                print(f"    {cat}: {count}")

            print(f"  Top permissions:")
            for perm, count in list(stats['by_permission'].items())[:5]:
                print(f"    {perm}: {count}")

        except Exception as e:
            print(f"  ERROR: {e}")
            return 1
    else:
        print("\n[3/4] Skipping classification")

    # Step 4: Save to database
    print("\n[4/4] Saving to database...")

    try:
        storage = SkillStorage(args.db)
        storage.save(skills)

        print(f"  Total in database: {storage.count()}")
        print(f"  High sensitivity: {storage.count('high')}")
        print(f"  Medium sensitivity: {storage.count('medium')}")
        print(f"  Low sensitivity: {storage.count('low')}")

    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
