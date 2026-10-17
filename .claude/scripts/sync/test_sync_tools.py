#!/usr/bin/env python3
# Cases for gitops.py on throwaway repositories (a bare origin and clones in a
# temporary directory) — never on the real repos.
#
#   python3 .claude/scripts/sync/test_sync_tools.py

import fcntl
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gitops  # noqa: E402

IDENT = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
             GIT_COMMITTER_EMAIL="t@t")


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env=IDENT)


def commit(repo, name, text="x"):
    with open(os.path.join(repo, name), "w") as fh:
        fh.write(text)
    sh(repo, "git", "add", name)
    sh(repo, "git", "commit", "-m", f"add {name}")


class Repos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.origin = os.path.join(root, "origin.git")
        self.repo = os.path.join(root, "repo")
        self.other = os.path.join(root, "other")
        sh(root, "git", "init", "--bare", "-b", "main", self.origin)
        sh(root, "git", "clone", self.origin, self.repo)
        sh(self.repo, "git", "checkout", "-b", "main")
        commit(self.repo, "a.txt")
        sh(self.repo, "git", "push", "-u", "origin", "main")
        sh(root, "git", "clone", self.origin, self.other)

    def tearDown(self):
        self.tmp.cleanup()

    def push_from_other(self, name="b.txt"):
        commit(self.other, name)
        sh(self.other, "git", "push", "origin", "main")

    def head(self, repo=None):
        return gitops.head_of(repo or self.repo)


class Status(Repos):
    def test_clean_on_main(self):
        out = gitops.status_one(self.repo, "r")
        self.assertIn("main | clean |", out)
        self.assertIn("behind 0, ahead 0", out)

    def test_dirty_tracked_and_untracked(self):
        with open(os.path.join(self.repo, "a.txt"), "w") as fh:
            fh.write("changed")
        with open(os.path.join(self.repo, "new.txt"), "w") as fh:
            fh.write("n")
        out = gitops.status_one(self.repo, "r")
        self.assertIn("dirty: 2 files", out)
        self.assertIn("a.txt", out)
        self.assertNotIn("changed", out)  # names only, never content

    def test_no_upstream_and_detached(self):
        sh(self.repo, "git", "checkout", "-b", "feat/x")
        self.assertIn("feat/x | clean", gitops.status_one(self.repo, "r"))
        self.assertIn("no upstream", gitops.status_one(self.repo, "r"))
        sh(self.repo, "git", "checkout", "--detach")
        self.assertIn("detached HEAD", gitops.status_one(self.repo, "r"))

    def test_behind_after_fetch(self):
        self.push_from_other()
        sh(self.repo, "git", "fetch", "origin")
        self.assertIn("behind 1, ahead 0", gitops.status_one(self.repo, "r"))

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertIn("not a git repo", gitops.status_one(empty, "r"))


class Log(Repos):
    def log(self, repo, n):
        real = gitops.paths
        gitops.paths = lambda project_dir=None: {"gandalf": self.repo, "brain": None}
        try:
            return gitops.log(repo, n)
        finally:
            gitops.paths = real

    def test_counts_and_clamps(self):
        for i in range(3):
            commit(self.repo, f"f{i}.txt")
        self.assertEqual(len(self.log("gandalf", 2).splitlines()), 2)
        self.assertEqual(len(self.log("gandalf", 500).splitlines()), 4)  # clamped, fewer exist
        self.assertEqual(len(self.log("gandalf", 0).splitlines()), 1)    # clamped up to 1
        self.assertEqual(len(self.log("gandalf", -5).splitlines()), 1)

    def test_bad_arguments(self):
        self.assertIn("unknown repo", self.log("../etc", 3))
        self.assertIn("unknown repo", self.log("origin", 3))
        self.assertIn("must be a number", self.log("gandalf", "--all"))
        self.assertIn("must be a number", self.log("gandalf", None))
        self.assertIn("not found", self.log("brain", 3))

    def test_no_diff_content(self):
        commit(self.repo, "secret.txt", "TOPSECRET")
        self.assertNotIn("TOPSECRET", self.log("gandalf", 5))


class CheckoutMain(Repos):
    def branch(self):
        return gitops.branch_of(self.repo)

    def feature(self, pushed=True):
        sh(self.repo, "git", "checkout", "-b", "feat/x")
        commit(self.repo, "f.txt")
        if pushed:
            sh(self.repo, "git", "push", "-u", "origin", "feat/x")

    def test_from_a_pushed_branch_to_main_and_fast_forward(self):
        self.feature()
        self.push_from_other()
        out = gitops.checkout_main_one(self.repo, "r")
        self.assertIn("feat/x -> main", out)
        self.assertEqual(self.branch(), "main")
        self.assertTrue(os.path.exists(os.path.join(self.repo, "b.txt")))

    def test_already_on_main_pulls(self):
        self.push_from_other()
        self.assertIn("r: main,", gitops.checkout_main_one(self.repo, "r"))
        self.assertTrue(os.path.exists(os.path.join(self.repo, "b.txt")))

    def test_dirty_tree_refused_nothing_changed(self):
        self.feature()
        path = os.path.join(self.repo, "f.txt")
        with open(path, "w") as fh:
            fh.write("edited")
        out = gitops.checkout_main_one(self.repo, "r")
        self.assertIn("REFUSED", out)
        self.assertEqual(self.branch(), "feat/x")
        with open(path) as fh:
            self.assertEqual(fh.read(), "edited")

    def test_untracked_file_also_refuses(self):
        self.feature()
        with open(os.path.join(self.repo, "u.txt"), "w") as fh:
            fh.write("u")
        self.assertIn("REFUSED", gitops.checkout_main_one(self.repo, "r"))
        self.assertEqual(self.branch(), "feat/x")

    def test_unpushed_commits_refused(self):
        self.feature(pushed=False)
        out = gitops.checkout_main_one(self.repo, "r")
        self.assertIn("REFUSED", out)
        self.assertIn("unpushed", out)
        self.assertEqual(self.branch(), "feat/x")

    def test_commit_ahead_of_its_upstream_refused(self):
        self.feature()
        commit(self.repo, "g.txt")
        self.assertIn("REFUSED", gitops.checkout_main_one(self.repo, "r"))
        self.assertEqual(self.branch(), "feat/x")

    def test_detached_head_refused(self):
        sh(self.repo, "git", "checkout", "--detach")
        self.assertIn("REFUSED", gitops.checkout_main_one(self.repo, "r"))
        self.assertEqual(self.branch(), "detached HEAD")

    def test_diverged_main_left_alone(self):
        commit(self.repo, "local.txt")  # unpushed commit on main
        self.push_from_other()
        before = self.head()
        out = gitops.checkout_main_one(self.repo, "r")
        self.assertIn("DIVERGED", out)
        self.assertEqual(self.head(), before)

    def test_offline_changes_nothing(self):
        self.feature()
        sh(self.repo, "git", "remote", "set-url", "origin", os.path.join(self.tmp.name, "gone.git"))
        out = gitops.checkout_main_one(self.repo, "r")
        self.assertIn("offline", out)
        self.assertEqual(self.branch(), "feat/x")

    def test_lock_held_by_another(self):
        lock_path = os.path.join(self.tmp.name, "lock")
        real_lock, real_paths = gitops.LOCK_FILE, gitops.paths
        gitops.LOCK_FILE = lock_path
        gitops.paths = lambda project_dir=None: {"gandalf": self.repo, "brain": None}
        holder = open(lock_path, "w")
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            self.assertIn("another session holds the lock", gitops.checkout_main("gandalf"))
        finally:
            holder.close()
            gitops.LOCK_FILE, gitops.paths = real_lock, real_paths

    def test_unknown_repo_and_both(self):
        self.assertIn("unknown repo", gitops.checkout_main("../x"))
        self.assertIn("unknown repo", gitops.checkout_main("origin"))


class Whitelist(unittest.TestCase):
    def test_other_subcommands_refused(self):
        for args in [("commit", "-m", "x"), ("push",), ("reset", "--hard"), ("merge", "x"),
                     ("checkout", "-f", "main"), ("stash",), ("branch", "-D", "x"), (),
                     ("switch", "-c", "x"), ("switch", "other", "--quiet"), ("pull", "--no-ff"),
                     ("fetch", "--all"), ("fetch", "https://example.com/x.git", "--quiet")]:
            with self.assertRaises(ValueError, msg=str(args)):
                gitops.git(".", *args)


VENV = os.path.join(HERE, "..", "gimli", ".venv", "bin", "python")


@unittest.skipUnless(os.path.exists(VENV), "the Gimli venv is not here")
class Handshake(unittest.TestCase):
    def test_tools_are_listed(self):
        import json
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "status", "arguments": {}}},
        ]
        # The server stops at end of input, so keep stdin open until the last
        # reply (id 3) has come back.
        proc = subprocess.Popen([VENV, os.path.join(HERE, "mcp_server.py")],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
        replies = {}
        try:
            for msg in msgs:
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
            while 3 not in replies:
                line = proc.stdout.readline()
                if not line:
                    break
                try:
                    reply = json.loads(line)
                except ValueError:
                    continue
                if "id" in reply:
                    replies[reply["id"]] = reply
        finally:
            proc.stdin.close()
            proc.stdout.close()
            proc.wait(timeout=30)
        names = {t["name"] for t in replies[2]["result"]["tools"]}
        self.assertEqual(names, {"pull", "status", "log", "checkout_main"})
        text = replies[3]["result"]["content"][0]["text"]
        self.assertIn("gandalf:", text)


if __name__ == "__main__":
    unittest.main()
