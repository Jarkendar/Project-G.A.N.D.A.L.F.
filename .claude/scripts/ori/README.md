# O.R.I. — commit and push brain/, as MCP tools

The one place that may write to brain/'s git history, for the `ori`
sub-agent (`.claude/agents/ori.md`). Agents that write files to brain/ hold
no shell; when the owner asks to commit, the router hands the paths to Ori.

## Tools

| Tool | What it does |
|---|---|
| `status()` | `git status --short --branch` of brain/ — file names only |
| `commit(paths, message)` | `git add -- <paths>`, one commit, `git push origin main` |

## What `commit` refuses

- brain/ on any branch but `main`;
- a path outside brain/ (absolute, `..`), the repository root, `.git/`, a
  symlink, a path that does not exist, anything starting with `-`;
- changes already staged by someone else;
- a set of paths that includes a deletion — brain/ is append-only;
- a message that does not start with a Conventional Commits subject, or that
  brings its own trailers.

It adds `Co-Authored-By: Claude <noreply@anthropic.com>` itself, never
amends, rebases or forces, and does not bypass brain/'s pre-commit hook: if
the hook rejects the commit, the staging is undone and the hook's text comes
back. A failed push leaves the commit local and says so.

`BRAIN_PATH` comes from `.claude/gandalf.env` on every call.

## Running

Started by Claude Code from `.mcp.json` over stdio. It uses the Gimli
server's venv (`.claude/scripts/gimli/.venv`) — the MCP SDK is the only
dependency of both.

Tested on a throwaway repository with a bare remote (2026-10-11): twenty
cases — the refusals above, a good commit reaching the remote with the
trailer, files not handed over left untouched, a failed push reported.
