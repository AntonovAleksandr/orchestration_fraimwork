#!/usr/bin/env python3
"""Claude Skills CLI - Discover and manage orchestration skills (no external deps)"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict, Optional

class SkillsCLI:
    def __init__(self):
        self.root = Path.cwd()
        self.skills_dir = self.root / ".claude" / "skills"
        self.skills_index = self._build_index()
    
    def _build_index(self) -> Dict:
        """Build index of all available skills"""
        index = {}
        
        if not self.skills_dir.exists():
            return index
        
        # Scan all .md files
        for skill_file in sorted(self.skills_dir.glob("*.md")):
            skill_name = skill_file.stem
            
            # Skip special files
            if skill_name in ["SKILLS-TAXONOMY", "skills-registry", "README"]:
                continue
            
            layer = self._determine_layer(skill_name)
            platform = self._determine_platform(skill_name)
            
            index[skill_name] = {
                "name": skill_name,
                "file": str(skill_file),
                "layer": layer,
                "platform": platform,
                "description": self._extract_description(skill_file),
            }
        
        return index
    
    def _determine_layer(self, skill_name: str) -> str:
        if skill_name.startswith("develop-"):
            return "stack"
        elif skill_name.startswith("pattern-"):
            return "generic"
        else:
            return "project"
    
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
        print(f"📦 Loading skills for project: {project}")
        print()
        
        project_skills = self._get_layer_skills("project", project)
        stack_skills = self._get_layer_skills("stack")
        generic_skills = self._get_layer_skills("generic")
        
        all_skills = []
        
        if project_skills:
            print("🔹 PROJECT SKILLS")
            for skill in project_skills:
                print(f"  ✓ {skill}")
                all_skills.append(skill)
            print()
        
        if stack_skills:
            print("🔹 STACK SKILLS")
            for skill in stack_skills[:5]:
                print(f"  ✓ {skill}")
                all_skills.append(skill)
            if len(stack_skills) > 5:
                print(f"  ... and {len(stack_skills) - 5} more")
            print()
        
        if generic_skills:
            print("🔹 GENERIC SKILLS")
            for skill in generic_skills:
                print(f"  ✓ {skill}")
                all_skills.append(skill)
            print()
        
        print(f"✅ Loaded {len(all_skills)} skills for {project}")
        return True
    
    def _get_layer_skills(self, layer: str, project: str = None) -> List[str]:
        skills = []
        
        if layer == "project" and project:
            for name, info in self.skills_index.items():
                if info["layer"] == "project" and project.lower() in name.lower():
                    skills.append(name)
        else:
            for name, info in self.skills_index.items():
                if info["layer"] == layer:
                    skills.append(name)
        
        return sorted(skills)
    
    def cmd_list(self, layer: Optional[str] = None, platform: Optional[str] = None):
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
        if skill_name not in self.skills_index:
            print(f"❌ Skill not found: {skill_name}")
            return False
        
        info = self.skills_index[skill_name]
        print(f"📖 {skill_name}")
        print(f"   Layer: {info['layer']} | Platform: {info['platform']}")
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
    
    def cmd_validate(self):
        print("✓ Validating skills...")
        print()
        print(f"✅ {len(self.skills_index)} skills found")
        
        by_layer = {}
        for info in self.skills_index.values():
            l = info["layer"]
            by_layer[l] = by_layer.get(l, 0) + 1
        
        for layer in ["project", "stack", "generic"]:
            if layer in by_layer:
                print(f"   {layer.upper()}: {by_layer[layer]}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="Claude Skills CLI")
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
    
    subparsers.add_parser("validate")
    
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
            return 0 if cli.cmd_validate() else 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
