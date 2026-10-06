# blender_mcp_bridge/tools/lifecycle.py

from mcp import types


def get_lifecycle_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="reconcile_operation",
            description=(
                "Query or reconcile the receipt state of a mutation after caller timeout, "
                "disconnect, or retry. For promoted operations, verifies native Blender datablock "
                "state. Pass action='resolve' with verified evidence or action='acknowledge' "
                "to inspect or handle uncertainty."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "op_id": {
                        "type": "string",
                        "description": "The semantic operation or request ID to reconcile.",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["query", "resolve", "acknowledge", "clear"],
                        "default": "query",
                        "description": "Action: 'query' inspects state without changing uncertainty set; 'resolve' or 'acknowledge' reconciles state.",
                    },
                },
                "required": ["op_id"],
            },
        ),
        types.Tool(
            name="operation_status",
            description="Read-only query for the cached receipt of an operation ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "op_id": {
                        "type": "string",
                        "description": "The semantic operation ID to inspect.",
                    },
                },
                "required": ["op_id"],
            },
        ),
    ]
