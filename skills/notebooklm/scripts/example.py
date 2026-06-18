#!/usr/bin/env python3
"""
NotebookLM Helper Script

This script provides utilities for working with Google NotebookLM,
including document preparation and workflow automation.

Features:
- Document preprocessing for NotebookLM upload
- Markdown to text conversion
- Study guide generation templates
- Flashcard creation utilities

Example usage:
    python notebooklm_helper.py --help
    python notebooklm_helper.py summarize "research_paper.pdf"
    python notebooklm_helper.py generate-flashcards notes.md
"""

import argparse
import sys
from pathlib import Path


def summarize_document(file_path):
    """Generate a summary of a document for NotebookLM."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found - {file_path}")
        return
    
    print(f"Preparing summary for: {path.name}")
    print("=" * 50)
    
    if path.suffix.lower() == '.md':
        content = path.read_text()
        lines = content.split('\n')
        headings = [line for line in lines if line.startswith('#')]
        
        print("Detected headings:")
        for heading in headings[:10]:
            print(f"  - {heading.strip()}")
        
        if len(lines) > 50:
            print(f"\nDocument is {len(lines)} lines long")
            print("Consider breaking it into smaller sections for NotebookLM")


def generate_flashcard_template():
    """Generate a flashcard template for study notes."""
    template = """# Flashcard Template for NotebookLM

## Key Concepts
- [Concept 1]: [Brief definition]
- [Concept 2]: [Brief definition]
- [Concept 3]: [Brief definition]

## Important Questions
1. [Question 1]
   - Answer: [Your answer here]

2. [Question 2]
   - Answer: [Your answer here]

## Key Takeaways
- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3]
"""
    print(template)


def generate_study_guide():
    """Generate a study guide template."""
    template = """# Study Guide Template

## Topic Overview
[Brief summary of the topic]

## Learning Objectives
1. [Objective 1]
2. [Objective 2]
3. [Objective 3]

## Key Terms & Definitions
| Term | Definition |
|------|------------|
| [Term 1] | [Definition] |
| [Term 2] | [Definition] |

## Review Questions
1. [Question 1]
2. [Question 2]
3. [Question 3]

## Additional Resources
- [Resource 1]
- [Resource 2]
"""
    print(template)


def main():
    parser = argparse.ArgumentParser(
        description="NotebookLM Helper - Utilities for working with Google NotebookLM"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    subparsers.add_parser('flashcards', help='Generate flashcard template')
    subparsers.add_parser('study-guide', help='Generate study guide template')
    
    summary_parser = subparsers.add_parser('summarize', help='Summarize a document')
    summary_parser.add_argument('file', help='Path to document file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'flashcards':
        generate_flashcard_template()
    elif args.command == 'study-guide':
        generate_study_guide()
    elif args.command == 'summarize':
        summarize_document(args.file)


if __name__ == "__main__":
    main()