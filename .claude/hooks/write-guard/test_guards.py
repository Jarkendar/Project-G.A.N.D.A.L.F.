#!/usr/bin/env python3
# Allowed and refused cases for guard.py and bash_guard.py, run as the hooks
# are run: a subprocess with the event on stdin, judged by its exit code.
#
#   python3 .claude/hooks/write-guard/test_guards.py

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
BRAIN = os.path.realpath(os.path.join(REPO, "..", "brain"))
ENV = dict(os.environ, CLAUDE_PROJECT_DIR=REPO)


def run(script, args, event):
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, script), *args],
        input=json.dumps(event), capture_output=True, text=True, env=ENV,
    )
    return proc.returncode, proc.stderr


class BashGuard(unittest.TestCase):
    def check(self, command, allowed, agent="aule", cwd=REPO):
        code, err = run("bash_guard.py", ["aule"], {
            "agent_type": agent, "cwd": cwd,
            "tool_name": "Bash", "tool_input": {"command": command},
        })
        self.assertEqual(code, 0 if allowed else 2, f"{command!r}: {err}")

    def test_allowed(self):
        for command in [
            "git status",
            "git diff main...HEAD --stat",
            "git log --oneline -5 origin/main",
            "git switch -c feat/aule",
            "git switch main",
            "git add .claude/agents/aule.md IMPLEMENTATION.md",
            'git commit -m "feat(agents): add aule; the smith" -m "Co-Authored-By: Claude <noreply@anthropic.com>"',
            'git commit -m "docs: never reads ../brain"',
            "git push -u origin feat/aule",
            "git pull --ff-only",
            "git fetch origin",
            'gh pr create --base main --title "feat: x" --body "Touches /tmp in prose only"',
            "gh pr view 73",
            "rg -n Aule .claude/agents",
            "ls -la .claude/hooks",
            "git log --oneline 2>&1 | head -20",
            "ls > /dev/null 2>/dev/null",
            "python3 .claude/hooks/write-guard/test_guards.py -v",
            "python3 -m py_compile .claude/hooks/write-guard/guard.py",
            "python3 .claude/scripts/gimli/mcp_server.py --help",
            "cd .claude && ls",
            "chmod +x .claude/hooks/write-guard/bash_guard.py",
            "git status && git diff\ngit log -1",
        ]:
            self.check(command, True)

    def test_refused(self):
        for command in [
            "git merge feat/aule",
            "git rebase main",
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git checkout -- .",
            "git restore README.md",
            "git push origin main",
            "git push origin HEAD:main",
            "git push origin feat/x:main",
            "git push",
            "git push --force origin feat/aule",
            "git push --force-with-lease origin feat/aule",
            "git push -f origin feat/aule",
            "git push origin +feat/aule",
            "git add -f .claude/gandalf.env",
            "git branch -D feat/old",
            "git pull",
            "git -c core.hooksPath=/tmp commit -m x",
            "git -C ../brain status",
            "gh pr merge 73",
            "gh api repos/x/y",
            "rm -rf .claude",
            "rm file.txt",
            "curl https://example.com",
            "wget https://example.com",
            "pip install requests",
            "npm install",
            "sudo ls",
            "cat ../brain/core/profile.md",
            "ls /home/rpi-jarkendar/github/second_brain/brain",
            "rg secret ~/",
            "cd .. && ls",
            "cd ../brain",
            "ls /tmp",
            "echo $HOME",
            "echo `whoami`",
            "ls $(pwd)/..",
            "FOO=1 git status",
            "(cd .. && ls)",
            "ls &",
            "cat < x",
            "git commit -F - <<'EOF'\nmsg\nEOF",
            "echo x > notes.txt",
            "git status | sh",
            "ls | xargs rm",
            "python3 -c 'import os'",
            "python3",
            "python3 -m pip install x",
            "rg --pre cat x",
            "find . -delete",
            "bash script.sh",
            "git status; rm -rf .",
        ]:
            self.check(command, False)

    def test_other_agent_passes(self):
        self.check("rm -rf /", True, agent="frodo")

    def test_cwd_outside_repo(self):
        self.check("git status", False, cwd=BRAIN)

    def test_garbage_input(self):
        proc = subprocess.run([sys.executable, os.path.join(HERE, "bash_guard.py"), "aule"],
                              input="not json", capture_output=True, text=True, env=ENV)
        self.assertEqual(proc.returncode, 2)


class WriteGuard(unittest.TestCase):
    def write(self, path, args, allowed, agent="aule"):
        code, err = run("guard.py", args, {
            "agent_type": agent, "cwd": REPO,
            "tool_name": "Write", "tool_input": {"file_path": path, "content": "x"},
        })
        self.assertEqual(code, 0 if allowed else 2, f"{path}: {err}")

    def read(self, tool, tool_input, allowed):
        code, err = run("guard.py", ["aule", "--read", "repo"], {
            "agent_type": "aule", "cwd": REPO, "tool_name": tool, "tool_input": tool_input,
        })
        self.assertEqual(code, 0 if allowed else 2, f"{tool} {tool_input}: {err}")

    def test_repo_writes(self):
        repo = ["aule", "repo"]
        self.write(os.path.join(REPO, ".claude/agents/aule.md"), repo, True)
        self.write(os.path.join(REPO, ".claude/hooks/x/guard.py"), repo, True)
        self.write("IMPLEMENTATION.md", repo, True)
        self.write(os.path.join(REPO, ".git/config"), repo, False)
        self.write(os.path.join(BRAIN, "core/profile.md"), repo, False)
        self.write("../brain/backlog/x.md", repo, False)
        self.write(os.path.join(tempfile.gettempdir(), "x.md"), repo, False)

    def test_existing_specs_unchanged(self):
        strider = ["strider", "brain:current/trips"]
        self.write(os.path.join(BRAIN, "current/trips/x.md"), strider, True, agent="strider")
        self.write(os.path.join(BRAIN, "current/trips/x.py"), strider, False, agent="strider")
        self.write(os.path.join(REPO, "x.md"), strider, False, agent="strider")
        frodo = ["frodo", "brain:knowledge", "!brain:knowledge/personas"]
        self.write(os.path.join(BRAIN, "knowledge/personas/x/p.md"), frodo, False, agent="frodo")
        self.write(os.path.join(BRAIN, "knowledge/places/x.md"), frodo, True, agent="frodo")

    def test_reads(self):
        self.read("Read", {"file_path": os.path.join(REPO, "CLAUDE.md")}, True)
        self.read("Read", {"file_path": ".claude/rules/dev.md"}, True)
        self.read("Grep", {"pattern": "aule"}, True)
        self.read("Grep", {"pattern": "/brain/", "path": ".claude"}, True)
        self.read("Glob", {"pattern": ".claude/agents/*.md"}, True)
        self.read("Glob", {"pattern": "**/*.py", "path": REPO}, True)
        self.read("Read", {"file_path": os.path.join(BRAIN, "core/profile.md")}, False)
        self.read("Read", {"file_path": "../brain/CLAUDE.md"}, False)
        self.read("Grep", {"pattern": "x", "path": BRAIN}, False)
        self.read("Grep", {"pattern": "x", "path": ".."}, False)
        self.read("Glob", {"pattern": "../brain/**/*.md"}, False)
        self.read("Glob", {"pattern": BRAIN + "/**/*.md"}, False)
        self.read("Glob", {"pattern": "*.md", "path": BRAIN}, False)


if __name__ == "__main__":
    unittest.main()
