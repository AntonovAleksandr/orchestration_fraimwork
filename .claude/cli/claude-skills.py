#!/usr/bin/env python3
"""Claude Skills CLI - Discover and manage orchestration skills (3-layer structure)"""

import os
import sys
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

class SkillsCLI:
    def __init__(self):
        self.root = Path.cwd()
        self.skills_dir = self.root / ".claude" / "skills"
        self.layers = {
            "project": self.skills_dir / "project",
            "stack": self.skills_dir / "stack",
            "generic": self.skills_dir / "generic",
        }
        self.skills_index = self._build_index()
        self.framework_version = "1.0.0"  # Current framework version

    def _extract_frontmatter(self, skill_file: Path) -> Dict:
        """Extract YAML frontmatter from skill file"""
        try:
            with open(skill_file) as f:
                content = f.read()
                if content.startswith("---"):
                    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
                    if match:
                        fm = match.group(1)
                        result = {}
                        for line in fm.split("\n"):
                            if ": " in line:
                                key, val = line.split(": ", 1)
                                result[key.strip()] = val.strip()
                        return result
        except:
            pass
        return {}

    def _build_index(self) -> Dict:
        """Build index from 3-layer structure"""
        index = {}

        for layer_name, layer_path in self.layers.items():
            if not layer_path.exists():
                continue

            for skill_file in sorted(layer_path.glob("*.md")):
                skill_name = skill_file.stem
                platform = self._determine_platform(skill_name)
                frontmatter = self._extract_frontmatter(skill_file)

                index[skill_name] = {
                    "name": skill_name,
                    "file": str(skill_file),
                    "layer": layer_name,
                    "platform": platform,
                    "description": self._extract_description(skill_file),
                    "version": frontmatter.get("version", "1.0.0"),
                    "deprecated": frontmatter.get("deprecated", "false").lower() == "true",
                    "compatibility": frontmatter.get("compatibility", ">=1.0.0"),
                }

        return index
    
    def _determine_platform(self, skill_name: str) -> str:
        platforms = {
            "ensi": "ENSI",
            "oms": "OMS",
            "site": "Site",
            "mobile": "Mobile",
            "integration": "Integration",
            "gloriaots": "Gloria OTS",
            "go": "Go",
        }
        
        for key, platform in platforms.items():
            if key in skill_name:
                return platform
        return "Generic"
    
    def _extract_description(self, skill_file: Path) -> str:
        try:
            with open(skill_file) as f:
                for line in f.read().split('\n')[1:]:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        return line[:80]
        except:
            pass
        return ""
    
    def cmd_load(self, project: str, verbose: bool = False):
        """Load skills for a project"""
        print(f"📦 Loading skills for project: {project}")
        print()
        
        all_skills = []
        
        # Load project-specific
        project_skills = [s for n, s in self.skills_index.items() 
                         if s["layer"] == "project" and project.lower() in n.lower()]
        if project_skills:
            print("🔹 PROJECT SKILLS")
            for skill in project_skills:
                print(f"  ✓ {skill['name']}")
                all_skills.append(skill)
            print()
        
        # Load stack
        stack_skills = [s for n, s in self.skills_index.items() if s["layer"] == "stack"]
        if stack_skills:
            print("🔹 STACK SKILLS")
            for skill in stack_skills[:5]:
                print(f"  ✓ {skill['name']}")
                all_skills.append(skill)
            if len(stack_skills) > 5:
                print(f"  ... and {len(stack_skills) - 5} more")
            print()
        
        # Load generic
        generic_skills = [s for n, s in self.skills_index.items() if s["layer"] == "generic"]
        if generic_skills:
            print("🔹 GENERIC SKILLS")
            for skill in generic_skills:
                print(f"  ✓ {skill['name']}")
                all_skills.append(skill)
            print()
        
        print(f"✅ Loaded {len(all_skills)} skills for {project}")
        return True
    
    def cmd_list(self, layer: Optional[str] = None, platform: Optional[str] = None):
        """List available skills"""
        skills = self.skills_index
        
        if layer:
            skills = {k: v for k, v in skills.items() if v["layer"].lower() == layer.lower()}
        
        if platform:
            skills = {k: v for k, v in skills.items() if v["platform"].lower() == platform.lower()}
        
        if not skills:
            print("No skills found")
            return
        
        print(f"📚 Available Skills ({len(skills)})")
        print()
        
        by_layer = {}
        for name, info in sorted(skills.items()):
            l = info["layer"]
            if l not in by_layer:
                by_layer[l] = []
            by_layer[l].append((name, info))
        
        for layer_name in ["project", "stack", "generic"]:
            if layer_name not in by_layer:
                continue
            
            print(f"🔹 {layer_name.upper()}")
            for name, info in by_layer[layer_name]:
                print(f"  {name}")
                if info["description"]:
                    print(f"    {info['description']}")
            print()
    
    def cmd_show(self, skill_name: str):
        """Show skill details"""
        if skill_name not in self.skills_index:
            print(f"❌ Skill not found: {skill_name}")
            return False

        info = self.skills_index[skill_name]
        print(f"📖 {skill_name}")
        print(f"   Version: {info['version']} | Compatibility: {info['compatibility']}")
        print(f"   Layer: {info['layer']} | Platform: {info['platform']}")
        if info['deprecated']:
            print(f"   ⚠️  DEPRECATED")
        print()

        try:
            with open(info['file']) as f:
                lines = f.readlines()[:15]
                for line in lines:
                    print(line.rstrip())
        except:
            print("Could not read skill file")

        return True
    
    def cmd_search(self, keyword: str):
        """Search for skills"""
        results = []
        keyword_lower = keyword.lower()
        
        for name, info in self.skills_index.items():
            if keyword_lower in name.lower() or keyword_lower in info['description'].lower():
                results.append((name, info))
        
        if not results:
            print(f"No skills matching: {keyword}")
            return
        
        print(f"🔍 Search: {keyword}")
        print()
        
        for name, info in sorted(results):
            print(f"  {name}")
            print(f"    Layer: {info['layer']} | Platform: {info['platform']}")
    
    def cmd_validate(self, check_compatibility: bool = False):
        """Validate skills registry"""
        print("✓ Validating 3-layer structure...")
        print()

        by_layer = {}
        deprecated_count = 0
        for info in self.skills_index.values():
            l = info["layer"]
            by_layer[l] = by_layer.get(l, 0) + 1
            if info["deprecated"]:
                deprecated_count += 1

        print(f"✅ {len(self.skills_index)} skills found")
        for layer in ["project", "stack", "generic"]:
            if layer in by_layer:
                print(f"   {layer.upper()}: {by_layer[layer]}")

        # Check directories exist
        for layer, path in self.layers.items():
            if path.exists():
                count = len(list(path.glob("*.md")))
                print(f"   📁 {layer}/: {count} files")

        if deprecated_count > 0:
            print(f"   ⚠️  {deprecated_count} deprecated skills")

        if check_compatibility:
            print()
            print("Checking compatibility with agents...")
            self._check_agent_compatibility()

        return True

    def _check_agent_compatibility(self):
        """Check if agents reference valid skills"""
        agents_dir = self.root / ".claude" / "agents"
        if not agents_dir.exists():
            print("   ℹ️  No agents directory found")
            return

        issues = []
        for agent_file in agents_dir.glob("*.md"):
            with open(agent_file) as f:
                content = f.read()
                # Find skill references like "- pattern-development-ensi"
                mentioned = re.findall(r"[-•] ([a-z0-9\-]+(?:_[a-z0-9\-]+)*)", content)
                for skill_name in mentioned:
                    if skill_name not in self.skills_index:
                        issues.append((agent_file.name, skill_name))

        if issues:
            print("   ❌ Broken references found:")
            for agent, skill in issues:
                print(f"      {agent} → {skill} (NOT FOUND)")
        else:
            print("   ✅ All agent skill references valid")

def main():
    parser = argparse.ArgumentParser(description="Claude Skills CLI (3-layer)")
    subparsers = parser.add_subparsers(dest="command")
    
    load_p = subparsers.add_parser("load")
    load_p.add_argument("--project", required=True)
    load_p.add_argument("-v", "--verbose", action="store_true")
    
    list_p = subparsers.add_parser("list")
    list_p.add_argument("--layer", choices=["project", "stack", "generic"])
    list_p.add_argument("--platform")
    
    show_p = subparsers.add_parser("show")
    show_p.add_argument("skill")
    
    search_p = subparsers.add_parser("search")
    search_p.add_argument("keyword")
    
    validate_p = subparsers.add_parser("validate")
    validate_p.add_argument("--compatibility", action="store_true", help="Check agent compatibility")

    args = parser.parse_args()
    cli = SkillsCLI()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "load":
            return 0 if cli.cmd_load(args.project, args.verbose) else 1
        elif args.command == "list":
            cli.cmd_list(args.layer, args.platform)
            return 0
        elif args.command == "show":
            return 0 if cli.cmd_show(args.skill) else 1
        elif args.command == "search":
            cli.cmd_search(args.keyword)
            return 0
        elif args.command == "validate":
            return 0 if cli.cmd_validate(args.compatibility) else 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
