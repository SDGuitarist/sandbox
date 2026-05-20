"""Clean up worktrees and branches from run 050."""
import subprocess
import os

REPO = "/Users/alejandroguillen/Projects/sandbox"

# Get list of worktrees
result = subprocess.run(["git", "-C", REPO, "worktree", "list", "--porcelain"],
                       capture_output=True, text=True)

worktree_paths = []
for line in result.stdout.strip().split("\n"):
    if line.startswith("worktree ") and "agent-" in line:
        path = line.replace("worktree ", "")
        worktree_paths.append(path)

print(f"Found {len(worktree_paths)} agent worktrees to remove")

# Remove each worktree
removed = 0
for path in worktree_paths:
    if os.path.exists(path):
        r = subprocess.run(["git", "-C", REPO, "worktree", "remove", path, "--force"],
                          capture_output=True, text=True)
        if r.returncode == 0:
            removed += 1
        else:
            print(f"  WARN: could not remove {path}: {r.stderr.strip()}")

print(f"Removed {removed} worktrees")

# Delete assembly branch
r = subprocess.run(["git", "-C", REPO, "branch", "-D", "swarm-050-assembly"],
                  capture_output=True, text=True)
if r.returncode == 0:
    print("Deleted swarm-050-assembly branch")

# Delete agent branches from this run
result = subprocess.run(["git", "-C", REPO, "branch", "--list", "worktree-agent-*"],
                       capture_output=True, text=True)
branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
print(f"Found {len(branches)} agent branches to delete")

deleted = 0
for branch in branches:
    r = subprocess.run(["git", "-C", REPO, "branch", "-D", branch],
                      capture_output=True, text=True)
    if r.returncode == 0:
        deleted += 1

print(f"Deleted {deleted} agent branches")
print("Cleanup complete")
