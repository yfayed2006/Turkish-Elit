from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    scan_barcode_input = fields.Char(
        string="Scan Barcode",
        copy=False,
    )
    last_scanned_barcode = fields.Char(
        string="Last Scanned Barcode",
        readonly=True,
        copy=False,
    )

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

    def _is_route_lot_workflow_enabled(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if "route_enable_lot_serial_tracking" not in company._fields:
            return True
        return bool(company.route_enable_lot_serial_tracking)

    def _is_route_expiry_workflow_enabled(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if not self._is_route_lot_workflow_enabled():
            return False
        if "route_enable_expiry_tracking" not in company._fields:
            return True
        return bool(company.route_enable_expiry_tracking)

    def _get_lot_expiry_date(self, lot):
        self.ensure_one()
        if not lot:
            return False
        # Prefer the earliest operational lot date that should drive field decisions.
        # removal_date is used first so already-removal lots are treated as expired
        # even when the final expiration_date is later.
        for field_name in ("removal_date", "expiration_date", "life_date", "use_date"):
            if field_name in lot._fields and lot[field_name]:
                return fields.Date.to_date(lot[field_name])
        return False

    def _find_available_lot_from_code(self, lot_code):
        self.ensure_one()
        if not self._is_route_lot_workflow_enabled():
            return False
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
        if not self._is_route_lot_workflow_enabled():
            return self.env["stock.lot"]
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

    # ---------------------------------------------------------
    # Packaging helpers
    # ---------------------------------------------------------
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

    def _get_packaging_qty(self, record):
        self.ensure_one()
        if not record:
            return 0.0

        # product.packaging usually stores the exact contained qty directly.
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
        ):
            if field_name in record._fields:
                value = record[field_name] or 0.0
                if value and value > 0:
                    return float(value)

        # Odoo 19 packaging may be stored on uom.uom. In that case factor/factor_inv
        # can be stored in either direction, so normalize to the larger meaningful qty.
        if getattr(record, "_name", "") == "uom.uom":
            candidates = []
            if "factor_inv" in record._fields:
                value = record["factor_inv"] or 0.0
                if value and value > 0:
                    candidates.append(float(value))
                    if value < 1:
                        candidates.append(1.0 / float(value))
            if "factor" in record._fields:
                value = record["factor"] or 0.0
                if value and value > 0:
                    candidates.append(float(value))
                    if value < 1:
                        candidates.append(1.0 / float(value))
            candidates = [v for v in candidates if v and v > 0]
            if candidates:
                meaningful = [v for v in candidates if v > 1]
                return max(meaningful or candidates)

        if "factor_inv" in record._fields:
            value = record["factor_inv"] or 0.0
            if value and value > 0:
                return float(value)

        if "factor" in record._fields:
            factor = record["factor"] or 0.0
            if factor and factor > 0:
                if factor < 1:
                    return 1.0 / factor
                return float(factor)

        # Last fallback: read number from packaging name like "box 24".
        display_name = self._get_packaging_display_name(record)
        digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in (display_name or ""))
        for token in digits.split():
            try:
                value = float(token)
            except Exception:
                continue
            if value > 1:
                return value
        return 0.0

    def _get_packaging_display_name(self, record):
        self.ensure_one()
        if not record:
            return False

        for field_name in ("name", "display_name"):
            if field_name in record._fields and record[field_name]:
                name = str(record[field_name]).strip()
                if name and not name.replace(".", "", 1).isdigit():
                    return name

        qty = self._get_packaging_qty(record)
        if qty > 0:
            qty_label = int(qty) if float(qty).is_integer() else qty
            package_type = False
            for field_name in ("package_type_id", "package_type"):
                if field_name in record._fields and record[field_name]:
                    val = record[field_name]
                    package_type = getattr(val, "display_name", False) or getattr(val, "name", False) or str(val)
                    break
            if package_type:
                return "%s %s" % (package_type, qty_label)
            return "Box %s" % qty_label

        return getattr(record, "display_name", False) or False

    def _record_matches_barcode(self, record, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not record or not barcode:
            return False

        # direct char barcode fields on record
        for field_name, field in record._fields.items():
            try:
                if getattr(field, "type", None) == "char" and "barcode" in field_name:
                    if (record[field_name] or "").strip() == barcode:
                        return True
            except Exception:
                continue

        # barcode relations like "barcodes"
        for field_name, field in record._fields.items():
            try:
                field_type = getattr(field, "type", None)
                if field_type not in ("one2many", "many2many"):
                    continue
                if "barcode" not in field_name and "barcode" not in (getattr(field, "comodel_name", "") or ""):
                    continue

                for child in record[field_name]:
                    for child_field_name, child_field in child._fields.items():
                        try:
                            if getattr(child_field, "type", None) != "char":
                                continue
                            if child_field_name not in ("name", "code") and "barcode" not in child_field_name:
                                continue
                            if (child[child_field_name] or "").strip() == barcode:
                                return True
                        except Exception:
                            continue
            except Exception:
                continue
        return False

    def _is_packaging_candidate(self, record):
        self.ensure_one()
        if not record:
            return False
        model_name = getattr(record, "_name", "") or ""
        if model_name == "product.packaging":
            return True
        if model_name == "uom.uom":
            if "package_type_id" in record._fields and record.package_type_id:
                return True
            name = ((getattr(record, "name", False) or getattr(record, "display_name", False) or "").lower())
            return any(token in name for token in ("box", "pack", "pcs", "piece"))
        return False

    def _find_products_linked_to_record(self, record):
        self.ensure_one()
        Product = self.env["product.product"]
        Template = self.env["product.template"]
        products = Product
        if not record:
            return products

        if "product_id" in record._fields and record.product_id:
            return record.product_id
        if "product_tmpl_id" in record._fields and record.product_tmpl_id:
            return record.product_tmpl_id.product_variant_ids[:1]

        for Model in (Product, Template):
            for field_name, field in Model._fields.items():
                try:
                    field_type = getattr(field, "type", None)
                    comodel_name = getattr(field, "comodel_name", None)
                    if comodel_name != record._name or field_type not in ("many2one", "many2many", "one2many"):
                        continue

                    found = Model.search([(field_name, "in", record.ids)], limit=1)
                    if found:
                        if Model._name == "product.template":
                            return found.product_variant_ids[:1]
                        return found[:1]
                except Exception:
                    continue
        return products

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        for model_name in ("product.packaging", "uom.uom"):
            if model_name not in self.env:
                continue
            Model = self.env[model_name]

            # direct barcode fields first
            for field_name, field in Model._fields.items():
                try:
                    if getattr(field, "type", None) != "char" or "barcode" not in field_name:
                        continue
                    rec = Model.search([(field_name, "=", barcode)], limit=1)
                    if rec and self._is_packaging_candidate(rec):
                        return rec
                except Exception:
                    continue

            # then relation-based barcodes
            try:
                for rec in Model.search([]):
                    if self._is_packaging_candidate(rec) and self._record_matches_barcode(rec, barcode):
                        return rec
            except Exception:
                continue

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
        rec = Barcode.search(domain, limit=1)
        return rec or False

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        product = self.env["product.product"].search([("barcode", "=", barcode)], limit=1)
        if product:
            return {
                "product": product,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "box_qty": 1.0,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        if packaging:
            packaging_product = self._find_products_linked_to_record(packaging)
            packaging_qty = self._get_packaging_qty(packaging)
            if packaging_product and packaging_qty > 0:
                product = packaging_product[:1]
                return {
                    "product": product,
                    "scan_type": "box",
                    "scan_type_label": _("Box Barcode"),
                    "packaging": packaging,
                    "box_qty": packaging_qty,
                    "default_scan_qty": 1.0,
                    "default_scanned_uom": product.uom_id,
                    "packaging_display_name": self._get_packaging_display_name(packaging),
                }

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = route_barcode.barcode_type if "barcode_type" in route_barcode._fields and route_barcode.barcode_type else "piece"
            qty_in_base_uom = route_barcode.qty_in_base_uom if "qty_in_base_uom" in route_barcode._fields and route_barcode.qty_in_base_uom else 1.0
            return {
                "product": route_barcode.product_id,
                "scan_type": barcode_type,
                "scan_type_label": _("Box Barcode" if barcode_type == "box" else "Piece Barcode"),
                "packaging": route_barcode,
                "box_qty": qty_in_base_uom if barcode_type == "box" else 1.0,
                "default_scan_qty": 1.0,
                "default_scanned_uom": route_barcode.product_id.uom_id,
                "packaging_display_name": self._get_packaging_display_name(route_barcode) if barcode_type == "box" else False,
            }

        raise UserError(_("No product was found with barcode '%s'.") % barcode)

    def _is_product_tracked_by_lot(self, product):
        self.ensure_one()
        if not product:
            return False
        tracking_value = getattr(product, "tracking", "none") or "none"
        return tracking_value in ("lot", "serial")

    def _resolve_product_active_lot(self, product, active_lot=False):
        self.ensure_one()
        if not product:
            return False

        if not self._is_route_lot_workflow_enabled():
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
            raise UserError(
                _("Tracked product '%s' has no available lot in the van stock or outlet stock.")
                % product.display_name
            )

        if len(available_lots) == 1:
            return available_lots[:1]

        lot_names = ", ".join(available_lots[:5].mapped("display_name"))
        more_text = _(" and more") if len(available_lots) > 5 else ""
        raise UserError(
            _(
                "Product '%(product)s' is tracked by Lot/Serial and has more than one available lot.\n\n"
                "Available lots: %(lots)s%(more)s\n\n"
                "Please scan or select the correct lot first, then scan the product barcode again."
            )
            % {"product": product.display_name, "lots": lot_names, "more": more_text}
        )

    def _is_product_available_in_vehicle(self, product):
        self.ensure_one()
        if not product:
            return False

        # Allow rescanning products already present on the visit lines.
        if self._find_visit_line_for_product(product):
            return True

        # During shelf count, availability can come from either the van stock
        # or the current outlet stock.
        allowed_locations = self._get_scan_allowed_locations()
        if not allowed_locations:
            return False

        quant = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", allowed_locations.ids),
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

    def _get_outlet_available_qty_for_product_lot(self, product, lot):
        self.ensure_one()
        outlet_location = self._get_scan_outlet_location()
        if not outlet_location or not product or not lot:
            return 0.0
        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", outlet_location.id),
            ("product_id", "=", product.id),
            ("lot_id", "=", lot.id),
        ])
        return sum(quants.mapped("quantity"))

    def _find_visit_line_for_product(self, product, lot=False):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.product_id == product)
        if not lines:
            return self.env["route.visit.line"]
        if lot and "lot_id" in self.env["route.visit.line"]._fields:
            exact = lines.filtered(lambda l: l.lot_id == lot)[:1]
            if exact:
                return exact
            return lines.filtered(lambda l: not l.lot_id)[:1]
        return lines.filtered(lambda l: not l.lot_id)[:1] or lines[:1]

    def _prepare_visit_line_from_scan(self, product, counted_increase, resolved_lot=False, resolved_expiry_date=False, previous_qty=0.0):
        self.ensure_one()
        vals = {
            "visit_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "previous_qty": previous_qty or 0.0,
            "counted_qty": counted_increase,
            "unit_price": product.lst_price or 0.0,
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
        }
        if resolved_lot and "lot_id" in self.env["route.visit.line"]._fields:
            vals["lot_id"] = resolved_lot.id
        if resolved_expiry_date:
            vals["expiry_date"] = resolved_expiry_date
        return vals

    def _get_or_create_visit_line_for_product_and_lot(self, product, resolved_lot=False, resolved_expiry_date=False, counted_increase=0.0):
        self.ensure_one()
        RouteVisitLine = self.env["route.visit.line"]

        if not resolved_lot or "lot_id" not in RouteVisitLine._fields:
            line = self._find_visit_line_for_product(product)
            if line:
                return line
            return RouteVisitLine.create([self._prepare_visit_line_from_scan(product, counted_increase)])

        exact_line = self.line_ids.filtered(
            lambda l: l.product_id == product and l.lot_id == resolved_lot
        )[:1]
        if exact_line:
            return exact_line

        unassigned_line = self.line_ids.filtered(
            lambda l: l.product_id == product
            and not l.lot_id
            and (l.counted_qty or 0.0) <= 0
            and (l.return_qty or 0.0) <= 0
            and (l.supplied_qty or 0.0) <= 0
        )[:1]

        lot_previous_qty = self._get_outlet_available_qty_for_product_lot(product, resolved_lot)

        if unassigned_line:
            original_previous_qty = unassigned_line.previous_qty or 0.0
            remainder_previous_qty = max(original_previous_qty - lot_previous_qty, 0.0)

            unassigned_line.write({
                "lot_id": resolved_lot.id,
                "previous_qty": lot_previous_qty,
                "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
                "expiry_date": resolved_expiry_date or unassigned_line.expiry_date,
            })

            if remainder_previous_qty > 0:
                RouteVisitLine.create({
                    "visit_id": self.id,
                    "company_id": self.company_id.id,
                    "product_id": product.id,
                    "previous_qty": remainder_previous_qty,
                    "counted_qty": 0.0,
                    "unit_price": unassigned_line.unit_price or product.lst_price or 0.0,
                    "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
                    "return_route": unassigned_line.return_route or "vehicle",
                })

            return unassigned_line

        return RouteVisitLine.create([
            self._prepare_visit_line_from_scan(
                product,
                counted_increase,
                resolved_lot=resolved_lot,
                resolved_expiry_date=resolved_expiry_date,
                previous_qty=lot_previous_qty,
            )
        ])

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
            raise UserError(
                _("Barcode scanning is only allowed when the visit is Checked In, Counting, or Reconciled.")
            )

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
        effective_scanned_uom = scanned_uom or scan_info.get("default_scanned_uom") or product.uom_id

        if scan_info.get("scan_type") == "box":
            effective_scan_qty = (scan_qty or 0.0) * (scan_info.get("box_qty") or 1.0)
            effective_scanned_uom = product.uom_id

        counted_increase = self._get_scan_counted_increase(
            product,
            scan_qty=effective_scan_qty,
            scanned_uom=effective_scanned_uom,
        )

        if not self._is_product_available_in_vehicle(product):
            raise UserError(
                _("Product '%s' is not currently available in the van stock or current outlet stock.")
                % product.display_name
            )

        resolved_lot = self._resolve_product_active_lot(product, active_lot=active_lot)
        resolved_expiry_date = self._get_lot_expiry_date(resolved_lot) if (resolved_lot and self._is_route_expiry_workflow_enabled()) else False

        line = self._get_or_create_visit_line_for_product_and_lot(
            product,
            resolved_lot=resolved_lot,
            resolved_expiry_date=resolved_expiry_date,
            counted_increase=counted_increase,
        )
        if line:
            update_vals = {
                "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
            }
            if resolved_lot and "lot_id" in line._fields and not line.lot_id:
                update_vals["lot_id"] = resolved_lot.id
            if resolved_expiry_date and not line.expiry_date:
                update_vals["expiry_date"] = resolved_expiry_date
            line.write(update_vals)
        else:
            line = RouteVisitLine.create([
                self._prepare_visit_line_from_scan(
                    product,
                    counted_increase,
                    resolved_lot=resolved_lot,
                    resolved_expiry_date=resolved_expiry_date,
                    previous_qty=self._get_outlet_available_qty_for_product_lot(product, resolved_lot),
                )
            ])

        self.last_scanned_barcode = (barcode or "").strip()
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
        if getattr(self, "_is_direct_sales_stop", False) and self._is_direct_sales_stop():
            raise UserError(_("Shelf counting is not used for Direct Sales stops."))
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
                "default_focus_target": "lot" if self._is_route_lot_workflow_enabled() else "product",
            },
        }



