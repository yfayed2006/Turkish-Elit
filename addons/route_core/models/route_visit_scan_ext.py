from odoo import fields, models, _
from odoo.exceptions import UserError
import re


class RouteVisit(models.Model):
    _inherit = "route.visit"

    scan_barcode_input = fields.Char(string="Scan Barcode", copy=False)
    last_scanned_barcode = fields.Char(string="Last Scanned Barcode", readonly=True, copy=False)

    # ---------------------------
    # Stock / lot helpers
    # ---------------------------
    def _get_scan_source_location(self):
        self.ensure_one()
        return self.source_location_id or self.vehicle_id.stock_location_id

    def _get_scan_outlet_location(self):
        self.ensure_one()
        return self.outlet_id.stock_location_id

    def _get_scan_allowed_locations(self):
        self.ensure_one()
        locations = self.env["stock.location"]
        source_location = self._get_scan_source_location()
        outlet_location = self._get_scan_outlet_location()
        if source_location:
            locations |= source_location
        if outlet_location:
            locations |= outlet_location
        return locations

    def _get_lot_expiry_date(self, lot):
        self.ensure_one()
        if not lot:
            return False
        for field_name in ("expiration_date", "life_date", "use_date"):
            if field_name in lot._fields and lot[field_name]:
                return fields.Date.to_date(lot[field_name])
        return False

    def _find_available_lot_from_code(self, lot_code):
        self.ensure_one()
        lot_code = (lot_code or "").strip()
        if not lot_code:
            raise UserError(_("Please scan or enter a lot/serial code first."))

        allowed_locations = self._get_scan_allowed_locations()
        if not allowed_locations:
            raise UserError(_("No stock location is available for this visit."))

        Lot = self.env["stock.lot"]
        Quant = self.env["stock.quant"]

        lot = Lot.search([("name", "=", lot_code)], limit=1)
        if not lot and "barcode" in Lot._fields:
            lot = Lot.search([("barcode", "=", lot_code)], limit=1)

        if not lot:
            raise UserError(_("No lot/serial was found with code '%s'.") % lot_code)

        quant = Quant.search(
            [
                ("location_id", "child_of", allowed_locations.ids),
                ("lot_id", "=", lot.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        if not quant:
            raise UserError(
                _("Lot '%s' is not currently available in the van stock or outlet stock.")
                % lot.display_name
            )
        return lot

    def _find_available_lots_for_product(self, product):
        self.ensure_one()
        allowed_locations = self._get_scan_allowed_locations()
        if not allowed_locations or not product:
            return self.env["stock.lot"]

        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", allowed_locations.ids),
                ("product_id", "=", product.id),
                ("lot_id", "!=", False),
                ("quantity", ">", 0),
            ]
        )
        return quants.mapped("lot_id")

    # ---------------------------
    # Packaging helpers
    # ---------------------------
    def _get_packaging_qty_field_name(self, record):
        self.ensure_one()
        if not record:
            return False
        for field_name in (
            "qty",
            "quantity",
            "contained_qty",
            "contained_quantity",
            "contained_uom_qty",
            "product_qty",
            "pack_qty",
            "qty_per_pack",
            "unit_qty",
            "units",
            "units_count",
            "factor_inv",
            "factor",
        ):
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_uom_field_name(self, record):
        self.ensure_one()
        if not record:
            return False
        for field_name in ("uom_id", "unit_id", "contained_uom_id", "product_uom_id"):
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_qty(self, record):
        self.ensure_one()
        if not record:
            return 0.0

        qty_field = self._get_packaging_qty_field_name(record)
        if not qty_field:
            return 0.0

        try:
            qty = float(record[qty_field] or 0.0)
        except Exception:
            qty = 0.0

        if qty_field == "factor" and qty:
            try:
                qty = 1.0 / qty
            except Exception:
                qty = 0.0

        if qty <= 0:
            # fallback from name like "box 24" or "box (12 pcs)"
            label = ""
            for attr in ("display_name", "name"):
                try:
                    label = (getattr(record, attr, False) or "").strip()
                    if label:
                        break
                except Exception:
                    continue
            if label:
                match = re.search(r"(\d+(?:\.\d+)?)", label)
                if match:
                    try:
                        qty = float(match.group(1))
                    except Exception:
                        qty = 0.0
        return qty

    def _get_packaging_uom(self, record, product=False):
        self.ensure_one()
        if not record:
            return product.uom_id if product else False
        uom_field = self._get_packaging_uom_field_name(record)
        if uom_field and record[uom_field]:
            return record[uom_field]
        return product.uom_id if product else False

    def _get_record_label(self, rec):
        if not rec:
            return ""
        for attr in ("display_name", "name"):
            try:
                value = (getattr(rec, attr, False) or "").strip()
                if value:
                    return value
            except Exception:
                continue
        return ""

    def _is_numeric_only(self, text):
        text = (text or "").strip()
        if not text:
            return False
        return bool(re.fullmatch(r"\d+(?:\.\d+)?", text))

    def _record_has_packaging_signature(self, rec):
        self.ensure_one()
        if not rec:
            return False

        model_name = getattr(rec, "_name", "") or ""
        label = self._get_record_label(rec).lower()
        qty_field = self._get_packaging_qty_field_name(rec)
        has_qty = bool(qty_field)
        has_package_type = any(name in rec._fields for name in ("package_type_id", "package_type"))
        packagingish_name = (
            "pack" in model_name
            or "packaging" in model_name
            or model_name == "uom.uom"
            or "box" in label
            or "pack" in label
            or "pcs" in label
        )

        if self._is_numeric_only(label):
            return False

        if has_qty and (has_package_type or packagingish_name):
            return True

        if has_qty and ("product_id" in rec._fields or "product_tmpl_id" in rec._fields):
            return True

        return False

    def _iter_related_records(self, rec):
        self.ensure_one()
        related = []
        if not rec:
            return related
        for field_name, field in rec._fields.items():
            try:
                if getattr(field, "type", None) not in ("many2one", "one2many", "many2many"):
                    continue
                value = rec[field_name]
                if not value:
                    continue
                if getattr(field, "type", None) == "many2one":
                    related.append(value)
                else:
                    related.extend(value)
            except Exception:
                continue
        return related

    def _record_matches_barcode(self, rec, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not rec or not barcode:
            return False

        for field_name in ("barcode", "name"):
            try:
                if field_name in rec._fields and (rec[field_name] or "").strip() == barcode:
                    return True
            except Exception:
                continue

        for field_name, field in rec._fields.items():
            try:
                if getattr(field, "type", None) not in ("one2many", "many2many"):
                    continue
                if "barcode" not in field_name:
                    continue
                value = rec[field_name]
                if not value:
                    continue
                for item in value:
                    for attr in ("barcode", "name", "display_name"):
                        try:
                            candidate = (getattr(item, attr, False) or "").strip()
                            if candidate == barcode:
                                return True
                        except Exception:
                            continue
            except Exception:
                continue
        return False

    def _find_linked_product_for_packaging(self, packaging):
        self.ensure_one()
        if not packaging:
            return False

        if "product_id" in packaging._fields and packaging.product_id:
            return packaging.product_id
        if "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
            tmpl = packaging.product_tmpl_id
            if hasattr(tmpl, "product_variant_id") and tmpl.product_variant_id:
                return tmpl.product_variant_id
            if hasattr(tmpl, "product_variant_ids") and tmpl.product_variant_ids:
                return tmpl.product_variant_ids[:1]

        # search product.product relations directly to packaging model
        product = self.env["product.product"]
        for field_name, field in product._fields.items():
            try:
                if getattr(field, "comodel_name", False) != packaging._name:
                    continue
                if getattr(field, "type", None) == "many2one":
                    rec = product.search([(field_name, "=", packaging.id)], limit=1)
                else:
                    rec = product.search([(field_name, "in", packaging.id)], limit=1)
                if rec:
                    return rec
            except Exception:
                continue

        tmpl_model = self.env["product.template"]
        for field_name, field in tmpl_model._fields.items():
            try:
                if getattr(field, "comodel_name", False) != packaging._name:
                    continue
                if getattr(field, "type", None) == "many2one":
                    tmpl = tmpl_model.search([(field_name, "=", packaging.id)], limit=1)
                else:
                    tmpl = tmpl_model.search([(field_name, "in", packaging.id)], limit=1)
                if tmpl:
                    if hasattr(tmpl, "product_variant_id") and tmpl.product_variant_id:
                        return tmpl.product_variant_id
                    if hasattr(tmpl, "product_variant_ids") and tmpl.product_variant_ids:
                        return tmpl.product_variant_ids[:1]
            except Exception:
                continue
        return False

    def _find_uom_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode or "uom.uom" not in self.env:
            return False

        Uom = self.env["uom.uom"]

        # direct barcode on uom, if any
        if "barcode" in Uom._fields:
            try:
                rec = Uom.search([("barcode", "=", barcode)], limit=1)
                if rec and self._record_has_packaging_signature(rec):
                    return rec
            except Exception:
                pass

        # barcode relation on uom
        for field_name, field in Uom._fields.items():
            try:
                if getattr(field, "type", None) not in ("one2many", "many2many"):
                    continue
                if "barcode" not in field_name:
                    continue
                rel_model_name = getattr(field, "comodel_name", False)
                if not rel_model_name or rel_model_name not in self.env:
                    continue
                Rel = self.env[rel_model_name]

                rel_recs = self.env[rel_model_name]
                for rel_field in ("barcode", "name"):
                    if rel_field in Rel._fields:
                        rel_recs |= Rel.search([(rel_field, "=", barcode)])
                if not rel_recs:
                    continue

                candidates = Uom.search([(field_name, "in", rel_recs.ids)])
                for candidate in candidates:
                    if self._record_has_packaging_signature(candidate):
                        return candidate
            except Exception:
                continue
        return False

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        # classic product.packaging first
        if "product.packaging" in self.env:
            Packaging = self.env["product.packaging"]
            try:
                domain = [("barcode", "=", barcode)]
                if "company_id" in Packaging._fields:
                    domain = [("barcode", "=", barcode), "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
                rec = Packaging.search(domain, limit=1)
                if rec:
                    return rec
            except Exception:
                pass

            for field_name, field in Packaging._fields.items():
                try:
                    if getattr(field, "type", None) not in ("one2many", "many2many"):
                        continue
                    if "barcode" not in field_name:
                        continue
                    rel_model_name = getattr(field, "comodel_name", False)
                    if not rel_model_name or rel_model_name not in self.env:
                        continue
                    Rel = self.env[rel_model_name]
                    rel_recs = self.env[rel_model_name]
                    for rel_field in ("barcode", "name"):
                        if rel_field in Rel._fields:
                            rel_recs |= Rel.search([(rel_field, "=", barcode)])
                    if not rel_recs:
                        continue
                    rec = Packaging.search([(field_name, "in", rel_recs.ids)], limit=1)
                    if rec:
                        return rec
                except Exception:
                    continue

        # Odoo 19 style packaging on uom.uom
        uom_pack = self._find_uom_packaging_by_barcode(barcode)
        if uom_pack:
            return uom_pack

        return False

    def _get_packaging_display_name(self, packaging, product=False, barcode=False):
        self.ensure_one()
        barcode = (barcode or "").strip()
        label = self._get_record_label(packaging)
        if label and not self._is_numeric_only(label) and label != barcode:
            return label

        qty = self._get_packaging_qty(packaging)
        if qty > 0:
            qty_label = int(qty) if float(qty).is_integer() else qty
            return _("box %s") % qty_label

        if label:
            return label
        if barcode:
            return barcode
        return False

    def _find_route_product_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode or "route.product.barcode" not in self.env:
            return False
        Barcode = self.env["route.product.barcode"]
        domain = [("barcode", "=", barcode)]
        if "active" in Barcode._fields:
            domain.append(("active", "=", True))
        if "company_id" in Barcode._fields:
            domain = [("barcode", "=", barcode)] + ([('active', '=', True)] if 'active' in Barcode._fields else []) + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
        return Barcode.search(domain, limit=1)

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        # 1) Direct product barcode
        product = self.env["product.product"].search([("barcode", "=", barcode)], limit=1)
        if product:
            return {
                "product": product,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        # 2) Real Odoo packaging first (classic or Odoo19 uom packaging)
        packaging = self._find_product_packaging_by_barcode(barcode)
        if packaging:
            packaging_product = self._find_linked_product_for_packaging(packaging)
            if packaging_product:
                packaging_qty = self._get_packaging_qty(packaging)
                if packaging_qty <= 0:
                    raise UserError(_("Packaging '%s' has no valid quantity configured.") % self._get_packaging_display_name(packaging, product=packaging_product, barcode=barcode))
                packaging_uom = self._get_packaging_uom(packaging, packaging_product) or packaging_product.uom_id
                return {
                    "product": packaging_product,
                    "scan_type": "box",
                    "scan_type_label": _("Box Barcode"),
                    "packaging": packaging,
                    "packaging_display_name": self._get_packaging_display_name(packaging, product=packaging_product, barcode=barcode),
                    "default_scan_qty": packaging_qty,
                    "default_scanned_uom": packaging_uom,
                }

        # 3) Route barcode only as fallback; for box require real packaging
        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = route_barcode.barcode_type if "barcode_type" in route_barcode._fields and route_barcode.barcode_type else "piece"
            if barcode_type == "box":
                raise UserError(
                    _("Box barcode '%(barcode)s' must be configured on the original Odoo Packaging / Packagings of the product, not only on route.product.barcode.")
                    % {"barcode": barcode}
                )
            return {
                "product": route_barcode.product_id,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": route_barcode.product_id.uom_id,
            }

        raise UserError(_("No product was found with barcode '%s'.") % barcode)

    # ---------------------------
    # Scan processing
    # ---------------------------
    def _is_product_tracked_by_lot(self, product):
        self.ensure_one()
        tracking_value = getattr(product, "tracking", "none") or "none"
        return bool(product) and tracking_value in ("lot", "serial")

    def _resolve_product_active_lot(self, product, active_lot=False):
        self.ensure_one()
        if not product:
            return False
        if not self._is_product_tracked_by_lot(product):
            return False
        if active_lot:
            if active_lot.product_id != product:
                raise UserError(
                    _(
                        "The scanned product does not belong to the active lot.\n\n"
                        "Active Lot: %(lot)s\n"
                        "Lot Product: %(lot_product)s\n"
                        "Scanned Product: %(barcode_product)s\n\n"
                        "Please clear the current lot first, then scan/select the correct lot for this product."
                    )
                    % {
                        "lot": active_lot.display_name,
                        "lot_product": active_lot.product_id.display_name,
                        "barcode_product": product.display_name,
                    }
                )
            return active_lot

        available_lots = self._find_available_lots_for_product(product)
        if not available_lots:
            raise UserError(_("Tracked product '%s' has no available lot in the van stock or outlet stock.") % product.display_name)
        if len(available_lots) == 1:
            return available_lots[:1]
        raise UserError(_("Product '%s' has more than one available lot in stock. Please scan/select the lot first.") % product.display_name)

    def _is_product_available_in_vehicle(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return False
        quant = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        return bool(quant)

    def _get_vehicle_available_qty_for_scan_product(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return 0.0
        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
            ]
        )
        return sum(quants.mapped("quantity"))

    def _find_visit_line_for_product(self, product):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.product_id == product)[:1]

    def _prepare_visit_line_from_scan(self, product, counted_increase):
        self.ensure_one()
        return {
            "visit_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "previous_qty": 0.0,
            "counted_qty": counted_increase,
            "unit_price": product.lst_price or 0.0,
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
        }

    def _get_scan_counted_increase(self, product, scan_qty=1.0, scanned_uom=False):
        self.ensure_one()
        if not product:
            raise UserError(_("Product is required."))
        if scan_qty <= 0:
            raise UserError(_("Quantity must be greater than zero."))
        base_uom = product.uom_id
        scanned_uom = scanned_uom or base_uom
        try:
            return scanned_uom._compute_quantity(scan_qty, base_uom)
        except Exception as e:
            raise UserError(
                _("Could not convert the scanned quantity from the selected UoM to the product base UoM.\n\n%s")
                % str(e)
            )

    def _process_scanned_barcode(self, barcode, scan_qty=1.0, scanned_uom=False, active_lot=False):
        self.ensure_one()
        RouteVisitLine = self.env["route.visit.line"]

        if self.visit_process_state not in ("checked_in", "counting", "reconciled"):
            raise UserError(_("Barcode scanning is only allowed when the visit is Checked In, Counting, or Reconciled."))
        if not self.vehicle_id:
            raise UserError(_("Please set a vehicle before scanning."))
        if not self.vehicle_id.stock_location_id:
            raise UserError(_("The selected vehicle does not have a Vehicle Stock Location."))

        self._sync_source_location_from_vehicle()
        if not self.source_location_id:
            raise UserError(_("No source location is available for this visit."))

        scan_info = self._resolve_scanned_barcode(barcode)
        product = scan_info["product"]

        effective_scan_qty = scan_qty
        effective_scanned_uom = scanned_uom or scan_info.get("default_scanned_uom")
        if scan_info.get("scan_type") == "box":
            effective_scan_qty = scan_info.get("default_scan_qty") or 1.0
            effective_scanned_uom = product.uom_id

        counted_increase = self._get_scan_counted_increase(
            product,
            scan_qty=effective_scan_qty,
            scanned_uom=effective_scanned_uom,
        )

        if not self._is_product_available_in_vehicle(product):
            raise UserError(_("Product '%s' is not currently available in the van stock.") % product.display_name)

        resolved_lot = self._resolve_product_active_lot(product, active_lot=active_lot)
        resolved_expiry_date = self._get_lot_expiry_date(resolved_lot) if resolved_lot else False

        line = self._find_visit_line_for_product(product)
        if line:
            line.write({
                "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
            })
        else:
            line = RouteVisitLine.create([self._prepare_visit_line_from_scan(product, counted_increase)])

        self.last_scanned_barcode = barcode
        if self.visit_process_state == "checked_in":
            self.visit_process_state = "counting"

        return {
            "line": line,
            "product": product,
            "scan_type": scan_info["scan_type"],
            "scan_type_label": scan_info["scan_type_label"],
            "counted_increase": counted_increase,
            "base_uom": product.uom_id,
            "used_uom": effective_scanned_uom or product.uom_id,
            "resolved_lot": resolved_lot,
            "resolved_expiry_date": resolved_expiry_date,
            "packaging": scan_info.get("packaging"),
            "packaging_display_name": scan_info.get("packaging_display_name"),
            "effective_scan_qty": effective_scan_qty,
        }

    def action_scan_barcode_input(self):
        for rec in self:
            rec._process_scanned_barcode(rec.scan_barcode_input, scan_qty=1.0)
            rec.scan_barcode_input = False
        return True

    def action_open_scan_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_quantity": 1.0,
                "default_scan_mode": "count",
            },
        }
