#!/usr/bin/env python3
"""
One-off script to fix swapped media_type and media_length fields in YAML files.

The fields were swapped in the data:
- media_type had the numeric length
- media_length had the MIME type

This script swaps them back to the correct values.
"""

from pathlib import Path
import yaml


def fix_yaml_file(yaml_path: Path, dry_run: bool = True):
    """Fix swapped media fields in a single YAML file."""
    print(f"\nProcessing: {yaml_path.name}")

    with yaml_path.open() as f:
        data = yaml.safe_load(f)

    if 'feed' not in data:
        print("  No feed section found, skipping.")
        return

    fixed_count = 0

    for item in data['feed']:
        media_type = item.get('media_type')
        media_length = item.get('media_length')

        # Check if they're swapped (type is numeric, length is string MIME type)
        if media_type and media_length:
            if isinstance(media_type, int) and isinstance(media_length, str) and '/' in media_length:
                # Swap them
                item['media_type'], item['media_length'] = item['media_length'], item['media_type']
                fixed_count += 1

    print(f"  Fixed {fixed_count} items")

    if not dry_run and fixed_count > 0:
        # Write back to file
        with yaml_path.open('w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  ✓ File updated")
    elif dry_run and fixed_count > 0:
        print(f"  (Dry run - no changes made)")


def main():
    """Run fix on all media YAML files."""
    media_dir = Path("media")
    yaml_files = sorted(media_dir.glob("media_*.yml"))

    print("="*80)
    print("MEDIA FIELD FIX SCRIPT")
    print("="*80)
    print(f"\nFound {len(yaml_files)} YAML files to process")

    # First, do a dry run
    print("\n" + "="*80)
    print("DRY RUN - Preview of changes")
    print("="*80)

    for yaml_file in yaml_files:
        fix_yaml_file(yaml_file, dry_run=True)

    # Ask for confirmation
    print("\n" + "="*80)
    response = input("\nDo you want to apply these changes? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        print("\n" + "="*80)
        print("APPLYING CHANGES")
        print("="*80)

        for yaml_file in yaml_files:
            fix_yaml_file(yaml_file, dry_run=False)

        print("\n✓ Fix complete!")
    else:
        print("\nFix cancelled.")


if __name__ == "__main__":
    main()
