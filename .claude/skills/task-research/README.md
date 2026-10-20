# Task Research Skill

Analyzes task requirements and gathers initial information.

## Input
- `task_id`: Unique task identifier
- `task_description`: Full task description

## Output
- `findings`: Structured research results
- `research_complete`: Boolean flag

## Usage
Register this skill and add to your DAG:
```python
dag.add_phase(1, "Research")
validator.pre_execute_validation("run-001", phase=1, required_skills=["task-research"])
```
