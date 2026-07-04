import os
import json
from openai import OpenAI

from database import (
    get_dashboard_stats, get_filtered_employees, get_filtered_logs,
    get_all_centres, get_all_checked_in_gadgets, get_employee_by_id,
    get_today_centre_visits
)

SYSTEM_PROMPT = """You are the AI Security Assistant for the MCC Digital ID System — a face recognition-based access control and visitor management system for the City of Mutare municipal council (Zimbabwe).

SYSTEM OVERVIEW:
- Enrolled employees are recognized via facial recognition when entering municipal centres.
- Verified visitors get a visit log with purpose, notes, and optional gadget check-in.
- Unrecognized faces are logged as "unknown" with a saved photo for admin review.
- Site staff can manually override unrecognized visitors via call verification.
- Gadgets (Laptop, Phone, Tablet, Hard Drive, Camera, Other) can be checked in/out per visit.

USER ROLES:
- Admin: Full access — enroll employees, verify visitors, manage logs/centres/staff, view gadgets
- Site Staff: Per-centre access — verify visitors, view centre logs, process gadget check-out, overrides

CENTRES: Civic Centre, Stores, Housing, Chikanga, Hobhouse

DATABASE TABLES:
1. employees — enrolled individuals (id, full_name, role, department, contact, centre, photo_path, face_encoding)
2. visit_logs — visit records (id, employee_id, site_name, status, purpose, notes, timestamp, is_override, override_name, unrecognized_photo_path)
3. users — system accounts (id, username, password_hash, role, assigned_centre)
4. centres — municipal centres (id, name)
5. gadgets — equipment per visit (id, visit_id, gadget_type, gadget_name, serial_number, checked_in_time, checked_out_time)

You help staff understand and interact with the system. Use the available functions to fetch real-time data when answering questions. Be concise, professional, and helpful."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_stats",
            "description": "Get overall system statistics: total enrolled employees, today's visits, total visit logs, unrecognized scan count.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_employees",
            "description": "Search enrolled employees by name, department, role, or centre. All parameters are optional; omit to get all employees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Employee name partial match"},
                    "department": {"type": "string", "description": "Department name"},
                    "role": {"type": "string", "description": "Job role"},
                    "centre": {"type": "string", "description": "Assigned centre"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_visits",
            "description": "Get recent visit logs with optional filters: date (YYYY-MM-DD), site, status (verified/unknown), or employee name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date filter YYYY-MM-DD"},
                    "site": {"type": "string", "description": "Site/centre name"},
                    "status": {"type": "string", "description": "verified or unknown"},
                    "name": {"type": "string", "description": "Employee name partial match"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_centres_list",
            "description": "Get list of all municipal centres.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_checked_in_gadgets",
            "description": "Get all gadgets currently checked in (not checked out) with visitor and centre info.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_centre_visits_today",
            "description": "Get today's visit count for a specific centre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "centre": {"type": "string", "description": "Centre name"}
                },
                "required": ["centre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_details",
            "description": "Get full details for a specific employee by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer", "description": "Employee ID"}
                },
                "required": ["employee_id"]
            }
        }
    }
]


def _call_tool(name, args, db_path):
    if not isinstance(args, dict):
        args = {}
    if name == "get_dashboard_stats":
        return get_dashboard_stats(db_path)
    elif name == "search_employees":
        cleaned = {k: v for k, v in args.items() if v}
        return [
            {"id": e["id"], "full_name": e["full_name"], "role": e["role"],
             "department": e["department"], "centre": e["centre"]}
            for e in get_filtered_employees(db_path, **cleaned)
        ]
    elif name == "get_recent_visits":
        cleaned = {k: v for k, v in args.items() if v}
        logs = get_filtered_logs(db_path, **cleaned)
        for log in logs:
            log.pop("face_encoding", None)
            if "photo_path" in log:
                log.pop("photo_path")
        return logs[:20]
    elif name == "get_all_centres_list":
        return get_all_centres(db_path)
    elif name == "get_checked_in_gadgets":
        return get_all_checked_in_gadgets(db_path)
    elif name == "get_centre_visits_today":
        return {"centre": args["centre"], "today_visits": get_today_centre_visits(db_path, args["centre"])}
    elif name == "get_employee_details":
        return get_employee_by_id(db_path, args["employee_id"])
    return {"error": f"Unknown tool: {name}"}


def get_chatbot_response(messages, db_path):
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("GROK_API_KEY")
    api_base = os.environ.get("AI_API_BASE", "https://openrouter.ai/api/v1")
    model = os.environ.get("AI_MODEL", "qwen/qwen-2.5-72b-instruct")

    if not api_key:
        return "The AI assistant is not configured. Ask an admin to set the AI_API_KEY in the .env file."

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            default_headers={
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "MCC Digital ID System",
            },
        )

        chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        chat_messages.extend(messages)

        resp = client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1024,
        )

        msg = resp.choices[0].message

        if msg.tool_calls:
            chat_messages.append(msg)
            for tc in msg.tool_calls:
                result = _call_tool(tc.function.name, json.loads(tc.function.arguments), db_path)
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)
                })

            final = client.chat.completions.create(
                model=model,
                messages=chat_messages,
                temperature=0.3,
                max_tokens=1024,
            )
            return final.choices[0].message.content or "Done."

        return msg.content

    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "unauthorized" in err_str.lower() or "authentication" in err_str.lower():
            return "Invalid API key. If using OpenRouter, get a key from https://openrouter.ai/keys and set AI_API_KEY in .env."
        if "402" in err_str:
            return "Your API provider requires payment. Add billing or use a free model."
        if "429" in err_str:
            return "Rate limited. Wait a moment and try again."
        if "model" in err_str.lower() and "not found" in err_str.lower():
            return f"Model '{model}' not found. Check AI_MODEL in .env or try a different model."
        return f"AI error: {err_str[:200]}"
