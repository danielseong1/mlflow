"""
Analysis Report Manager for generating structured markdown reports.
"""

import os
from typing import Any


class AnalysisReportManager:
    """Manages creation and updates of analysis reports in markdown format."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.operational_issue_count = 0
        self.quality_issue_count = 0
        self.strength_count = 0

    def create_report(self, agent_name: str, agent_overview: str) -> None:
        """
        Create a new analysis report with template structure.

        Args:
            agent_name: Name of the agent being analyzed
            agent_overview: Overview description of the agent
        """
        template = f"""# {agent_name} Analysis Report

## Executive Summary

[To be filled at the end]

## Agent Overview

{agent_overview}

## Summary Statistics

- **Total Traces Analyzed:** [number]
- **Success Rate:** [percentage]
- **Latency Distribution:**
  - P50 (Median): [value]
  - P90: [value]
  - P95: [value]
  - P99: [value]
  - Max: [value]
- **Analysis Period:** [date range]

## Operational Issues

## Quality Issues

## Strengths & Successes

## Refuted Hypotheses

## Recommendations

[To be filled at the end - organize by priority]

## Conclusion

[To be filled at the end]
"""

        with open(self.filepath, "w") as f:
            f.write(template)

    def add_issue(
        self,
        category: str,
        title: str,
        finding: str,
        evidence: list[dict[str, Any]],
        root_cause: str,
        impact: str,
    ) -> None:
        """
        Add an issue to the report under the appropriate category section.

        Args:
            category: "operational" or "quality"
            title: Issue title
            finding: One-sentence summary
            evidence: List of evidence dictionaries
            root_cause: Explanation of why the issue occurs
            impact: Quantified impact description
        """
        # Read current content
        with open(self.filepath) as f:
            content = f.read()

        # Determine issue number and section marker
        if category == "operational":
            self.operational_issue_count = content.count(
                "## Operational Issues\n\n### "
            )
            issue_num = self.operational_issue_count + 1
            section_marker = "## Operational Issues"
            next_section = "## Quality Issues"
        else:  # quality
            self.quality_issue_count = content.count("## Quality Issues\n\n### ")
            issue_num = self.quality_issue_count + 1
            section_marker = "## Quality Issues"
            next_section = "## Strengths & Successes"

        # Format evidence - same structure for both categories
        evidence_lines = []
        for ev in evidence:
            trace_id = ev.get("trace_id", "unknown")
            request = ev.get("request", "")
            response = ev.get("response", "")
            rationale = ev.get("rationale", "")

            # Add trace header (include latency for operational issues if provided)
            if category == "operational" and "latency_ms" in ev:
                latency = ev.get("latency_ms")
                evidence_lines.append(f"- **{trace_id}** ({latency}ms)")
            else:
                evidence_lines.append(f"- **{trace_id}**")

            # Add request
            evidence_lines.append(f'  - Request: "{request}"')

            # Add response
            evidence_lines.append(f'  - Response: "{response}"')

            # Add rationale (required - explains how this trace supports the hypothesis)
            if rationale:
                evidence_lines.append(f"  - Rationale: {rationale}")

        evidence_text = "\n".join(evidence_lines)

        # Build issue text
        issue_text = f"""
### {issue_num}. {title} (CONFIRMED)

**Finding:** {finding}

**Evidence:**

{evidence_text}

**Root Cause:** {root_cause}

**Impact:** {impact}

"""

        # Find insertion point (right after section header)
        section_start = content.find(section_marker)
        if section_start == -1:
            raise ValueError(f"Section '{section_marker}' not found in report")

        # Find next section to insert before it
        next_section_start = content.find(next_section, section_start)
        if next_section_start == -1:
            raise ValueError(f"Next section '{next_section}' not found in report")

        # Insert issue text
        new_content = (
            content[:next_section_start]
            + issue_text
            + "\n"
            + content[next_section_start:]
        )

        # Write back
        with open(self.filepath, "w") as f:
            f.write(new_content)

    def add_strength(self, title: str, description: str, evidence: list[str]) -> None:
        """
        Add a strength/success to the report.

        Args:
            title: Strength title
            description: Description of what's working well
            evidence: List of evidence strings (metrics, examples)
        """
        # Read current content
        with open(self.filepath) as f:
            content = f.read()

        # Determine strength number
        self.strength_count = content.count("## Strengths & Successes\n\n### ")
        strength_num = self.strength_count + 1

        # Format evidence
        evidence_text = "\n".join(f"- {ev}" for ev in evidence)

        # Build strength text
        strength_text = f"""
### {strength_num}. {title} (CONFIRMED)

{description}

{evidence_text}

"""

        # Find insertion point
        section_marker = "## Strengths & Successes"
        next_section = "## Refuted Hypotheses"

        section_start = content.find(section_marker)
        if section_start == -1:
            raise ValueError(f"Section '{section_marker}' not found in report")

        next_section_start = content.find(next_section, section_start)
        if next_section_start == -1:
            raise ValueError(f"Next section '{next_section}' not found in report")

        # Insert strength text
        new_content = (
            content[:next_section_start]
            + strength_text
            + "\n"
            + content[next_section_start:]
        )

        # Write back
        with open(self.filepath, "w") as f:
            f.write(new_content)

    def add_refuted_hypothesis(self, hypothesis: str, reason: str) -> None:
        """
        Add a refuted hypothesis to the report.

        Args:
            hypothesis: Hypothesis statement that was refuted
            reason: Brief explanation of why it was refuted
        """
        # Read current content
        with open(self.filepath) as f:
            content = f.read()

        # Build refuted hypothesis text
        refuted_text = f"- **{hypothesis}**: {reason}\n"

        # Find insertion point
        section_marker = "## Refuted Hypotheses"
        next_section = "## Recommendations"

        section_start = content.find(section_marker)
        if section_start == -1:
            raise ValueError(f"Section '{section_marker}' not found in report")

        next_section_start = content.find(next_section, section_start)
        if next_section_start == -1:
            raise ValueError(f"Next section '{next_section}' not found in report")

        # Find where to insert (after section header, before next section)
        insert_pos = content.find("\n", section_start) + 1

        # Check if section is empty (has another header immediately after)
        if content[insert_pos:next_section_start].strip() == "":
            # Section is empty, add content
            new_content = (
                content[:insert_pos] + "\n" + refuted_text + content[insert_pos:]
            )
        else:
            # Append to existing content
            new_content = (
                content[:next_section_start]
                + refuted_text
                + content[next_section_start:]
            )

        # Write back
        with open(self.filepath, "w") as f:
            f.write(new_content)

    def finalize_report(
        self,
        executive_summary: str,
        statistics: dict[str, Any],
        recommendations: dict[str, list[str]],
        conclusion: str,
    ) -> None:
        """
        Finalize the report by filling in summary sections.

        Args:
            executive_summary: Executive summary paragraph
            statistics: Summary statistics dict
            recommendations: Recommendations dict with priority categories
            conclusion: Conclusion paragraph
        """
        # Read current content
        with open(self.filepath) as f:
            content = f.read()

        # Replace Executive Summary
        content = content.replace(
            "## Executive Summary\n\n[To be filled at the end]",
            f"## Executive Summary\n\n{executive_summary}",
        )

        # Replace Summary Statistics
        stats_lines = [
            f"- **Total Traces Analyzed:** {statistics.get('total_traces', 'N/A')}",
            f"- **Success Rate:** {statistics.get('success_rate', 'N/A')}",
            "- **Latency Distribution:**",
            f"  - P50 (Median): {statistics.get('p50_latency', 'N/A')}",
            f"  - P90: {statistics.get('p90_latency', 'N/A')}",
            f"  - P95: {statistics.get('p95_latency', 'N/A')}",
            f"  - P99: {statistics.get('p99_latency', 'N/A')}",
            f"  - Max: {statistics.get('max_latency', 'N/A')}",
            f"- **Analysis Period:** {statistics.get('analysis_period', 'N/A')}",
        ]
        stats_text = "\n".join(stats_lines)

        # Find and replace statistics section
        stats_start = content.find("## Summary Statistics\n\n")
        stats_end = content.find("## Operational Issues")
        if stats_start != -1 and stats_end != -1:
            content = (
                content[: stats_start + len("## Summary Statistics\n\n")]
                + stats_text
                + "\n\n"
                + content[stats_end:]
            )

        # Replace Recommendations
        rec_lines = []
        for category, items in recommendations.items():
            category_title = category.replace("_", " ").title()
            rec_lines.append(f"\n### {category_title}\n")
            for item in items:
                rec_lines.append(f"- {item}")
        rec_text = "\n".join(rec_lines)

        content = content.replace(
            "## Recommendations\n\n[To be filled at the end - organize by priority]",
            f"## Recommendations{rec_text}",
        )

        # Replace Conclusion
        content = content.replace(
            "## Conclusion\n\n[To be filled at the end]",
            f"## Conclusion\n\n{conclusion}",
        )

        # Write back
        with open(self.filepath, "w") as f:
            f.write(content)
