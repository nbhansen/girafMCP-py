# Next Steps - Making GIRAF MCP Useful

Quick guide to populate the knowledge base and deploy for students.

## 1. Set Up Your Documents Folder

Create a folder for PDFs (research papers, handover docs):

```bash
mkdir -p ~/giraf-documents/{research,handover,guides}
```

Add to your `.env`:
```
GIRAF_DOCUMENTS_DIR=/home/youruser/giraf-documents
```

### What to add:

| Folder | Content |
|--------|---------|
| `research/` | Papers on autism, visual schedules, AAC |
| `handover/` | Previous semester handover reports |
| `guides/` | Student handbooks, onboarding docs |

**Tag each folder** with `_meta.yaml`:
```yaml
# research/_meta.yaml
tags: ["research", "academic", "autism"]
```

## 2. Update Project Context

Edit `data/context.yaml` with current info:

```yaml
semester: "Fall 2025"
focus: "Your current focus"

current_priorities:
  - "Issue #XX: Description"
  - "Issue #YY: Description"

known_gotchas:
  - issue: "Common problem students hit"
    workaround: "How to solve it"

recent_decisions:
  - date: "2025-XX-XX"
    decision: "What was decided"
    context: "Link to ADR or discussion"
```

## 3. Expand Domain Knowledge

Add markdown files to `data/domain/` for topics students ask about:

**Priority topics to add:**
- [ ] `communication-strategies.md` - AAC, PECS, how GIRAF supports them
- [ ] `transitions.md` - Why transitions are hard, how the app helps
- [ ] `customization.md` - Why personalization matters for autism
- [ ] `caregiver-perspective.md` - What parents/teachers need

## 4. Review Personas

Check `data/personas.yaml` matches your actual user types. Consider adding:
- Specific course personas (e.g., "SW6 Student", "DAT Student")
- Teaching assistant persona
- External collaborator persona

## 5. Test With Real Questions

Before deploying, test with questions students actually ask:

```
"How do I run the API locally?"
"Where is the meal planning logic?"
"What accessibility standards should I follow?"
"What did last semester's team work on?"
```

## 6. Deploy for Students

### Option A: Students run locally
Share setup instructions (README.md covers this)

### Option B: Shared server
Set up on a server students can connect to via MCP

### Claude Desktop Config for students:
```json
{
  "mcpServers": {
    "giraf": {
      "command": "/path/to/.venv/bin/giraf-mcp",
      "cwd": "/path/to/girafMCP-py",
      "env": {
        "GITHUB_TOKEN": "ghp_...",
        "GIRAF_DOCUMENTS_DIR": "/path/to/documents"
      }
    }
  }
}
```

## 7. Maintenance Checklist

**Each semester:**
- [ ] Update `context.yaml` with new focus/priorities
- [ ] Add previous semester's handover to documents
- [ ] Review and update domain knowledge
- [ ] Test all tools still work

**When issues arise:**
- [ ] Add to `known_gotchas` in context.yaml
- [ ] Update domain knowledge if it's a recurring question

## Quick Wins

1. **Add 2-3 PDFs** to documents folder and run `giraf-mcp --extract` → searchable by keyword
2. **Update context.yaml** with this semester's info → immediate value
3. **Write one domain file** on the most common question → reduces repetitive answers

## File Checklist

```
✅ .env (GITHUB_TOKEN, GIRAF_DOCUMENTS_DIR)
✅ data/context.yaml (current semester info)
✅ data/personas.yaml (review/customize)
⬜ data/domain/*.md (add 3-5 topics)
⬜ $GIRAF_DOCUMENTS_DIR/**/*.pdf (add research/handover)
⬜ $GIRAF_DOCUMENTS_DIR/**/_meta.yaml (tag folders)
```
