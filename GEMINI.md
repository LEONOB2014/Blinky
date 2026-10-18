# GEMINI.md

@AGENTS.md

## Gemini CLI specifics

- You own WS5 (`api/`, `web/`). Build against `mocks/` first; switch to the real lake only when
  the producing workstream's PR has merged into `develop`.
- Never run `git push` without the maintainer approving that specific push. Never commit in the
  main checkout or on `main`/`develop`; work in a worktree under `../radar-worktrees/`.
