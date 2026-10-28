#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "============================================================"
echo "  CDT-Blender: On-Demand Service Launcher (PC 171)"
echo "============================================================"

# Locate Python
PYTHON_BIN=""
if [ -f "${REPO_ROOT}/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [ -f "${REPO_ROOT}/.venv/bin/python" ]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
elif [ -f "${REPO_ROOT}/venv/Scripts/python.exe" ]; then
    PYTHON_BIN="${REPO_ROOT}/venv/Scripts/python.exe"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python not found. Please setup .venv."
    exit 1
fi

PORT="${1:-8812}"
TRANSPORT="${2:-http}"

export BLENDER_MCP_TOKEN="${BLENDER_MCP_TOKEN:-cdt-blender-session-token}"

echo "[INFO] Python:    ${PYTHON_BIN}"
echo "[INFO] Transport: ${TRANSPORT}"
echo "[INFO] Port:      ${PORT}"
echo "[INFO] Note:       Ensure Blender 4.x is running with blender_mcp_addon (port 8888)."
echo "------------------------------------------------------------"
echo "Starting CDT-Blender service on PC 171..."

if [ "${TRANSPORT}" = "stdio" ]; then
    exec "${PYTHON_BIN}" -m blender_mcp_bridge.main serve --transport stdio
else
    exec "${PYTHON_BIN}" -m blender_mcp_bridge.main serve --transport http --host 127.0.0.1 --port "${PORT}"
fi
