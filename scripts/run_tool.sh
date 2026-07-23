#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: run_tool.sh <script.py|script.mjs|script.js> [args...]" >&2
  exit 2
fi

target=$1
shift
if [ ! -f "$target" ]; then
  echo "[FAIL] script not found: $target" >&2
  exit 2
fi

case "$target" in
  *.py)
    python_bin=${CODEX_PYTHON_BIN:-}
    bundled_python="${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    system_python=$(command -v python3 || true)
    required_module=""
    case "$(basename "$target")" in
      audit_layout_runtime.py) required_module="playwright" ;;
      generate_pptx_from_plan.py) required_module="pptx" ;;
    esac
    if [ -z "$python_bin" ]; then
      for candidate in "$bundled_python" "$system_python"; do
        [ -x "$candidate" ] || continue
        if [ -z "$required_module" ] || "$candidate" -c "import $required_module" >/dev/null 2>&1; then
          python_bin=$candidate
          break
        fi
      done
    fi
    if [ -z "$python_bin" ]; then
      echo "[FAIL] Python 3 with module '${required_module:-stdlib}' not found; install requirements.txt or set CODEX_PYTHON_BIN" >&2
      exit 2
    fi
    exec "$python_bin" "$target" "$@"
    ;;
  *.mjs|*.js)
    node_bin=${CODEX_NODE_BIN:-}
    bundled_node="${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    bundled_modules="${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    if [ -z "$node_bin" ] && [ -x "$bundled_node" ]; then node_bin=$bundled_node; fi
    if [ -z "$node_bin" ]; then node_bin=$(command -v node || true); fi
    if [ -z "$node_bin" ]; then
      echo "[FAIL] Node.js not found; set CODEX_NODE_BIN" >&2
      exit 2
    fi
    if [ -z "${CODEX_NODE_MODULES:-}" ] && [ -d "$bundled_modules" ]; then
      CODEX_NODE_MODULES=$bundled_modules
      export CODEX_NODE_MODULES
    fi
    exec "$node_bin" "$target" "$@"
    ;;
  *)
    echo "[FAIL] unsupported script type: $target" >&2
    exit 2
    ;;
esac
