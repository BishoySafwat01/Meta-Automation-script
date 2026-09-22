# Codex Automation Protocol

## Mandatory Post-Task Workflow:
1. Automatic Stage & Commit:
   - Immediately upon completing and validating any code task, bugfix, or refactor, stage all tracked files:
     `git add .`
   - Create an imperative Conventional Commit message (e.g., `fix(messaging): ...` or `feat(gui): ...`).

2. Silent Auto-Push:
   - Immediately push changes to GitHub via SSH:
     `git push origin HEAD`

3. Version Release Workflow:
   - Whenever a task increments or bumps the release version:
     1. Sync version markers across relevant files.
     2. Commit the changes.
     3. Generate an annotated tag: `git tag -a vX.X.X -m "Release vX.X.X"`
     4. Push both branch and tags: `git push origin HEAD --tags`
