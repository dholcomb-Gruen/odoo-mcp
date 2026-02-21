# Odoo MCP Server — Setup Guide

## 1 · Install the Python dependency

```bash
cd ~/odoo-mcp
pip install -r requirements.txt
```

> The only new package is `mcp` (the official Anthropic MCP SDK for Python).  
> Your existing `xmlrpc` + `ssl` setup needs nothing extra.

---

## 2 · Set your Odoo API password

Never hard-code credentials. Export the password before launching Claude Desktop:

**macOS / Linux (add to `~/.zshrc` or `~/.bashrc`):**
```bash
export ODOO_PASSWORD="your_odoo_password_here"
```

Then reload: `source ~/.zshrc`

**Windows (PowerShell):**
```powershell
[Environment]::SetEnvironmentVariable("ODOO_PASSWORD","your_password","User")
```

---

## 3 · Add the server to Claude Desktop

Open (or create) the config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Paste this (adjust the path to match where you cloned the repo):

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python3",
      "args": ["/Users/YOUR_USERNAME/odoo-mcp/server.py"],
      "env": {
        "ODOO_URL":      "https://www.gruen-systems.com",
        "ODOO_DB":       "v18.gruen-systems.com",
        "ODOO_USER":     "d.holcomb@gruen-systems.com",
        "ODOO_PASSWORD": "your_odoo_password_here"
      }
    }
  }
}
```

> **Tip:** Putting the password directly in the JSON is convenient for a single-user machine.  
> For a shared machine prefer the env-var approach in step 2 and omit `ODOO_PASSWORD` from the JSON.

---

## 4 · Restart Claude Desktop

Fully quit (Cmd+Q / Alt+F4) and relaunch.  
You should see an **MCP icon** (hammer 🔨 or plug 🔌) in the bottom-right of the chat input.

Click it → you'll see all 10 Odoo tools listed.

---

## 5 · Test it

Try these prompts in Claude Desktop:

```
Search for our top 5 partners
```
```
Show me all open sale orders
```
```
List unpaid invoices (state = posted)
```
```
What fields are available on crm.lead?
```
```
Create a new contact: name = "Test Corp", email = "test@example.com", is_company = true
```

---

## Available Tools

| Tool | What it does |
|------|-------------|
| `odoo_search_partners` | Search contacts by name or email |
| `odoo_get_partner` | Full detail for one partner by ID |
| `odoo_search_records` | Generic search on any model |
| `odoo_get_record` | Read a single record by model + ID |
| `odoo_list_sale_orders` | List sale orders (filter by state) |
| `odoo_list_invoices` | List customer invoices |
| `odoo_list_crm_leads` | List CRM leads / opportunities |
| `odoo_create_record` | Create a record in any model |
| `odoo_update_record` | Update a record in any model |
| `odoo_get_fields` | Introspect available fields on a model |

---

## Troubleshooting

**Server not appearing in Claude Desktop?**
- Check logs: `~/Library/Logs/Claude/mcp-server-odoo.log` (macOS)
- Make sure `python3` is in PATH — try using the full path: `/usr/bin/python3` or `/usr/local/bin/python3`
- Run the server manually to check for errors: `python3 ~/odoo-mcp/server.py`

**Authentication errors?**
- Verify `ODOO_PASSWORD` is set correctly
- Test with your existing `test_odoo.py` first

**SSL errors?**
- The server inherits Python's default SSL context (same as your working test script)
- If you had custom SSL workarounds in `test_odoo.py`, replicate them in the `_rpc_common` / `_rpc_object` helper functions in `server.py`
