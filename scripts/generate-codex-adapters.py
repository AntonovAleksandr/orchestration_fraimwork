#!/usr/bin/env python3
"""Generate local Codex adapters from canonical .claude agents and skills."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Tuple


def parse_agent_markdown(path: Path) -> Tuple[Dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return parse_legacy_header_agent(path, text)

    _, frontmatter_text, body = text.split("---", 2)
    metadata = parse_key_value_block(frontmatter_text)
    validate_agent_metadata(path, metadata)
    return metadata, body.strip()


def parse_legacy_header_agent(path: Path, text: str) -> Tuple[Dict[str, str], str]:
    header, separator, body = text.partition("\n\n")
    if not separator:
        raise ValueError(f"{path} must include metadata followed by a blank line")
    metadata = parse_key_value_block(header)
    validate_agent_metadata(path, metadata)
    return metadata, body.strip()


def parse_key_value_block(text: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def validate_agent_metadata(path: Path, metadata: Dict[str, str]) -> None:
    if "name" not in metadata:
        raise ValueError(f"{path} frontmatter is missing name")
    if "description" not in metadata:
        raise ValueError(f"{path} frontmatter is missing description")


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    if "'''" in value:
        return toml_string(value)
    return f"'''\n{value}\n'''"


def codex_instructions(body: str) -> str:
    return body.replace(".claude/skills/", ".agents/skills/").replace(".Codex/skills/", ".agents/skills/")


def write_codex_agent(source: Path, target_dir: Path) -> None:
    metadata, body = parse_agent_markdown(source)
    target = target_dir / f"{metadata['name']}.toml"
    lines = [
        f"name = {toml_string(metadata['name'])}",
        f"description = {toml_string(metadata['description'])}",
    ]
    lines.append(f"developer_instructions = {toml_multiline(codex_instructions(body))}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def replace_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    if source.exists():
        shutil.copytree(source, target)


def generate(root: Path) -> None:
    claude_agents = root / ".claude" / "agents"
    claude_skills = root / ".claude" / "skills"
    codex_agents = root / ".codex" / "agents"
    agents_skills = root / ".agents" / "skills"

    if not claude_agents.exists():
        raise FileNotFoundError(f"Missing canonical agents directory: {claude_agents}")
    if not claude_skills.exists():
        raise FileNotFoundError(f"Missing canonical skills directory: {claude_skills}")

    if codex_agents.exists():
        shutil.rmtree(codex_agents)
    codex_agents.mkdir(parents=True)

    for source in sorted(claude_agents.glob("*.md")):
        write_codex_agent(source, codex_agents)

    replace_tree(claude_skills, agents_skills)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Workspace root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    generate(root)


if __name__ == "__main__":
    main()
