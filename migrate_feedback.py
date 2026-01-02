#!/usr/bin/env python3
"""
One-off script to migrate feedback from descriptions to structured feedback format.

This script:
1. Extracts feedback comments from descriptions (format: "username: comment")
2. Converts them to the new structured feedback format
3. Removes the feedback text from descriptions
"""

import re
from pathlib import Path
import yaml


def extract_feedback_from_description(description: str) -> tuple[str, list[dict]]:
    """
    Extract feedback entries from description text.

    Returns:
        Tuple of (cleaned_description, feedback_list)
    """
    # Pattern to match feedback lines: "username: comment text"
    # Usernames can be: max, tino, phil, alain, etc. (case insensitive)
    feedback_pattern = re.compile(
        r'^\s*([a-zA-Z]+):\s*(.+?)$',
        re.MULTILINE
    )

    feedback_entries = []
    lines = description.split('\n')
    cleaned_lines = []

    # Track if we're in the feedback section (usually at the end)
    in_feedback_section = False

    for line in lines:
        match = feedback_pattern.match(line)

        # Check if this looks like a feedback line
        if match:
            username = match.group(1)
            comment = match.group(2).strip()

            # Only treat as feedback if username is lowercase or starts with uppercase
            # and the comment doesn't look like part of the main description
            # (e.g., avoid matching things like "HTTP: protocol description")
            common_usernames = ['max', 'tino', 'phil', 'alain', 'Max', 'Tino', 'Phil', 'Alain']

            if username in common_usernames or (len(username) < 15 and username[0].islower()):
                in_feedback_section = True
                feedback_entries.append({
                    'username': username.lower(),  # Normalize to lowercase
                    'comment': comment
                })
                continue

        # If we're not in feedback section, keep the line
        if not in_feedback_section:
            cleaned_lines.append(line)
        # Once we hit feedback, check if this line is empty - if so, we might keep it
        # to avoid cutting off the description abruptly
        elif not line.strip():
            # Don't add trailing empty lines
            pass
        else:
            # We hit a non-feedback line after feedback started
            # This might be a continuation of feedback comment, skip it
            pass

    # Clean up the description - remove trailing whitespace and empty lines
    cleaned_description = '\n'.join(cleaned_lines).rstrip()

    return cleaned_description, feedback_entries


def migrate_yaml_file(yaml_path: Path, dry_run: bool = True):
    """Migrate a single YAML file."""
    print(f"\n{'='*80}")
    print(f"Processing: {yaml_path.name}")
    print(f"{'='*80}")

    with yaml_path.open() as f:
        data = yaml.safe_load(f)

    if 'feed' not in data:
        print("No feed section found, skipping.")
        return

    modified_count = 0

    for idx, item in enumerate(data['feed']):
        description = item.get('description', '')

        if not description:
            continue

        # Extract feedback
        cleaned_desc, feedback = extract_feedback_from_description(description)

        if feedback:
            modified_count += 1
            print(f"\n[{idx+1}] {item.get('title', 'Untitled')}")
            print(f"    Found {len(feedback)} feedback entries:")

            for entry in feedback:
                print(f"      - {entry['username']}: {entry['comment'][:60]}...")

            if not dry_run:
                # Update the item
                item['description'] = cleaned_desc
                item['feedback'] = feedback

    print(f"\nTotal items modified: {modified_count}/{len(data['feed'])}")

    if not dry_run and modified_count > 0:
        # Write back to file
        with yaml_path.open('w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✓ File updated: {yaml_path}")
    elif dry_run:
        print("(Dry run - no changes made)")


def main():
    """Run migration on all media YAML files."""
    media_dir = Path("media")
    yaml_files = sorted(media_dir.glob("media_*.yml"))

    print("="*80)
    print("FEEDBACK MIGRATION SCRIPT")
    print("="*80)
    print(f"\nFound {len(yaml_files)} YAML files to process")

    # First, do a dry run
    print("\n" + "="*80)
    print("DRY RUN - Preview of changes")
    print("="*80)

    for yaml_file in yaml_files:
        migrate_yaml_file(yaml_file, dry_run=True)

    # Ask for confirmation
    print("\n" + "="*80)
    response = input("\nDo you want to apply these changes? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        print("\n" + "="*80)
        print("APPLYING CHANGES")
        print("="*80)

        for yaml_file in yaml_files:
            migrate_yaml_file(yaml_file, dry_run=False)

        print("\n✓ Migration complete!")
    else:
        print("\nMigration cancelled.")


if __name__ == "__main__":
    main()
