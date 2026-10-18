# Versioning and releases

## Policy

- [Semantic Versioning 2.0.0](https://semver.org/), **0.x until the submission**.
- Every release from `develop` bumps MINOR (`0.1.0` → `0.2.0`); a hotfix on `main` bumps PATCH.
  Breaking changes also bump MINOR while in 0.x (`major_version_zero = true`).
- Releases follow the sync points: the 09:00 demo freeze and the 12:00 submission are releases.
- The version lives in `pyproject.toml` (`[tool.commitizen]`), tags are `vX.Y.Z`, and
  [`CHANGELOG.md`](../../CHANGELOG.md) follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
  generated from the Conventional Commits history by commitizen.

| Version | Content |
|---|---|
| `v0.1.0` | Repository scaffold and engineering practices |

## Cut a release

```bash
git fetch origin
git worktree add -b release/v0.2.0 ../radar-worktrees/release-v0.2.0 origin/develop
cd ../radar-worktrees/release-v0.2.0
uv run cz bump --increment MINOR --yes --files-only    # version in pyproject.toml
uv run cz changelog --incremental --unreleased-version v0.2.0
git add pyproject.toml CHANGELOG.md
git commit -m "bump: version 0.1.0 → 0.2.0"
```

Both `cz` commands can exit 16 ("No tag found…") even after updating the files: check the files,
not the exit code, and never run them under a bare `set -e`.

1. Review `CHANGELOG.md`; add a short *Highlights* section with measured numbers only.
2. Push (approved), open the PR `release/v0.2.0` → `main`, wait for CI, merge with a **merge commit**.
3. Tag the merge commit on `main` and publish (each push approved):

```bash
cd ../../radar && git pull --ff-only
git tag -a v0.2.0 -m "v0.2.0: <one-line summary>"
git push origin v0.2.0
gh release create v0.2.0 --title "v0.2.0" --notes-file <changelog section>
```

4. Bring the release commit back: open a PR `main` → `develop` (merge commit).

## Hotfix

```bash
git worktree add -b hotfix/<desc> ../radar-worktrees/hotfix-<desc> origin/main
# fix, test, commit; then:
uv run cz bump --increment PATCH --yes --files-only
uv run cz changelog --incremental --unreleased-version vX.Y.Z
```

PR into `main` (merge commit), tag, release, then PR `main` → `develop`.
