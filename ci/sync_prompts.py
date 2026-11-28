#!/usr/bin/env python3
"""Synchronize kit markdown prompts (`kits/<kit>/prompts/*.md`) into kit `spec.yaml` and `setup.sh`.

Prompts are installed natively inside sandboxes for:
  - Google Antigravity (`~/.gemini/config/rules/<name>.md`)
  - OpenCode (`~/.config/opencode/rules/<name>.md` + `~/.config/opencode/opencode.json` `instructions`)
  - Claude Code (`~/.claude/rules/<name>.md`)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
KITS_DIR = ROOT_DIR / "kits"

BEGIN_MARKER = "# BEGIN GENERATED PROMPTS (managed by ci/sync_prompts.py - do not edit manually)"
END_MARKER = "# END GENERATED PROMPTS"

VALID_TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


@dataclasses.dataclass(frozen=True)
class PromptSpec:
    """Parsed markdown prompt and its normalized per-agent frontmatter metadata."""

    name: str
    trigger: str
    description: str
    globs: str | None
    paths: list[str]
    body: str


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        inner = value[1:-1]
        if value[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def _parse_frontmatter(raw_text: str) -> tuple[dict[str, object], str]:
    """Extract simple YAML frontmatter and body using pure Python stdlib."""
    text = raw_text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text.lstrip("\n")

    rest = text[4:]
    end_idx = rest.find("\n---")
    if end_idx == -1:
        return {}, text.lstrip("\n")

    fm_block = rest[:end_idx]
    after = rest[end_idx + 4 :]
    if after.startswith("\n"):
        after = after[1:]

    meta: dict[str, object] = {}
    current_list_key: str | None = None
    for line in fm_block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if current_list_key and stripped.startswith("- "):
            items = meta.setdefault(current_list_key, [])
            if isinstance(items, list):
                items.append(_unquote(stripped[2:]))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, raw_val = line.split(":", 1)
        key = key.strip()
        val = raw_val.strip()
        if not val:
            meta[key] = []
            current_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [_unquote(x) for x in inner.split(",") if x.strip()] if inner else []
        else:
            meta[key] = _unquote(val)
    return meta, after.lstrip("\n")


def _extract_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return fallback


def load_prompt(path: pathlib.Path) -> PromptSpec:
    """Load and validate a single `.md` prompt file."""
    name = path.stem
    if not SAFE_NAME_RE.match(name):
        raise ValueError(f"Unsafe prompt filename '{path.name}'; use [a-zA-Z0-9._-] only.")

    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    trigger = str(meta.get("trigger") or "always_on").strip()
    if trigger not in VALID_TRIGGERS:
        raise ValueError(f"{path}: invalid trigger '{trigger}' (expected one of {sorted(VALID_TRIGGERS)})")

    description = str(meta.get("description") or "").strip() or _extract_heading(body, name)
    globs = str(meta["globs"]).strip() if meta.get("globs") else None
    raw_paths = meta.get("paths")
    paths = [str(p) for p in raw_paths] if isinstance(raw_paths, list) else ([str(raw_paths)] if raw_paths else [])

    normalized_body = body.rstrip() + "\n"
    return PromptSpec(
        name=name,
        trigger=trigger,
        description=description,
        globs=globs,
        paths=paths,
        body=normalized_body,
    )


def discover_kit_prompts(kit_dir: pathlib.Path) -> list[PromptSpec]:
    """Discover all custom `.md` prompts under `kits/<kit>/prompts/`."""
    prompts_dir = kit_dir / "prompts"
    if not prompts_dir.is_dir():
        return []
    files = sorted(
        p
        for p in prompts_dir.glob("*.md")
        if p.is_file() and not p.name.startswith((".", "_")) and p.name.upper() != "README.MD"
    )
    return [load_prompt(p) for p in files]


def _yaml_double_quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _bash_single_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _pick_delimiter(name: str, body: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "CUSTOM"
    base = f"__SBX_PROMPT_{slug}__"
    candidate = base
    idx = 1
    while candidate in body:
        candidate = f"{base}_{idx}"
        idx += 1
    return candidate


def render_shell_script(prompts: list[PromptSpec]) -> list[str]:
    """Render a self-contained POSIX/bash script installing all prompts natively."""
    lines: list[str] = [
        "set -e",
        "install_kit_prompt() {",
        '  local name="$1" trigger="$2" desc_yaml="$3" globs_yaml="$4" claude_paths_yaml="$5" body_file="$6"',
        '  local agy_dir="$HOME/.gemini/config/rules"',
        '  local oc_dir="$HOME/.config/opencode/rules"',
        '  local claude_dir="$HOME/.claude/rules"',
        '  mkdir -p "$agy_dir"',
        "  {",
        '    printf "%s\\n" "---"',
        '    printf "trigger: %s\\n" "$trigger"',
        '    [ -n "$desc_yaml" ] && printf "description: %s\\n" "$desc_yaml"',
        '    [ -n "$globs_yaml" ] && printf "globs: %s\\n" "$globs_yaml"',
        '    printf "%s\\n\\n" "---"',
        '    cat "$body_file"',
        '  } > "$agy_dir/${name}.md"',
        '  if [ "$trigger" = "always_on" ]; then',
        '    mkdir -p "$oc_dir"',
        '    cp "$body_file" "$oc_dir/${name}.md"',
        "    if command -v jq >/dev/null 2>&1; then",
        '      local oc_cfg="$HOME/.config/opencode/opencode.json"',
        '      local oc_rule="$oc_dir/${name}.md"',
        '      mkdir -p "$(dirname "$oc_cfg")"',
        '      [ -s "$oc_cfg" ] || echo \'{"$schema":"https://opencode.ai/config.json","mcp":{}}\' > "$oc_cfg"',
        '      jq --arg p "$oc_rule" \'.instructions = (((.instructions // []) + [$p]) | unique)\' "$oc_cfg" > "$oc_cfg.tmp"',
        '      mv "$oc_cfg.tmp" "$oc_cfg"',
        "    fi",
        "  fi",
        '  if [ "$trigger" = "always_on" ] || { [ "$trigger" = "glob" ] && [ -n "$claude_paths_yaml" ]; }; then',
        '    mkdir -p "$claude_dir"',
        "    {",
        '      if [ -n "$claude_paths_yaml" ]; then',
        '        printf "%s\\npaths:\\n%b---\\n\\n" "---" "$claude_paths_yaml"',
        "      fi",
        '      cat "$body_file"',
        '    } > "$claude_dir/${name}.md"',
        "  fi",
        "}",
        'tmp_prompt_body="$(mktemp)"',
        'trap \'rm -f "$tmp_prompt_body"\' EXIT',
    ]

    for p in prompts:
        delim = _pick_delimiter(p.name, p.body)
        desc_yaml = _yaml_double_quote(p.description.replace("\n", " ")) if p.description else ""
        globs_yaml = _yaml_double_quote(p.globs.replace("\n", " ")) if p.globs else ""
        claude_paths_yaml = "".join(
            f"  - {_yaml_double_quote(item.replace(chr(10), ' '))}\\n" for item in p.paths
        )

        lines.append(f"cat <<'{delim}' > \"$tmp_prompt_body\"")
        for body_line in p.body.rstrip("\n").split("\n"):
            lines.append(body_line)
        lines.append(delim)
        lines.append(
            "install_kit_prompt "
            + " ".join(
                [
                    _bash_single_quote(p.name),
                    _bash_single_quote(p.trigger),
                    _bash_single_quote(desc_yaml),
                    _bash_single_quote(globs_yaml),
                    _bash_single_quote(claude_paths_yaml),
                    '"$tmp_prompt_body"',
                ]
            )
        )

    lines.append('rm -f "$tmp_prompt_body"')
    lines.append("trap - EXIT")
    return lines


def render_yaml_startup_block(prompts: list[PromptSpec], item_indent: str = "        ") -> str:
    """Render a marked `startup:` item block for `spec.yaml`."""
    script_indent = item_indent + "    "
    prop_indent = item_indent + "  "
    script_lines = render_shell_script(prompts)

    out = [
        f"{item_indent}{BEGIN_MARKER}",
        f"{item_indent}- command: |",
    ]
    for line in script_lines:
        out.append(f"{script_indent}{line}" if line else "")
    out.extend(
        [
            f'{prop_indent}user: "1000"',
            f"{prop_indent}description: Install kit markdown prompts as native rules for Antigravity, OpenCode, and Claude Code",
            f"{item_indent}{END_MARKER}",
        ]
    )
    return "\n".join(out)


def render_setup_sh_block(prompts: list[PromptSpec]) -> str:
    """Render a marked standalone shell block for `setup.sh`."""
    script_lines = [line for line in render_shell_script(prompts) if line != "set -e"]
    return "\n".join([BEGIN_MARKER, *script_lines, END_MARKER])


def _replace_marker_section(content: str, replacement: str | None) -> str | None:
    """Replace `BEGIN_MARKER..END_MARKER` if present. Returns None if markers were not found."""
    pattern = re.compile(
        rf"^[ \t]*{re.escape(BEGIN_MARKER)}\n.*?^[ \t]*{re.escape(END_MARKER)}[ \t]*\n?",
        re.MULTILINE | re.DOTALL,
    )
    if not pattern.search(content):
        return None
    if replacement is None:
        return pattern.sub("", content, count=1)
    return pattern.sub(lambda _: replacement + "\n", content, count=1)


def _insert_into_spec_yaml(content: str, block: str) -> str:
    """Insert generated prompt block into an existing `startup:` section or `capabilities:`."""
    lines = content.splitlines(keepends=True)
    startup_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s+startup:\s*$", line):
            startup_idx = i
            break

    if startup_idx is not None:
        startup_indent = len(lines[startup_idx]) - len(lines[startup_idx].lstrip(" "))
        insert_at = len(lines)
        for j in range(startup_idx + 1, len(lines)):
            stripped = lines[j].strip()
            if not stripped:
                continue
            indent = len(lines[j]) - len(lines[j].lstrip(" "))
            if indent <= startup_indent:
                insert_at = j
                break
        prefix = "".join(lines[:insert_at]).rstrip("\n")
        suffix = "".join(lines[insert_at:])
        sep = "\n\n" if suffix else "\n"
        return f"{prefix}\n\n{block}{sep}{suffix}"

    # Fallback: add a lifecycle@1 capability at the end of capabilities
    block_12 = render_yaml_startup_block_from_block(block)
    return content.rstrip("\n") + "\n\n" + block_12 + "\n"


def render_yaml_startup_block_from_block(startup_item_block: str) -> str:
    return "\n".join(
        [
            "  - type: com.docker.sandbox/lifecycle@1",
            "    config:",
            "      startup:",
            startup_item_block,
        ]
    )


def sync_kit(kit_dir: pathlib.Path, check_only: bool) -> list[pathlib.Path]:
    """Synchronize one kit directory; returns list of files modified (or out-of-sync in check mode)."""
    prompts = discover_kit_prompts(kit_dir)
    changed: list[pathlib.Path] = []

    spec_path = kit_dir / "spec.yaml"
    if spec_path.is_file():
        original = spec_path.read_text(encoding="utf-8")
        block = render_yaml_startup_block(prompts) if prompts else None
        updated = _replace_marker_section(original, block)
        if updated is None and block is not None:
            updated = _insert_into_spec_yaml(original, block)
        if updated is not None and updated != original:
            changed.append(spec_path)
            if not check_only:
                spec_path.write_text(updated, encoding="utf-8")

    setup_path = kit_dir / "setup.sh"
    if setup_path.is_file():
        original = setup_path.read_text(encoding="utf-8")
        block = render_setup_sh_block(prompts) if prompts else None
        updated = _replace_marker_section(original, block)
        if updated is not None and updated != original:
            changed.append(setup_path)
            if not check_only:
                setup_path.write_text(updated, encoding="utf-8")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync kits/<kit>/prompts/*.md into kit spec.yaml and setup.sh"
    )
    parser.add_argument("--kit", action="append", default=[], help="Kit directory name to process (repeatable)")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any kit files are out of sync")
    args = parser.parse_args()

    if args.kit:
        kit_dirs = [KITS_DIR / name for name in args.kit]
    else:
        kit_dirs = sorted(p for p in KITS_DIR.iterdir() if p.is_dir())

    all_changed: list[pathlib.Path] = []
    for kit_dir in kit_dirs:
        if not kit_dir.is_dir():
            print(f"Error: kit directory not found: {kit_dir}", file=sys.stderr)
            return 2
        all_changed.extend(sync_kit(kit_dir, check_only=args.check))

    if args.check:
        if all_changed:
            print("Prompt sync check failed; out-of-sync files:", file=sys.stderr)
            for path in all_changed:
                print(f"  - {path.relative_to(ROOT_DIR)}", file=sys.stderr)
            print("Run: python3 ./ci/sync_prompts.py", file=sys.stderr)
            return 1
        print("All kit prompts are in sync.")
        return 0

    if all_changed:
        print("Synchronized kit prompts into:")
        for path in all_changed:
            print(f"  - {path.relative_to(ROOT_DIR)}")
    else:
        print("All kit prompts already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
