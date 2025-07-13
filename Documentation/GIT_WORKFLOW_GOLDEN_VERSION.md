# India TS 3.0 - Git Workflow for Golden Version

## Overview

This document outlines the Git workflow for maintaining India TS 3.0 as a golden version. The local copy should remain untouched, with all development happening through Git.

## Initial Setup

### 1. Run the Setup Script

```bash
cd /Users/maverick/PycharmProjects/India-TS
./git_setup_golden_version.sh
```

This script will:
- Initialize Git repository
- Create comprehensive .gitignore
- Create config.ini.example (sanitized)
- Add all files and create initial commit
- Tag the version as v3.0 and golden-version

### 2. Add Remote Repository

```bash
# If using GitHub
git remote add origin https://github.com/yourusername/india-ts.git

# If using GitLab
git remote add origin https://gitlab.com/yourusername/india-ts.git

# If using private Git server
git remote add origin git@yourserver.com:india-ts.git
```

### 3. Push to Remote

```bash
# Push main branch
git push -u origin main

# Push tags
git push --tags
```

### 4. Protect the Main Branch

On your Git hosting service (GitHub/GitLab/Bitbucket):

1. Go to Settings → Branches
2. Add branch protection rule for 'main'
3. Enable:
   - Require pull request reviews
   - Dismiss stale pull request approvals
   - Require status checks to pass
   - Include administrators
   - Restrict who can push to matching branches

## Development Workflow

### IMPORTANT: Never Edit Local Files Directly!

After setting up the golden version, follow this workflow:

### 1. Clone Fresh Copy for Development

```bash
# Create a development directory
mkdir ~/Development/India-TS-Dev
cd ~/Development/India-TS-Dev

# Clone the repository
git clone https://github.com/yourusername/india-ts.git .

# Copy config.ini from golden version (if needed)
cp /Users/maverick/PycharmProjects/India-TS/config.ini .
```

### 2. Create Feature Branch

```bash
# Always branch from main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name

# Examples:
git checkout -b feature/add-options-scanner
git checkout -b bugfix/stop-loss-calculation
git checkout -b enhancement/dashboard-metrics
```

### 3. Make Changes

```bash
# Edit files in the development copy
# Test thoroughly
python test_system.py

# Commit changes
git add -A
git commit -m "Feature: Add options scanner with Greeks calculation"
```

### 4. Push and Create Pull Request

```bash
# Push feature branch
git push origin feature/your-feature-name

# Create pull request on Git hosting service
# Review changes carefully
# Merge after approval
```

### 5. Update Golden Version (Only After Merge)

```bash
# In the golden version directory
cd /Users/maverick/PycharmProjects/India-TS

# Fetch latest changes
git fetch origin

# Verify you're on main
git checkout main

# Pull changes (fast-forward only)
git pull --ff-only origin main

# Verify golden version lock
ls -la .GOLDEN_VERSION_LOCK
```

## Emergency Procedures

### If Local Files Were Accidentally Modified

```bash
# Check what was changed
git status
git diff

# Discard ALL local changes (CAREFUL!)
git reset --hard HEAD

# Or discard specific file changes
git checkout -- path/to/file
```

### Rollback to Previous Version

```bash
# List all tags
git tag -l

# Checkout specific version
git checkout v3.0

# Or revert to previous commit
git log --oneline -10
git checkout <commit-hash>
```

## Best Practices

### 1. Branch Naming Convention

- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Urgent production fixes
- `enhancement/` - Improvements to existing features
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

### 2. Commit Message Format

```
Type: Brief description (max 50 chars)

Longer description if needed. Explain:
- What changed
- Why it changed
- Any impacts

Fixes #123
```

Types: Feature, Bugfix, Hotfix, Enhancement, Refactor, Docs, Test

### 3. Testing Before Merge

Always test in development environment:

```bash
# Run system tests
python test_system.py

# Run specific component tests
python Daily/Market_Regime/test_market_regime.py

# Check for syntax errors
python -m py_compile Daily/**/*.py
```

### 4. Version Tagging

After major releases:

```bash
# Create new version tag
git tag -a v3.1 -m "Version 3.1 - Added options trading support"

# Push tag
git push origin v3.1
```

## Backup Strategy

### 1. Local Backup (Automated)

Create a cron job to backup the golden version:

```bash
# Add to crontab
0 2 * * * tar -czf ~/Backups/india-ts-golden-$(date +\%Y\%m\%d).tar.gz /Users/maverick/PycharmProjects/India-TS
```

### 2. Remote Backup

- Git repository serves as primary backup
- Consider additional cloud backup for database and state files

### 3. State File Backup

```bash
# Create state backup script
cat > backup_state.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/Backups/india-ts-state
mkdir -p $BACKUP_DIR

# Backup critical state files
cp Daily/trading_state.json $BACKUP_DIR/trading_state_$(date +%Y%m%d_%H%M%S).json
cp Market_Regime/data/regime_learning.db $BACKUP_DIR/regime_learning_$(date +%Y%m%d_%H%M%S).db

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete
EOF

chmod +x backup_state.sh
```

## Monitoring Golden Version

### 1. Create Read-Only Reminder

```bash
# Add to .bashrc or .zshrc
alias cdgold='cd /Users/maverick/PycharmProjects/India-TS && echo "⚠️  GOLDEN VERSION - DO NOT EDIT FILES! ⚠️"'
```

### 2. File System Protection (Optional)

```bash
# Make files read-only
find /Users/maverick/PycharmProjects/India-TS -name "*.py" -exec chmod 444 {} \;

# To restore write permissions when needed
find /Users/maverick/PycharmProjects/India-TS -name "*.py" -exec chmod 644 {} \;
```

### 3. Git Hooks

Create `.git/hooks/pre-commit` to prevent accidental commits:

```bash
#!/bin/bash
echo "⚠️  WARNING: This is the GOLDEN VERSION repository!"
echo "Are you sure you want to commit directly to the golden version?"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read
```

## Deployment Checklist

When deploying updates from Git to golden version:

- [ ] All tests pass in development environment
- [ ] Code reviewed and approved
- [ ] Backup current golden version
- [ ] Stop all running services
- [ ] Pull changes with --ff-only
- [ ] Verify config files are intact
- [ ] Restart services
- [ ] Monitor logs for errors
- [ ] Verify dashboard is functional

## Summary

1. **Golden Version = Production**: Never edit directly
2. **All Development in Git**: Use branches and pull requests
3. **Test Everything**: Before merging to main
4. **Backup Regularly**: State files and database
5. **Monitor and Audit**: Keep track of all changes

---

*Remember: The golden version is your production system. Treat it with care and always work through Git for any changes.*