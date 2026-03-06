#!/bin/bash
# 数字3桁-アルファベット4文字のショートIDを生成する
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec uv run --project "$SCRIPT_DIR" python "$SCRIPT_DIR/small-id-gen.py" "$@"
