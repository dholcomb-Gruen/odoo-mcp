#!/usr/bin/env python3
"""
Odoo 18 MCP Server
Connects Claude Desktop to Odoo via XML-RPC over SSL.
"""

import os
import xmlrpc.client
import ssl
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Config (override with env vars) ──────────────────────────────────────────
ODOO_URL      = os.getenv("ODOO_URL",      "https://www.gruen-systems.com")
ODOO_DB       = os.getenv("ODOO_DB",       "v18.gruen-systems.com")
ODOO_USER     = os.getenv("ODOO_USER",     "d.holcomb@gruen-systems.com")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")   # set via env — never hard-code

# ── XML-RPC helpers ───────────────────────────────────────────────────────────
def _rpc_common() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")

def _rpc_object(uid: int) -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

def authenticate() -> int:
    common = _rpc_common()
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise ValueError("Odoo authentication failed — check credentials/password env var")
    return uid

def execute(model: str, method: str, *args, **kwargs) -> Any:
    uid = authenticate()
    obj = _rpc_object(uid)
    return obj.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)

# ── MCP Server ────────────────────────────────────────────────────────────────
server = Server("odoo-mcp")

# ── Tool definitions ──────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="odoo_search_partners",
            description="Search Odoo contacts/partners by name, email, or other criteria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name or email fragment to search"},
                    "limit":  {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="odoo_get_partner",
            description="Get full details for a single Odoo partner/contact by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "partner_id": {"type": "integer", "description": "res.partner record ID"},
                },
                "required": ["partner_id"],
            },
        ),
        types.Tool(
            name="odoo_search_records",
            description=(
                "Generic Odoo record search. Provide a model name (e.g. 'sale.order', "
                "'account.move', 'crm.lead') and an optional domain filter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model":  {"type": "string", "description": "Odoo model technical name"},
                    "domain": {
                        "type": "array",
                        "description": "Odoo domain list, e.g. [[\"state\",\"=\",\"sale\"]]",
                        "default": [],
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to return (empty = all)",
                        "default": [],
                    },
                    "limit": {"type": "integer", "description": "Max results", "default": 10},
                },
                "required": ["model"],
            },
        ),
        types.Tool(
            name="odoo_get_record",
            description="Read a single Odoo record by model and ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model":     {"type": "string",  "description": "Odoo model technical name"},
                    "record_id": {"type": "integer", "description": "Record ID"},
                    "fields":    {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to return (empty = all)",
                        "default": [],
                    },
                },
                "required": ["model", "record_id"],
            },
        ),
        types.Tool(
            name="odoo_list_sale_orders",
            description="List sale orders with their state, amount and customer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Filter by state: draft, sent, sale, cancel (empty = all)",
                        "default": "",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="odoo_list_invoices",
            description="List customer invoices (account.move) with state and amount.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Filter: draft, posted, cancel (empty = all)",
                        "default": "",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="odoo_list_crm_leads",
            description="List CRM leads/opportunities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Stage name filter (partial match)", "default": ""},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="odoo_create_record",
            description="Create a new record in any Odoo model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model":  {"type": "string", "description": "Odoo model technical name"},
                    "values": {"type": "object", "description": "Field name → value dict"},
                },
                "required": ["model", "values"],
            },
        ),
        types.Tool(
            name="odoo_update_record",
            description="Update an existing Odoo record.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model":     {"type": "string",  "description": "Odoo model technical name"},
                    "record_id": {"type": "integer", "description": "Record ID to update"},
                    "values":    {"type": "object",  "description": "Fields to update"},
                },
                "required": ["model", "record_id", "values"],
            },
        ),
        types.Tool(
            name="odoo_get_fields",
            description="Introspect the fields available on an Odoo model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Odoo model technical name"},
                },
                "required": ["model"],
            },
        ),
    ]


# ── Tool call handlers ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    def ok(data: Any) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

    def err(msg: str) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=f"ERROR: {msg}")]

    try:
        # ── Search Partners ───────────────────────────────────────────────────
        if name == "odoo_search_partners":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            domain = []
            if query:
                domain = ["|", ["name", "ilike", query], ["email", "ilike", query]]
            records = execute(
                "res.partner", "search_read",
                domain,
                fields=["id", "name", "email", "phone", "mobile", "street", "city", "country_id", "is_company"],
                limit=limit,
            )
            return ok(records)

        # ── Get Partner ───────────────────────────────────────────────────────
        elif name == "odoo_get_partner":
            pid = arguments["partner_id"]
            records = execute("res.partner", "read", [pid], fields=[])
            return ok(records[0] if records else {})

        # ── Generic Search ────────────────────────────────────────────────────
        elif name == "odoo_search_records":
            model  = arguments["model"]
            domain = arguments.get("domain", [])
            fields = arguments.get("fields", [])
            limit  = arguments.get("limit", 10)
            kwargs = {"limit": limit}
            if fields:
                kwargs["fields"] = fields
            records = execute(model, "search_read", domain, **kwargs)
            return ok(records)

        # ── Get Record ────────────────────────────────────────────────────────
        elif name == "odoo_get_record":
            model     = arguments["model"]
            record_id = arguments["record_id"]
            fields    = arguments.get("fields", [])
            records   = execute(model, "read", [record_id], fields=fields)
            return ok(records[0] if records else {})

        # ── Sale Orders ───────────────────────────────────────────────────────
        elif name == "odoo_list_sale_orders":
            state = arguments.get("state", "")
            limit = arguments.get("limit", 10)
            domain = [["state", "=", state]] if state else []
            records = execute(
                "sale.order", "search_read",
                domain,
                fields=["id", "name", "partner_id", "state", "amount_total", "date_order", "currency_id"],
                limit=limit,
            )
            return ok(records)

        # ── Invoices ──────────────────────────────────────────────────────────
        elif name == "odoo_list_invoices":
            state = arguments.get("state", "")
            limit = arguments.get("limit", 10)
            domain = [["move_type", "=", "out_invoice"]]
            if state:
                domain.append(["state", "=", state])
            records = execute(
                "account.move", "search_read",
                domain,
                fields=["id", "name", "partner_id", "state", "amount_total", "invoice_date", "invoice_date_due", "currency_id"],
                limit=limit,
            )
            return ok(records)

        # ── CRM Leads ─────────────────────────────────────────────────────────
        elif name == "odoo_list_crm_leads":
            stage  = arguments.get("stage", "")
            limit  = arguments.get("limit", 10)
            domain = []
            if stage:
                domain = [["stage_id.name", "ilike", stage]]
            records = execute(
                "crm.lead", "search_read",
                domain,
                fields=["id", "name", "partner_id", "stage_id", "user_id", "expected_revenue", "probability", "date_deadline"],
                limit=limit,
            )
            return ok(records)

        # ── Create Record ─────────────────────────────────────────────────────
        elif name == "odoo_create_record":
            model  = arguments["model"]
            values = arguments["values"]
            new_id = execute(model, "create", values)
            return ok({"created_id": new_id, "model": model})

        # ── Update Record ─────────────────────────────────────────────────────
        elif name == "odoo_update_record":
            model     = arguments["model"]
            record_id = arguments["record_id"]
            values    = arguments["values"]
            result = execute(model, "write", [record_id], values)
            return ok({"success": result, "model": model, "record_id": record_id})

        # ── Get Fields ────────────────────────────────────────────────────────
        elif name == "odoo_get_fields":
            model  = arguments["model"]
            fields = execute(model, "fields_get", [], attributes=["string", "type", "required", "help"])
            # Return a compact summary sorted by name
            summary = {k: {"label": v.get("string"), "type": v.get("type"), "required": v.get("required")}
                       for k, v in sorted(fields.items())}
            return ok(summary)

        else:
            return err(f"Unknown tool: {name}")

    except Exception as exc:
        return err(str(exc))


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
