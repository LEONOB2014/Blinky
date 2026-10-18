# Versioning and releases

## Policy

- [Semantic Versioning 2.0.0](https://semver.org/), **0.x until the submission**.
- Every release bumps MINOR (`0.1.0` → `0.2.0`); a fix released on its own bumps PATCH. Breaking
  changes also bump MINOR while in 0.x (`major_version_zero = true`).
- There are no `release/*` or `hotfix/*` branches. The only way into `main` is the `develop` →
  `main` PR, and that PR is the release. A fix for `main` lands on `develop` first.
- Releases follow the sync points: the 10:00 demo freeze and the 12:00 submission are releases.
- The version lives in `pyproject.toml` (`[tool.commitizen]`), tags are `vX.Y.Z`, and
  [`CHANGELOG.md`](../../CHANGELOG.md) follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
  generated from the Conventional Commits history by commitizen.

| Version | Content |
|---|---|
| `v0.1.0` | Repository scaffold and engineering practices |

## Cut a release

1. Bump the version on a short branch into `develop` (never commit on `develop` itself):

```bash
make worktree BRANCH=chore/release-v0.2.0
cd ../radar-worktrees/chore-release-v0.2.0
uv run cz bump --increment MINOR --yes --files-only    # version in pyproject.toml
uv run cz changelog --incremental --unreleased-version v0.2.0
git add pyproject.toml CHANGELOG.md
git commit -m "bump: version 0.1.0 → 0.2.0"
```

Both `cz` commands can exit 16 ("No tag found…") even after updating the files: check the files,
not the exit code, and never run them under a bare `set -e`.

2. Review `CHANGELOG.md`; add a short *Highlights* section with measured numbers only.
3. Push (approved) and merge the bump PR into `develop`. It touches only `pyproject.toml` and
   `CHANGELOG.md`, so it costs one CI run.
4. Open the release PR `develop` → `main` (`gh pr create --base main --head develop`), wait for CI
   (it also checks that the head is `develop`), merge with a **merge commit**.
5. Tag the merge commit on `main` and publish (each push approved):

```bash
cd ../../radar && git pull --ff-only
git tag -a v0.2.0 -m "v0.2.0: <one-line summary>"
git push origin v0.2.0
gh release create v0.2.0 --title "v0.2.0" --notes-file <changelog section>
```

No back-merge is needed: `main` only ever receives `develop`.
