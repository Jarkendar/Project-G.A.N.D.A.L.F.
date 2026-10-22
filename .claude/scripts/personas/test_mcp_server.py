#!/usr/bin/env python3
# Refusals and the stage report of the persona MCP tools. Run with the Gimli
# venv (it holds the MCP SDK):
#   .claude/scripts/gimli/.venv/bin/python .claude/scripts/personas/test_mcp_server.py
# Touches nothing in brain/: the checks that write use a throwaway slug and
# are asserted to be refused before any file is made.

import asyncio
import inspect
import sys
import types
import unittest
from pathlib import Path

try:
    import mcp  # noqa: F401
except ImportError:  # plain python3: a stand-in for the SDK, enough to import the tools
    class _Server:
        def __init__(self, **kw): pass
        def tool(self, **kw): return lambda fn: fn
    for name, attrs in (("mcp", {}), ("mcp.server", {}), ("mcp.server.mcpserver", {"MCPServer": _Server}),
                        ("mcp_types", {"ToolAnnotations": lambda **kw: kw})):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcp_server as m  # noqa: E402


class Tools(unittest.TestCase):
    def test_bad_slug(self):
        for bad in ("../x", "A b", "", "x/y", "-x"):
            self.assertIn("refused", m.status(bad), bad)
            self.assertIn("refused", m.catalog_put(bad, [{"id": "a", "url": "https://x.y"}]), bad)

    def test_bad_ids(self):
        for bad in ("../x", "a b", "", "/etc/passwd"):
            self.assertIn("refused", m.prepare("will-larson", [bad]), bad)
            self.assertIn("refused", m.verify_quotes("will-larson", [bad]), bad)
        self.assertIn("refused", m.prepare("will-larson", []))

    def test_catalog_checks(self):
        self.assertIn("empty", m.catalog_put("will-larson", []))
        self.assertIn("unknown fields", m.catalog_put("will-larson", [{"id": "a", "url": "https://x.y", "cmd": "x"}]))
        self.assertIn("http", m.catalog_put("will-larson", [{"id": "a", "url": "file:///etc/passwd"}]))
        self.assertIn("duplicate", m.catalog_put("will-larson", [{"id": "a", "url": "https://x.y"}] * 2))

    def test_drafts_outside_tmp(self):
        self.assertIn("under /tmp", m.assemble("will-larson", "/home", ["a"]))
        self.assertIn("under /tmp", m.assemble("will-larson", "/tmp/../etc", ["a"]))

    def test_validation_checks(self):
        self.assertIn("refused", m.validation_put("will-larson", {"name": "x", "dilemmas": []}))
        self.assertIn("not a run name", m.validation_start("will-larson", run="a b"))

    def test_status_of_unknown_persona(self):
        self.assertIn("no folder yet", m.status("zz-no-such-persona"))


EXPECTED_PARAMS = {
    "status": ["slug"],
    "catalog_put": ["slug", "sources"],
    "fetch": ["slug", "wayback", "only"],
    "prepare": ["slug", "ids"],
    "assemble": ["slug", "drafts_dir", "ids", "write"],
    "verify_quotes": ["slug", "ids"],
    "validation_put": ["slug", "config"],
    "validation_start": ["slug", "run", "reuse_bare"],
    "validation_status": ["slug", "run"],
}


class Schemas(unittest.TestCase):
    def test_signatures_survive_guard(self):
        for name, params in EXPECTED_PARAMS.items():
            self.assertEqual(list(inspect.signature(getattr(m, name)).parameters), params, name)

    def test_server_schemas(self):
        if not hasattr(m.server, "list_tools"):
            self.skipTest("needs the real MCP SDK (Gimli venv)")
        tools = {t.name: t for t in asyncio.run(m.server.list_tools())}
        for name, params in EXPECTED_PARAMS.items():
            self.assertIn(name, tools)
            self.assertEqual(list(tools[name].inputSchema["properties"]), params, name)


if __name__ == "__main__":
    unittest.main()
