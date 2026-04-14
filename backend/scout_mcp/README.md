# Scout MCP Server

A read-only [Model Context Protocol](https://modelcontextprotocol.io)
server that exposes a curated slice of Scout household data to local
MCP clients — primarily Claude Desktop.

## What it does

Lets Claude Desktop (or any MCP client) ask read-only questions
about a single Scout family's state:

| Tool                    | Returns                                           |
|-------------------------|---------------------------------------------------|
| `get_family_schedule`   | Upcoming calendar events in a date window        |
| `get_tasks_summary`     | Pending personal tasks + today's routines/chores |
| `get_current_meal_plan` | The current approved weekly meal plan            |
| `get_grocery_list`      | Pending grocery items                             |
| `get_action_inbox`      | Pending parent action items (redacted)           |
| `get_recent_briefs`     | Recent morning briefs, weekly retros, anomalies  |
| `get_homework_summary`  | Per-child homework session rollup                |
| `get_ai_usage`          | AI usage + approximate cost rollup                |

There are **no write tools**. No tool takes a `family_id` argument —
the server is bound at boot time to a single family via env vars, so
cross-family access is structurally impossible.

## What it does NOT expose

- Raw blocked moderation message content
- Child personality notes (parent-private)
- Any write / update / delete capability
- Other families' data (even if the DB has them)
- Raw SQL or arbitrary queries
- Internal audit rows or session tokens

## Setup

### 1. Install dependencies

From the `backend/` directory:

```bash
pip install -r requirements.txt
```

The `mcp` Python package is pinned in `requirements.txt`.

### 2. Run locally (smoke test)

```bash
cd backend
export SCOUT_DATABASE_URL='postgresql://scout:scout@localhost:5432/scout'
export SCOUT_MCP_TOKEN='any-non-empty-string'
export SCOUT_MCP_FAMILY_ID='<your-family-uuid>'
python -m scout_mcp
```

The server will block on stdio and wait for MCP protocol frames.
Kill it with Ctrl+C.

To find your family UUID:

```sql
SELECT id, name FROM families;
```

### 3. Wire into Claude Desktop

Edit the Claude Desktop config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add an `mcpServers` entry:

```json
{
  "mcpServers": {
    "scout": {
      "command": "python",
      "args": ["-m", "scout_mcp"],
      "cwd": "/absolute/path/to/Scout/backend",
      "env": {
        "SCOUT_DATABASE_URL": "postgresql://scout:scout@localhost:5432/scout",
        "SCOUT_MCP_TOKEN": "pick-any-non-empty-string",
        "SCOUT_MCP_FAMILY_ID": "<your-family-uuid>"
      }
    }
  }
}
```

Restart Claude Desktop. You should see the Scout tools appear in the
tool picker. Try asking `what's on our schedule this week?` and
Claude will call `get_family_schedule` against your local DB.

## Security model

Three stacked gates protect the data:

1. **Local DB creds** — the server needs `SCOUT_DATABASE_URL` to
   connect. No one on the internet has that.
2. **Opt-in token** — `SCOUT_MCP_TOKEN` must be set, even though its
   value isn't verified remotely. If it's missing, the server
   refuses to boot. This prevents a stray `python -m scout_mcp` from
   accidentally serving data.
3. **Family scoping at boot** — `SCOUT_MCP_FAMILY_ID` is required
   and fixed for the life of the process. Tools cannot target a
   different family.

The moderation inbox is further redacted: `moderation_alert` rows
return with `detail: null` so blocked child message content never
leaves the app. Parents who want the full context open the alert
in-app.

## Troubleshooting

**`boot error: SCOUT_MCP_TOKEN must be set`** — set the env var.
Any non-empty string works.

**`boot error: SCOUT_MCP_FAMILY_ID is not a valid UUID`** — check
the value against `SELECT id FROM families;`.

**Claude Desktop doesn't see the tools** — check `~/Library/Logs/Claude/mcp*.log`
(macOS) or `%APPDATA%\Claude\logs\mcp*.log` (Windows) for boot
errors from the subprocess. The `[scout_mcp]` prefix identifies our
messages.

**ModuleNotFoundError: mcp** — the `mcp` Python package isn't
installed in the `python` on your PATH. Use a venv's python binary
as the `command` in the MCP config.
