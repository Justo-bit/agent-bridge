# Syncing with Upstream Repositories

This document explains how to fetch improvements from the original Agent-S and Coasty repositories.

## Upstream Remotes

```bash
# Agent-S improvements
git remote add upstream-agent-s https://github.com/Justo-bit/Agent-S.git

# Coasty/open-computer-use improvements
git remote add upstream-coasty https://github.com/Justo-bit/open-computer-use.git
```

## Fetch Latest Changes

### From Agent-S
```bash
git fetch upstream-agent-s
git log upstream-agent-s/main --oneline -10
```

### From Coasty
```bash
git fetch upstream-coasty
git log upstream-coasty/main --oneline -10
```

## Integration Workflow

### Option 1: Cherry-pick specific commits
```bash
# View commits from Agent-S
git log upstream-agent-s/main --oneline

# Cherry-pick a specific improvement
git cherry-pick <commit-hash>
```

### Option 2: Merge specific branches
```bash
# Fetch latest
git fetch upstream-agent-s

# Create feature branch from upstream
git checkout -b sync/agent-s-improvements upstream-agent-s/main

# Review changes
git diff main..HEAD

# If good, merge to main
git checkout main
git merge sync/agent-s-improvements
git push origin main
```

### Option 3: Sync entire directory
```bash
# If Agent-S has improvements to specific modules
git checkout upstream-agent-s/main -- bridge/llm_router.py
git commit -m "chore: sync llm_router.py from Agent-S upstream"
git push origin main
```

## Automated Sync Script

Save as `sync-upstream.sh`:

```bash
#!/bin/bash

echo "🔄 Syncing with upstream repositories..."

# Fetch Agent-S improvements
echo "📦 Fetching Agent-S..."
git fetch upstream-agent-s
echo "✅ Agent-S fetched"

# Fetch Coasty improvements
echo "📦 Fetching Coasty..."
git fetch upstream-coasty
echo "✅ Coasty fetched"

# Show what's new
echo ""
echo "📊 Agent-S updates:"
git log main..upstream-agent-s/main --oneline | head -5

echo ""
echo "📊 Coasty updates:"
git log main..upstream-coasty/main --oneline | head -5

echo ""
echo "💡 To integrate specific commits, use:"
echo "   git cherry-pick <commit-hash>"
echo ""
echo "💡 To view full diff:"
echo "   git diff main..upstream-agent-s/main"
```

Make it executable:
```bash
chmod +x sync-upstream.sh
./sync-upstream.sh
```

## Recommended Sync Frequency

- **Weekly**: Check for critical bug fixes
- **Monthly**: Integrate feature improvements
- **As needed**: Pull urgent security patches

## Version Strategy

After syncing, update version:
```bash
# Current: v1.0.0
# After sync: v1.0.1 (patch) or v1.1.0 (minor)

# Update version in code
# Create release with changelog
git tag -a v1.0.1 -m "sync: merge improvements from Agent-S and Coasty"
git push origin main --tags
```

## Handling Conflicts

If merge conflicts occur:
```bash
# See conflicts
git status

# Edit conflicted files
# Then resolve:
git add <resolved-files>
git commit -m "chore: resolve merge conflicts from upstream sync"
```

## Push Synced Changes

```bash
# After resolving any conflicts
git push origin main

# Or if you want to create a PR for review first
git checkout -b chore/upstream-sync
git push origin chore/upstream-sync
# Then create PR on GitHub
```

## What to Sync

### From Agent-S (backend improvements)
- ✅ llm_router.py - LLM provider routing improvements
- ✅ agents3_adapter.py - Agent-S integration updates
- ✅ Feature implementations from unwired_features.py
- ✅ Cost tracking improvements

### From Coasty (frontend/integration)
- ✅ coasty_integration.py - Coasty bridge improvements
- ✅ API endpoint compatibility updates
- ✅ Authentication/security improvements
- ✅ Performance optimizations

## Status Check

```bash
# See all remotes
git remote -v

# Check for unpulled changes
git fetch --all
for remote in origin upstream-agent-s upstream-coasty; do
  echo "=== $remote ==="
  git log main..$remote/main --oneline | head -3
done
```

---

**Last updated**: 2026-06-08  
**Status**: Ready for upstream syncing
