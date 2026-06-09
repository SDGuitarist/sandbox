"""
Patch docs/plans/film-production-pm-plan.md:
Replace the compact ## Swarm Agent Assignment table with the canonical block format.

Run once: python3 docs/reports/070/patch_swarm_assignment.py
from /Users/alejandroguillen/Projects/sandbox/
"""
import re

PLAN = '/Users/alejandroguillen/Projects/sandbox/docs/plans/film-production-pm-plan.md'
SECTION = '/Users/alejandroguillen/Projects/sandbox/docs/reports/070/swarm-assignment-section.md'

with open(PLAN, 'r') as f:
    content = f.read()

with open(SECTION, 'r') as f:
    new_section = f.read().rstrip('\n')

# The existing section starts at '## Swarm Agent Assignment\n' and ends just before '\n---\n\n## Acceptance Tests'
pattern = r'## Swarm Agent Assignment\n.*?(?=\n---\n\n## Acceptance Tests)'
if not re.search(pattern, content, flags=re.DOTALL):
    print("ERROR: pattern not found in plan file")
    raise SystemExit(1)

new_content = re.sub(pattern, new_section, content, flags=re.DOTALL)

assert new_content.count('## Swarm Agent Assignment') == 1, "Duplicate section after patch"

with open(PLAN, 'w') as f:
    f.write(new_content)

print("DONE: ## Swarm Agent Assignment section replaced in", PLAN)
print("Section count:", new_content.count('## Swarm Agent Assignment'))
