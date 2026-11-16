# Plan review (Claude Code only)

When in plan mode, after writing the final plan but before calling ExitPlanMode, spawn a Plan agent to critically review the plan. The agent should check for incorrect assumptions about the codebase, missing steps, scope issues, and pattern mismatches. Append findings as a "## Critical Review" section in the same plan file so the planning agent and user can read them.
