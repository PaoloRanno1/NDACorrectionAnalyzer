# Test NDA Database

This folder contains the NDAs used for consistent testing. Each NDA should have two versions:

## File Naming Convention:
- **Clean version**: `[project_name]_clean.md`
- **Corrected version**: `[project_name]_corrected.md`

## How to Add New Test NDAs:
1. Save the original NDA as `[project_name]_clean.md`
2. Save the HR-edited version as `[project_name]_corrected.md`
3. The app will automatically detect and list them in the testing interface

## Current Test NDAs:
- Project Octagon (project_octagon_clean.md / project_octagon_corrected.md)

## File Format:
- All files should be in Markdown (.md) format
- Use `++text++` markers for HR additions
- Use `--text--` markers for HR deletions