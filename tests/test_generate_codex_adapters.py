import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import TestCase, main


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate-codex-adapters.py"


class GenerateCodexAdaptersTest(TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="codex-adapters-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir))
        (self.tmpdir / ".claude" / "agents").mkdir(parents=True)
        (self.tmpdir / ".claude" / "skills" / "demo-skill").mkdir(parents=True)

    def run_generator(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.tmpdir)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_generates_codex_agent_toml_from_claude_agent_markdown(self) -> None:
        (self.tmpdir / ".claude" / "agents" / "demo-agent.md").write_text(
            textwrap.dedent(
                """\
                ---
                name: demo-agent
                description: Use for demo tasks.
                tools: Read, Grep
                model: sonnet
                ---

                You are the demo agent.

                Read `.claude/skills/demo-skill/SKILL.md` before acting.
                """
            ),
            encoding="utf-8",
        )
        (self.tmpdir / ".claude" / "skills" / "demo-skill" / "SKILL.md").write_text(
            "# Demo Skill\n",
            encoding="utf-8",
        )

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        agent_toml = (self.tmpdir / ".codex" / "agents" / "demo-agent.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('name = "demo-agent"', agent_toml)
        self.assertIn('description = "Use for demo tasks."', agent_toml)
        self.assertNotIn('model = "sonnet"', agent_toml)
        self.assertIn("developer_instructions = '''", agent_toml)
        self.assertIn("You are the demo agent.", agent_toml)
        self.assertIn("Read `.agents/skills/demo-skill/SKILL.md` before acting.", agent_toml)
        self.assertNotIn("tools:", agent_toml)

    def test_preserves_backslash_heavy_instructions_as_literal_toml(self) -> None:
        (self.tmpdir / ".claude" / "agents" / "regex-agent.md").write_text(
            textwrap.dedent(
                """\
                ---
                name: regex-agent
                description: Use for regex tasks.
                ---

                ```bash
                grep -rn "function checkoutAction\\|class CheckoutController" platform/integration/
                grep -rn "process\\.env\\.|Config\\." platform/mobile-app/
                ```

                Convert `App\\Domain\\Foo\\Bar` to `app/Domain/Foo/Bar.php`.
                """
            ),
            encoding="utf-8",
        )
        (self.tmpdir / ".claude" / "skills" / "demo-skill" / "SKILL.md").write_text(
            "# Demo Skill\n",
            encoding="utf-8",
        )

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        agent_toml = (self.tmpdir / ".codex" / "agents" / "regex-agent.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn("developer_instructions = '''", agent_toml)
        self.assertIn('checkoutAction\\|class CheckoutController', agent_toml)
        self.assertIn('process\\.env\\.|Config\\.', agent_toml)
        self.assertIn('App\\Domain\\Foo\\Bar', agent_toml)

    def test_syncs_claude_skills_to_agents_skills_and_removes_stale_files(self) -> None:
        (self.tmpdir / ".claude" / "agents" / "demo-agent.md").write_text(
            "---\nname: demo-agent\ndescription: Demo.\n---\n\nBody.\n",
            encoding="utf-8",
        )
        (self.tmpdir / ".claude" / "skills" / "demo-skill" / "SKILL.md").write_text(
            "# Demo Skill\n",
            encoding="utf-8",
        )
        stale = self.tmpdir / ".agents" / "skills" / "stale-skill" / "SKILL.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("# Stale\n", encoding="utf-8")

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.tmpdir / ".agents" / "skills" / "demo-skill" / "SKILL.md").exists())
        self.assertFalse(stale.exists())

    def test_generates_codex_agent_from_legacy_header_without_frontmatter(self) -> None:
        (self.tmpdir / ".claude" / "agents" / "legacy-agent.md").write_text(
            textwrap.dedent(
                """\
                name: legacy-agent
                description: Legacy imported agent.
                model: sonnet
                color: cyan

                You are the legacy imported agent.
                """
            ),
            encoding="utf-8",
        )
        (self.tmpdir / ".claude" / "skills" / "demo-skill" / "SKILL.md").write_text(
            "# Demo Skill\n",
            encoding="utf-8",
        )

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        agent_toml = (self.tmpdir / ".codex" / "agents" / "legacy-agent.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('name = "legacy-agent"', agent_toml)
        self.assertIn('description = "Legacy imported agent."', agent_toml)
        self.assertIn("You are the legacy imported agent.", agent_toml)


if __name__ == "__main__":
    main()
