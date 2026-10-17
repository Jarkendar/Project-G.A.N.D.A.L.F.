#!/usr/bin/env python3
# Bash guard for agents that work on this repo. A `PreToolUse` hook on `Bash`,
# declared in an agent's own frontmatter; the only argument is that agent's
# name (a call made by another agent is passed through — see guard.py for why):
#
#   bash_guard.py aule
#
# The command is split into its simple commands (on `&&`, `||`, `;`, `|` and
# line breaks, quotes respected) and every one of them must be on the list
# below. Anything else is refused (exit 2, reason on stderr):
#
#   git      status, diff, log, show, branch, switch, add, commit, push,
#            fetch, pull --ff-only, rev-parse, ls-files, mv, rm — never merge,
#            rebase, reset, clean, checkout or restore; no -f / --force of any
#            kind; push only as `git push [-u] <remote> <branch>` with a branch
#            that is not main / master / HEAD
#   gh       pr create, view, list, status, diff, checks — never merge
#   python3  a script inside this repo, or -m pytest / unittest / py_compile
#   rg, ls, cat, head, tail, wc, diff, pwd, echo, chmod, cd
#
# Refused everywhere: any path that resolves outside this repo (`../brain`,
# `/tmp`, `~`), `$` and backticks (expansion and command substitution), `VAR=`
# prefixes, subshells, background `&`, input redirection, heredocs, and output
# redirection other than `2>&1` and `> /dev/null`.
#
# What this does not cover: a script the agent wrote inside the repo can do
# anything once run. That gap is closed by the agent's prompt and by the diff
# in the pull request, not by this hook.
#
# Fails closed: input it cannot read is a refusal.

import json
import os
import shlex
import sys

SEPARATORS = {"&&", "||", ";", "|", "\n"}
REDIRECTS = {">", ">>", ">&"}

GIT_SUBCOMMANDS = {
    "status", "diff", "log", "show", "branch", "switch", "add", "commit",
    "push", "fetch", "pull", "rev-parse", "ls-files", "mv", "rm",
}
GH_PR_SUBCOMMANDS = {"create", "view", "list", "status", "diff", "checks"}
PROTECTED_BRANCHES = {"main", "master", "HEAD"}
PYTHON_MODULES = {"pytest", "unittest", "py_compile"}
PLAIN_COMMANDS = {"rg", "ls", "cat", "head", "tail", "wc", "diff", "pwd", "echo", "chmod"}
# Values that are prose, not paths: a commit message, a PR's title and body.
MESSAGE_FLAGS = {"-m", "--message", "-t", "--title", "-b", "--body"}


def refuse(reason):
    print(f"bash-guard: {reason}", file=sys.stderr)
    sys.exit(2)


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def check_expansions(command):
    # `$` and backticks are live outside single quotes; a backslash escapes
    # the next character outside single quotes.
    quote, escaped = None, False
    for ch in command:
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote == "'":
            if ch == "'":
                quote = None
        elif ch in "$`":
            refuse(f"'{ch}' (expansion or command substitution) is not allowed")
        elif ch == '"':
            quote = None if quote == '"' else '"'
        elif ch == "'" and quote is None:
            quote = "'"


def tokenize(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError as exc:
        refuse(f"could not parse the command ({exc})")


def segments(tokens):
    current, out = [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in SEPARATORS:
            out.append(current)
            current = []
        elif tok in REDIRECTS:
            if current and current[-1] in ("1", "2"):
                current.pop()
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if tok == ">&" and target in ("1", "2"):
                i += 1
            elif tok in (">", ">>") and target == "/dev/null":
                i += 1
            else:
                refuse(f"output redirection '{tok} {target}' is not allowed — write files with Write / Edit")
        elif tok and set(tok) <= set(";&|<>()\n"):
            refuse(f"'{tok.strip()}' (subshell, background job, input redirection or heredoc) is not allowed")
        else:
            current.append(tok)
        i += 1
    out.append(current)
    return [seg for seg in out if seg]


def looks_like_path(tok):
    return tok.startswith(("/", "~", ".")) or "/" in tok


def check_paths(args, cwd, repo):
    skip = False
    for tok in args:
        if skip:
            skip = False
            continue
        if tok in MESSAGE_FLAGS:
            skip = True
            continue
        if tok.startswith("-"):
            flag, _, value = tok.partition("=")
            if not value or flag in MESSAGE_FLAGS:
                continue
            tok = value
        if not looks_like_path(tok):
            continue
        raw = os.path.expanduser(tok)
        path = os.path.realpath(raw if os.path.isabs(raw) else os.path.join(cwd, raw))
        if not inside(path, repo):
            refuse(f"'{tok}' resolves to {path}, outside this repo")


def check_git(args):
    if args and args[0] == "-C":
        args = args[2:]
    if args and args[0].startswith("-"):
        refuse(f"git option '{args[0]}' before the subcommand is not allowed")
    if not args:
        refuse("bare 'git' is not allowed")
    sub, rest = args[0], args[1:]
    if sub not in GIT_SUBCOMMANDS:
        refuse(f"'git {sub}' is not allowed (merging, rebasing, resetting and discarding changes are the owner's)")
    for tok in rest:
        if tok in ("-f", "--force", "--no-verify") or tok.startswith(("--force", "--mirror", "--delete")):
            refuse(f"'git {sub} {tok}' is not allowed")
    if sub == "branch" and any(t in ("-D", "-M", "-C", "-d", "--delete") for t in rest):
        refuse("deleting or renaming a branch is not allowed")
    if sub == "switch" and "--discard-changes" in rest:
        refuse("'git switch --discard-changes' is not allowed")
    if sub == "pull" and "--ff-only" not in rest:
        refuse("'git pull' only with --ff-only (a pull that merges is a merge)")
    if sub == "push":
        check_push(rest)


def check_push(rest):
    positional = []
    for tok in rest:
        if tok in ("-u", "--set-upstream"):
            continue
        if tok.startswith("-"):
            refuse(f"'git push {tok}' is not allowed")
        positional.append(tok)
    if len(positional) != 2:
        refuse("push as 'git push [-u] <remote> <branch>' — name the remote and the branch")
    refspec = positional[1]
    if refspec.startswith("+"):
        refuse(f"'{refspec}' is a forced push")
    for side in refspec.split(":"):
        name = side.removeprefix("refs/heads/")
        if name in PROTECTED_BRANCHES or not name:
            refuse(f"pushing to '{refspec}' is not allowed — never to main, master or HEAD")


def check_python(args):
    if not args:
        refuse("an interactive python is not allowed")
    if args[0] == "-m":
        if len(args) < 2 or args[1] not in PYTHON_MODULES:
            refuse(f"'python -m {args[1] if len(args) > 1 else ''}' is not allowed (only {', '.join(sorted(PYTHON_MODULES))})")
        return
    if args[0].startswith("-") or not args[0].endswith(".py"):
        refuse(f"python with '{args[0]}' is not allowed — run a .py script inside this repo")


def check_segment(seg, cwd, repo):
    cmd, args = seg[0], seg[1:]
    if "=" in cmd and not cmd.startswith("-"):
        refuse(f"'{cmd}' — variable assignments are not allowed")
    check_paths(args, cwd, repo)
    if cmd == "cd":
        if len(args) != 1:
            refuse("'cd' takes exactly one folder inside this repo")
        return os.path.realpath(os.path.join(cwd, os.path.expanduser(args[0])))
    if cmd == "git":
        check_git(args)
    elif cmd == "gh":
        if len(args) < 2 or args[0] != "pr" or args[1] not in GH_PR_SUBCOMMANDS:
            refuse(f"'gh {' '.join(args[:2])}' is not allowed (only gh pr {', '.join(sorted(GH_PR_SUBCOMMANDS))})")
    elif cmd in ("python3", "python"):
        check_python(args)
    elif cmd == "rg":
        if any(t.startswith("--pre") for t in args):
            refuse("'rg --pre' runs a program — not allowed")
    elif cmd not in PLAIN_COMMANDS:
        refuse(f"'{cmd}' is not on this agent's list")
    return cwd


def main():
    try:
        event = json.load(sys.stdin)
        command = event["tool_input"]["command"]
        if not isinstance(command, str):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        refuse("could not read the tool input — command refused")
    if len(sys.argv) < 2:
        refuse("no agent name configured — command refused")
    owner = sys.argv[1]
    caller = event.get("agent_type")
    if caller and caller != owner:
        sys.exit(0)
    repo = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
    cwd = os.path.realpath(event.get("cwd") or os.getcwd())
    if not inside(cwd, repo):
        refuse(f"the working directory {cwd} is outside this repo — command refused")
    check_expansions(command)
    for seg in segments(tokenize(command)):
        cwd = check_segment(seg, cwd, repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
