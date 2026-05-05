#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent

manifest_path = ROOT / "__manifest__.py"
models_init_path = ROOT / "models" / "__init__.py"

insertions = [
    (
        '        "views/route_direct_return_views.xml",',
        '        "views/route_direct_return_tax_policy_views.xml",',
    ),
    (
        '        "views/sale_order_direct_sale_views.xml",',
        '        "views/sale_order_direct_sale_tax_display_views.xml",',
    ),
]

if not manifest_path.exists():
    raise SystemExit("Run this script from addons/route_core. __manifest__.py was not found.")

manifest = manifest_path.read_text(encoding="utf-8")
for anchor, new_line in insertions:
    if new_line.strip() not in manifest:
        if anchor not in manifest:
            raise SystemExit(f"Could not find manifest anchor: {anchor.strip()}")
        manifest = manifest.replace(anchor, anchor + "\n" + new_line, 1)

version_match = re.search(r'("version"\s*:\s*")([0-9]+(?:\.[0-9]+)+)(")', manifest)
if version_match:
    version_parts = version_match.group(2).split(".")
    try:
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version = ".".join(version_parts)
        manifest = manifest[:version_match.start(2)] + new_version + manifest[version_match.end(2):]
    except Exception:
        pass

manifest_path.write_text(manifest, encoding="utf-8")
print("Updated __manifest__.py")

if not models_init_path.exists():
    raise SystemExit("models/__init__.py was not found.")
models_init = models_init_path.read_text(encoding="utf-8")
import_line = "from . import route_direct_return_pricelist_policy"
if import_line not in models_init:
    if not models_init.endswith("\n"):
        models_init += "\n"
    models_init += import_line + "\n"
    models_init_path.write_text(models_init, encoding="utf-8")
    print("Updated models/__init__.py")
else:
    print("models/__init__.py already contains the policy import")

print("Patch applied. Now run: odoo-update route_core")
