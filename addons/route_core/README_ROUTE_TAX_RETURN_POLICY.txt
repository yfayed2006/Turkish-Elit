Route Core - Direct Return Pricelist Policy + Tax Display

Purpose
- Direct Return remains open and is NOT restricted by Reference Sale Order / Reference Delivery.
- Return price, discount, and taxes are calculated from the outlet/customer direct-sale pricelist.
- Reference Sale Order / Delivery is tracking only.
- Sale and Return mobile screens display Untaxed / Tax / Total Incl. Tax clearly.

Files to add / replace inside addons/route_core:
1) models/route_direct_return_pricelist_policy.py        NEW
2) models/__init__.py                                  REPLACE OR let the patch script update it
3) views/route_direct_return_tax_policy_views.xml      NEW
4) views/sale_order_direct_sale_tax_display_views.xml  NEW
5) apply_route_tax_return_policy_patch.py              TEMP helper script in module root

Recommended steps on Odoo.sh
1) Upload/copy the files into addons/route_core using the same paths above.
2) From addons/route_core, run:
   python3 apply_route_tax_return_policy_patch.py
3) Run:
   odoo-update route_core
4) Hard-refresh browser/mobile if old view cache remains.

Notes
- The helper script only inserts the two new XML files into __manifest__.py and appends the new model import.
- It also bumps the last manifest version number by 1.
- After the patch is applied successfully, you can delete apply_route_tax_return_policy_patch.py if desired.
