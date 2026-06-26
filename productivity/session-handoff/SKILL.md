---
name: "session-handoff"
description: "Use when the user says 'session handoff', 'wrap up session', 'hand off', 'handoff summary', or wants a structured end-of-session summary before clearing context. Produces a chat-only handoff covering decisions, shipped changes, key files, running state, verification steps, deferrals, and open questions so a fresh agent can continue seamlessly."
---

# Session Handoff

## Overview

Produce a repeatable end-of-session summary so the user can `/clear` and start a fresh agent without losing continuity. The next agent should be able to pick up by reading this summary alone.

This is a **context-handoff artifact**, not a status report. The audience is a future instance of Claude, not a stakeholder.

## Core Content

### When to invoke

User says: "session handoff", "wrap up session", "hand off", "handoff summary", "let's wrap up", "summarize before I clear", or any near-equivalent. Also invoke proactively if the user says they're about to `/clear` without having run it yet.

### How to produce the summary

1. **Review the full conversation**, not just the last few turns. Handoffs miss things when they only summarize recent context.
2. **Pull state from these sources (in order):**
   - Plan files referenced this session.
   - TodoWrite state — any in-progress or pending tasks.
   - Background processes started with `run_in_background` — shell IDs are load-bearing for the next agent.
   - Files created or modified this session — you know what you touched; don't grep to re-discover.
   - Memory files written or updated.
   - Unresolved questions — things you asked the user that never got a clear answer.
3. **Do NOT audit the filesystem.** This is synthesis of what happened in this session. No `git log`, no broad `Glob` sweeps. If you didn't touch it this session, it doesn't belong here.
4. **Produce the output in chat.** Do not write a file. Do not update memory.

### Output template — use exactly this structure, every time

```
# Session Handoff — <one-line title of what this session was about>

## Where it started
<2-3 sentences: what the user asked for, key framing or constraints that emerged>

## Decisions locked + what shipped
- <decision or change> — <why, and where it lives (absolute path if a file)>
- ...

## Key files for next session
- `<absolute path>` — <why the next agent should read this first>
- Plan file: `<path>` (if a plan drove the session)
- Memory files touched: `<paths>` (if any)

## Running state
- Background processes: <shell IDs + what they are + how to kill> — or "none"
- Dev servers / ports: <url + port> — or "none"
- Open worktrees / branches: <paths> — or "none"

## Verification — how to confirm things still work
- `<command>` — <expected outcome>
- ...

## Deferred + open questions
- Deferred: <item> — <why pushed to later>
- Open: <question needing the user's input> — <context>

## Pick up here
<1-2 sentences: the single most likely next action for a fresh agent>
```

### Hard rules

1. **Chat output only.** Never write the handoff to a file. Never update memory from this skill.
2. **Never invent state.** If a section has nothing to report, write "none" — do not omit the section. Structure stability is the point.
3. **Absolute paths always.** The next agent may have a different working directory.
4. **Name the plan file first** in "Key files" if one drove the session.
5. **Background process IDs are critical.** If you started any `run_in_background` shells, their IDs must appear with the kill command — the next agent cannot find them otherwise.

## Anti-Patterns

**Don't summarize the last 3 turns and call it a handoff.** Review the whole conversation.

**Don't list files by relative path.** The next agent may not know the working directory.

**Don't skip the "Running state" section** because nothing is running — write "none" instead. Structure stability lets the next agent skim quickly.

**Don't write the summary to a file.** Chat-only by design. A file that gets stale is worse than no handoff.

**Don't add "what went well / what went poorly."** This isn't a retro. Terse and concrete — paths, commands, shell IDs, decisions.

**Don't recommend next steps beyond the single "Pick up here" line.** The next agent decides; you just hand off.

## Cross-References

- [engineering/write-a-skill](../../engineering/write-a-skill/SKILL.md) — how skills like this one are authored
- [engineering/workflow-builder](../../engineering/workflow-builder/SKILL.md) — automate multi-session workflows
- [productivity/claude-coach](../../productivity/claude-coach/SKILL.md) — general session effectiveness guidance
