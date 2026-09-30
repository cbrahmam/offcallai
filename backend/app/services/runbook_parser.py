# backend/app/services/runbook_parser.py
"""
Runbook content parser service.
Extracts executable steps from markdown content with optional YAML frontmatter.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedStep:
    """A single executable step from a runbook."""
    name: str
    command: str
    requires_approval: bool = False
    timeout: int = 300  # seconds
    step_number: int = 0


@dataclass
class ParsedRunbook:
    """Parsed runbook with executable steps and variables."""
    steps: List[ParsedStep] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None
    raw_markdown: Optional[str] = None


class RunbookParser:
    """
    Parses runbook content from markdown format.

    Supports two formats:

    Format 1: YAML Frontmatter
    ```
    ---
    steps:
      - name: Check service status
        command: kubectl get pods -n {{namespace}}
      - name: Restart deployment
        command: kubectl rollout restart deployment/{{service}}
        requires_approval: true
    variables:
      namespace: production
      service: api-server
    ---

    # Runbook Description
    ...
    ```

    Format 2: Markdown with code blocks
    ```
    # Database Runbook

    ## Step 1: Check connections
    ```bash
    psql -c "SELECT count(*) FROM pg_stat_activity"
    ```

    ## Step 2: Kill idle connections
    ```bash
    psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle'"
    ```
    ```
    """

    YAML_FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n',
        re.DOTALL
    )

    CODE_BLOCK_PATTERN = re.compile(
        r'```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n```',
        re.DOTALL | re.IGNORECASE
    )

    STEP_HEADER_PATTERN = re.compile(
        r'^##\s*(?:Step\s*\d+[:\s]*)?(.+)$',
        re.MULTILINE | re.IGNORECASE
    )

    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    def __init__(self):
        pass

    def parse(self, content: str) -> ParsedRunbook:
        """
        Parse runbook content and extract executable steps.

        Args:
            content: Markdown content with optional YAML frontmatter.

        Returns:
            ParsedRunbook with steps and variables.
        """
        result = ParsedRunbook(raw_markdown=content)

        # Try to parse YAML frontmatter first
        frontmatter_match = self.YAML_FRONTMATTER_PATTERN.match(content)

        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            markdown_content = content[frontmatter_match.end():]
            result = self._parse_yaml_frontmatter(frontmatter)
            result.raw_markdown = markdown_content
            result.description = self._extract_description(markdown_content)
        else:
            # Parse markdown code blocks
            result = self._parse_markdown_steps(content)
            result.description = self._extract_description(content)

        return result

    def _parse_yaml_frontmatter(self, frontmatter: str) -> ParsedRunbook:
        """Parse YAML frontmatter to extract steps and variables."""
        try:
            import yaml
            data = yaml.safe_load(frontmatter)

            if not isinstance(data, dict):
                logger.warning("Frontmatter is not a valid YAML dictionary")
                return ParsedRunbook()

            result = ParsedRunbook()

            # Extract variables
            result.variables = data.get("variables", {})
            if not isinstance(result.variables, dict):
                result.variables = {}

            # Extract steps
            steps_data = data.get("steps", [])
            if isinstance(steps_data, list):
                for i, step_data in enumerate(steps_data):
                    if isinstance(step_data, dict):
                        step = ParsedStep(
                            name=step_data.get("name", f"Step {i + 1}"),
                            command=step_data.get("command", ""),
                            requires_approval=step_data.get("requires_approval", False),
                            timeout=step_data.get("timeout", 300),
                            step_number=i + 1
                        )
                        if step.command:
                            result.steps.append(step)

            return result

        except ImportError:
            logger.warning("PyYAML not installed, falling back to markdown parsing")
            return ParsedRunbook()
        except Exception as e:
            logger.error(f"Error parsing YAML frontmatter: {e}")
            return ParsedRunbook()

    def _parse_markdown_steps(self, content: str) -> ParsedRunbook:
        """Parse steps from markdown code blocks."""
        result = ParsedRunbook()

        # Find all step headers and their positions
        headers = list(self.STEP_HEADER_PATTERN.finditer(content))

        # Find all code blocks
        code_blocks = list(self.CODE_BLOCK_PATTERN.finditer(content))

        if not code_blocks:
            return result

        step_number = 0
        for code_match in code_blocks:
            step_number += 1
            command = code_match.group(1).strip()

            # Find the nearest preceding header
            step_name = f"Step {step_number}"
            code_start = code_match.start()

            for header in reversed(headers):
                if header.start() < code_start:
                    step_name = header.group(1).strip()
                    break

            step = ParsedStep(
                name=step_name,
                command=command,
                step_number=step_number
            )
            result.steps.append(step)

        return result

    def _extract_description(self, content: str) -> Optional[str]:
        """Extract the first paragraph or heading as description."""
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('```'):
                return line[:500]  # Limit description length

            if line.startswith('# '):
                return line[2:].strip()

        return None

    def substitute_variables(
        self,
        command: str,
        variables: Dict[str, str],
        execution_context: Dict[str, Any] = None
    ) -> str:
        """
        Substitute variables in a command.

        Variables can come from:
        1. Runbook's predefined variables
        2. Execution context (e.g., alert data)
        3. Environment variables (not implemented for security)

        Args:
            command: Command with {{variable}} placeholders.
            variables: Runbook-defined variables.
            execution_context: Runtime context (alert data, etc.).

        Returns:
            Command with variables substituted.
        """
        merged_vars = {**variables}

        if execution_context:
            # Flatten execution context for variable substitution
            for key, value in execution_context.items():
                if isinstance(value, str):
                    merged_vars[key] = value
                elif isinstance(value, (int, float, bool)):
                    merged_vars[key] = str(value)

        def replace_var(match):
            var_name = match.group(1)
            if var_name in merged_vars:
                # Sanitize the value to prevent command injection
                return self._sanitize_value(merged_vars[var_name])
            else:
                logger.warning(f"Variable '{var_name}' not found, leaving as-is")
                return match.group(0)

        return self.VARIABLE_PATTERN.sub(replace_var, command)

    def _sanitize_value(self, value: str) -> str:
        """
        Sanitize a value for safe shell substitution.

        This provides basic protection against command injection.
        For production use, consider more robust sanitization or
        using proper shell escaping libraries.
        """
        # Remove or escape dangerous shell metacharacters
        dangerous_chars = ['`', '$', '(', ')', ';', '|', '&', '\n', '\r']

        sanitized = value
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')

        # Also escape single quotes for safe embedding in shell strings
        sanitized = sanitized.replace("'", "'\"'\"'")

        return sanitized

    def get_required_variables(self, content: str) -> List[str]:
        """Extract all variable names used in the runbook content."""
        matches = self.VARIABLE_PATTERN.findall(content)
        return list(set(matches))

    def validate_runbook(self, content: str) -> Dict[str, Any]:
        """
        Validate runbook content and return validation results.

        Returns:
            Dict with 'valid' bool and 'errors'/'warnings' lists.
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "step_count": 0,
            "variables_used": [],
            "has_approval_steps": False
        }

        try:
            parsed = self.parse(content)
            result["step_count"] = len(parsed.steps)
            result["variables_used"] = self.get_required_variables(content)
            result["has_approval_steps"] = any(s.requires_approval for s in parsed.steps)

            if not parsed.steps:
                result["warnings"].append("No executable steps found in runbook")

            # Check for undefined variables
            defined_vars = set(parsed.variables.keys())
            used_vars = set(result["variables_used"])
            undefined = used_vars - defined_vars

            if undefined:
                result["warnings"].append(
                    f"Variables used but not defined: {', '.join(undefined)}. "
                    "They must be provided at execution time."
                )

            # Check for empty commands
            for step in parsed.steps:
                if not step.command.strip():
                    result["errors"].append(f"Step '{step.name}' has an empty command")
                    result["valid"] = False

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Failed to parse runbook: {str(e)}")

        return result


# Singleton instance
runbook_parser = RunbookParser()
