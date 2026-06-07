#!/bin/bash

# Sync Upstream Improvements Script
# Fetches latest changes from Agent-S and Coasty repositories

set -e

echo "🔄 Syncing with upstream repositories..."
echo ""

# Fetch Agent-S improvements
echo "📦 Fetching Agent-S improvements..."
git fetch upstream-agent-s 2>/dev/null || echo "⚠️  upstream-agent-s not configured"

# Fetch Coasty improvements
echo "📦 Fetching Coasty improvements..."
git fetch upstream-coasty 2>/dev/null || echo "⚠️  upstream-coasty not configured"

echo ""
echo "✅ Fetch complete"
echo ""

# Show Agent-S updates
echo "📊 Agent-S Updates (commits ahead of main):"
if git rev-parse upstream-agent-s/main >/dev/null 2>&1; then
  git log main..upstream-agent-s/main --oneline | head -5 || echo "  No new commits"
else
  echo "  upstream-agent-s/main not available"
fi

echo ""

# Show Coasty updates
echo "📊 Coasty Updates (commits ahead of main):"
if git rev-parse upstream-coasty/main >/dev/null 2>&1; then
  git log main..upstream-coasty/main --oneline | head -5 || echo "  No new commits"
else
  echo "  upstream-coasty/main not available"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "💡 Integration Options:"
echo ""
echo "1. Cherry-pick specific commit:"
echo "   git cherry-pick <commit-hash>"
echo ""
echo "2. Create sync branch:"
echo "   git checkout -b chore/sync-upstream upstream-agent-s/main"
echo ""
echo "3. View full diff:"
echo "   git diff main..upstream-agent-s/main | head -100"
echo ""
echo "4. Sync specific file:"
echo "   git checkout upstream-agent-s/main -- <filepath>"
echo "═══════════════════════════════════════════"
