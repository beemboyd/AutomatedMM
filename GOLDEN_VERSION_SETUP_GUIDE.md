# India TS 3.0 - Golden Version Setup Guide

## Overview

This guide will help you set up India TS 3.0 as a golden version in Git, ensuring that your local copy remains untouched and all development happens through Git.

## Step 1: Prepare the Golden Version

Run the preparation script:

```bash
cd /Users/maverick/PycharmProjects/India-TS
./prepare_golden_version.sh
```

This will:
- Create a comprehensive .gitignore
- Stash any uncommitted changes
- Create a new branch 'golden-version-3.0'
- Commit all files as the golden version
- Tag the version as v3.0-golden

## Step 2: Push to Remote Repository

### Option A: If you already have a remote repository

```bash
# Push the new branch
git push -u origin golden-version-3.0

# Push tags
git push --tags
```

### Option B: If you need to create a new repository

1. Create a new repository on GitHub/GitLab (WITHOUT README or .gitignore)
2. Add the remote:

```bash
# For GitHub
git remote add origin https://github.com/yourusername/india-ts-3.0.git

# For GitLab
git remote add origin https://gitlab.com/yourusername/india-ts-3.0.git
```

3. Push everything:

```bash
git push -u origin golden-version-3.0
git push --tags
```

## Step 3: Configure Repository Settings

### On GitHub:

1. Go to your repository → Settings → Branches
2. Change default branch to 'golden-version-3.0' (or merge to main first)
3. Add branch protection rule:
   - Branch name pattern: `main` or `golden-version-3.0`
   - Enable:
     - ✓ Require pull request reviews before merging
     - ✓ Dismiss stale pull request approvals
     - ✓ Require review from CODEOWNERS
     - ✓ Require status checks to pass
     - ✓ Require branches to be up to date
     - ✓ Include administrators
     - ✓ Restrict who can push to matching branches

### On GitLab:

1. Go to Project → Settings → Repository → Protected branches
2. Select branch: 'main' or 'golden-version-3.0'
3. Set:
   - Allowed to merge: Maintainers
   - Allowed to push: No one
   - Require approval from: 1 or more

## Step 4: Set Up Development Workflow

### Create Development Environment

```bash
# Create a separate development directory
mkdir ~/Development
cd ~/Development

# Clone the repository
git clone https://github.com/yourusername/india-ts-3.0.git india-ts-dev

# Enter the development directory
cd india-ts-dev

# Copy sensitive files from golden version
cp /Users/maverick/PycharmProjects/India-TS/Daily/config.ini Daily/
cp /Users/maverick/PycharmProjects/India-TS/data/trading_state.json data/ 2>/dev/null || true
```

### Create First Development Branch

```bash
# Make sure you're on the main branch
git checkout main

# Create a development branch
git checkout -b development

# Push the development branch
git push -u origin development
```

## Step 5: Protect the Golden Version

### Add Visual Reminders

1. Create an alias in your shell configuration:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias india-gold='cd /Users/maverick/PycharmProjects/India-TS && echo "⚠️  WARNING: GOLDEN VERSION - DO NOT EDIT! ⚠️"'
alias india-dev='cd ~/Development/india-ts-dev'
```

2. Create a pre-commit hook in the golden version:

```bash
# In the golden version directory
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "⚠️  ERROR: This is the GOLDEN VERSION repository!"
echo "You should not commit directly here."
echo "Please use the development repository instead."
echo ""
echo "To override (NOT RECOMMENDED), use: git commit --no-verify"
exit 1
EOF

chmod +x .git/hooks/pre-commit
```

### Optional: Make Files Read-Only

```bash
# Make Python files read-only
find /Users/maverick/PycharmProjects/India-TS -name "*.py" -exec chmod 444 {} \;

# Make shell scripts still executable but not writable
find /Users/maverick/PycharmProjects/India-TS -name "*.sh" -exec chmod 555 {} \;
```

## Step 6: Update Golden Version (When Needed)

Only update the golden version after changes have been tested and merged:

```bash
# In golden version directory
cd /Users/maverick/PycharmProjects/India-TS

# Fetch latest changes
git fetch origin

# Switch to main branch
git checkout main

# Pull changes (fast-forward only to prevent local changes)
git pull --ff-only origin main

# Verify the lock file is still there
ls -la .GOLDEN_VERSION_LOCK
```

## Daily Workflow

### For Development:

```bash
# Always work in development directory
cd ~/Development/india-ts-dev

# Create feature branch
git checkout -b feature/new-scanner

# Make changes, test, commit
git add .
git commit -m "Feature: Add new scanner"

# Push and create pull request
git push origin feature/new-scanner
```

### For Running Production:

```bash
# Use the golden version (read-only)
cd /Users/maverick/PycharmProjects/India-TS

# Run the system
python3 Daily/scanners/Long_Reversal_Daily.py

# Check logs, monitor, but DO NOT EDIT
```

## Important Files to Backup

Before setting up the golden version, backup these files:

```bash
# Create backup directory
mkdir -p ~/Backups/india-ts-golden-backup

# Backup critical files
cp Daily/config.ini ~/Backups/india-ts-golden-backup/
cp data/trading_state.json ~/Backups/india-ts-golden-backup/ 2>/dev/null || true
cp Market_Regime/data/regime_learning.db ~/Backups/india-ts-golden-backup/ 2>/dev/null || true

# Create a full backup
tar -czf ~/Backups/india-ts-golden-backup/full-backup-$(date +%Y%m%d).tar.gz .
```

## Troubleshooting

### If you accidentally edit golden version files:

```bash
# Check what changed
git status
git diff

# Discard all changes
git reset --hard HEAD

# Or discard specific file
git checkout -- path/to/file
```

### If you need to make emergency changes:

1. Create a hotfix branch in development repo
2. Test thoroughly
3. Create pull request
4. After merge, update golden version

### If golden version gets out of sync:

```bash
# Force sync with remote (CAREFUL - will lose local changes)
git fetch origin
git reset --hard origin/main
```

## Summary Checklist

- [ ] Run prepare_golden_version.sh
- [ ] Push to remote repository
- [ ] Configure branch protection
- [ ] Create development environment
- [ ] Add visual reminders
- [ ] Set up pre-commit hooks
- [ ] Create backups
- [ ] Document repository URLs

## Repository Information

Fill in after setup:

- **Repository URL**: _________________________
- **Default Branch**: _________________________
- **Golden Version Tag**: v3.0-golden
- **Development Directory**: ~/Development/india-ts-dev
- **Golden Directory**: /Users/maverick/PycharmProjects/India-TS

---

*Remember: The golden version is your production system. Never edit it directly. All changes go through Git.*

*Created: June 25, 2025*