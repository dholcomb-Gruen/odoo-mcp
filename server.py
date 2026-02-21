#!/usr/bin/env python3
import os
import xmlrpc.client
import ssl
import json
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import uvicorn
from mcp import types

ODOO_URL      = os.getenv("ODOO_URL",      "https://www.gruen-systems.com")
ODOO_DB       = os.getenv("ODOO_DB",       "v18.gruen-systems.com")
ODOO_USER     = os.getenv("ODOO_USER",     "d.holcomb@gruen-systems.com")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

def _ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _rpc_common():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", context=_ssl_context())

def _rpc_object(uid: int):
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", context=_ssl_context())

def authenticate() -> int:
    common = _rpc_common()
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise ValueError("Odoo authentication failed")
    return uid

def execute(model: str, method: str, *args, **kwargs) -> Any:
    uid = authenticate()
    obj = _rpc_object(uid)
    return obj.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)

server = Server("odoo-mcp")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name="odoo_search_partners", description="Search Odoo contacts/partners.", inputSchema={"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","default":10}},"required":[]}),
        types.Tool(name="odoo_get_partner", description="Get full details for a single partner by ID.", inputSchema={"type":"object","properties":{"partner_id":{"type":"integer"}},"required":["partner_id"]}),
        types.Tool(name="odoo_search_records", description="Generic Odoo record search.", inputSchema={"type":"object","properties":{"model":{"type":"string"},"domain":{"type":"array","default":[]},"fields":{"type":"array","default":[]},"limit":{"type":"integer","default":10}},"required":["model"]}),
        types.Tool(name="odoo_get_record", description="Read a single Odoo record.", inputSchema={"type":"object","properties":{"model":{"type":"string"},"record_id":{"type":"integer"},"fields":{"type":"array","default":[]}},"required":["model","record_id"]}),
        types.Tool(name="odoo_list_sale_orders", description="List sale orders.", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":10},"state":{"type":"string","default":""}},"required":[]}),
        types.Tool(name="odoo_list_invoices", description="List customer invoices.", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":10},"state":{"type":"string","default":""}},"required":[]}),
        types.Tool(name="odoo_list_crm_leads", description="List CRM leads/opportunities.", inputSchema={"type":"object","properties":{"limit":{"type":"integer","default":10},"stage":{"type":"string","default":""}},"required":[]}),
        types.Tool(name="odoo_create_record", description="Create a new record in any Odoo model.", inputSchema={"type":"object","properties":{"model":{"type":"string"},"values":{"type":"object"}},"required":["model","values"]}),
        types.Tool(name="odoo_update_record", description="Update an existing Odoo record.", inputSchema={"type":"object","properties":{"model":{"type":"string"},"record_id":{"type":"integer"},"values":{"type":"object"}},"required":["model","record_id","values"]}),
        types.Tool(name="odoo_get_fields", description="Introspect fields on an Odoo model.", inputSchema={"type":"object","properties":{"model":{"type":"string"}},"required":["model"]}),
    ]

def ok(data): return [types.TextContent(type="text", text=json.dumps(data))]
def err(msg): return [types.TextContent(type="text", text=json.dumps({"error": msg}))]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "odoo_search_partners":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            domain = ["|", ["name","ilike",query], ["email","ilike",query]] if query else []
            return ok(execute("res.partner","search_read",domain,fields=["id","name","email","phone","is_company"],limit=limit))
        elif name == "odoo_get_partner":
            return ok(execute("res.partner","read",[arguments["partner_id"]],fields=[])[0])
        elif name == "odoo_search_records":
            return ok(execute(arguments["model"],"search_read",arguments.get("domain",[]),fields=arguments.get("fields",[]),limit=arguments.get("limit",10)))
        elif name == "odoo_get_record":
            results = execute(arguments["model"],"read",[arguments["record_id"]],fields=arguments.get("fields",[]))
            return ok(results[0] if results else {})
        elif name == "odoo_list_sale_orders":
            domain = [["state","=",arguments["state"]]] if arguments.get("state") else []
            return ok(execute("sale.order","search_read",domain,fields=["id","name","partner_id","state","amount_total","date_order"],limit=arguments.get("limit",10)))
        elif name == "odoo_list_invoices":
            domain = [["move_type","=","out_invoice"]]
            if arguments.get("state"):
                domain.append(["state","=",arguments["state"]])
            return ok(execute("account.move","search_read",domain,fields=["id","name","partner_id","state","amount_total","invoice_date"],limit=arguments.get("limit",10)))
        elif name == "odoo_list_crm_leads":
            domain = [["stage_id.name","ilike",arguments["stage"]]] if arguments.get("stage") else []
            return ok(execute("crm.lead","search_read",domain,fields=["id","name","partner_id","stage_id","user_id","expected_revenue","probability"],limit=arguments.get("limit",10)))
        elif name == "odoo_create_record":
            return ok({"created_id": execute(arguments["model"],"create",arguments["values"])})
        elif name == "odoo_update_record":
            return ok({"success": execute(arguments["model"],"write",[arguments["record_id"]],arguments["values"])})
        elif name == "odoo_get_fields":
            fields = execute(arguments["model"],"fields_get",[],attributes=["string","type","required"])
            return ok({k:{"label":v.get("string"),"type":v.get("type")} for k,v in sorted(fields.items())})
        else:
            return err(f"Unknown tool: {name}")
    except Exception as exc:
        return err(str(exc))

sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())
    return Response()

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return Response()

app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/messages/", endpoint=handle_messages, methods=["POST"]),
])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
