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

    def _get_packaging_qty_field_name(self, record):
        self.ensure_one()
        if not record:
            return False

        candidate_fields = (
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
        )
        for field_name in candidate_fields:
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_uom_field_name(self, record):
        self.ensure_one()
        if not record:
            return False

        candidate_fields = (
            "uom_id",
            "unit_id",
            "contained_uom_id",
            "product_uom_id",
        )
        for field_name in candidate_fields:
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

        qty = record[qty_field] or 0.0
        try:
            qty = float(qty)
        except Exception:
            qty = 0.0

        if qty_field == "factor" and qty:
            try:
                qty = 1.0 / qty
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


    def _record_matches_barcode(self, rec, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not rec or not barcode:
            return False

        direct_fields = ("barcode", "name")
        for field_name in direct_fields:
            try:
                if field_name in rec._fields and (rec[field_name] or "").strip() == barcode:
                    return True
            except Exception:
                continue

        for field_name, field in rec._fields.items():
            try:
                field_type = getattr(field, "type", None)
                if field_type not in ("one2many", "many2many"):
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

    def _record_has_packaging_signature(self, rec):
        self.ensure_one()
        if not rec:
            return False

        qty_field = self._get_packaging_qty_field_name(rec)
        has_qty = bool(qty_field)

        model_name = (getattr(rec, "_name", "") or "").lower()
        display_name = ""
        try:
            display_name = (rec.display_name or "").lower()
        except Exception:
            display_name = ""

        has_product = "product_id" in rec._fields and bool(rec.product_id)
        has_pack_hint = (
            "pack" in model_name
            or "packaging" in model_name
            or "box" in display_name
            or "pack" in display_name
            or "pcs" in display_name
            or "package_type_id" in rec._fields
            or "package_type" in rec._fields
        )
        has_barcode_relation = any(
            getattr(field, "type", None) in ("one2many", "many2many") and "barcode" in field_name
            for field_name, field in rec._fields.items()
        )

        if has_product and has_qty:
            return True
        if has_qty and (has_pack_hint or has_barcode_relation):
            return True
        return False

    def _iter_related_records(self, rec):
        self.ensure_one()
        if not rec:
            return []

        related_records = []
        for field_name, field in rec._fields.items():
            try:
                field_type = getattr(field, "type", None)
                if field_type not in ("many2one", "one2many", "many2many"):
                    continue

                value = rec[field_name]
                if not value:
                    continue

                if field_type == "many2one":
                    related_records.append(value)
                else:
                    related_records.extend(value)
            except Exception:
                continue

        return related_records

    def _find_product_specific_packaging(self, product, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not product or not barcode:
            return False

        candidates = []

        def _add_candidate(rec):
            if not rec or not getattr(rec, "id", False):
                return
            if rec in candidates:
                return
            try:
                if self._record_has_packaging_signature(rec):
                    candidates.append(rec)
            except Exception:
                return

        # product relations
        for target in self._iter_related_records(product):
            _add_candidate(target)
            try:
                for sub_target in self._iter_related_records(target):
                    _add_candidate(sub_target)
            except Exception:
                continue

        # template relations
        if getattr(product, "product_tmpl_id", False):
            tmpl = product.product_tmpl_id
            _add_candidate(tmpl)
            for target in self._iter_related_records(tmpl):
                _add_candidate(target)
                try:
                    for sub_target in self._iter_related_records(target):
                        _add_candidate(sub_target)
                except Exception:
                    continue

        for candidate in candidates:
            if self._record_matches_barcode(candidate, barcode):
                return candidate

        return False

    def _find_product_and_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False, False

        Product = self.env["product.product"]

        # First prefer products already present on the visit.
        visit_products = self.line_ids.mapped("product_id")
        for product in visit_products:
            packaging = self._find_product_specific_packaging(product, barcode)
            if packaging:
                return product, packaging

        # Then check all sellable/stockable products.
        products = Product.search([])
        for product in products:
            packaging = self._find_product_specific_packaging(product, barcode)
            if packaging:
                return product, packaging

        return False, False

    def _get_packaging_display_name(self, packaging, product=False, barcode=False):
        self.ensure_one()
        resolved = packaging
        barcode = (barcode or "").strip()

        if product and barcode:
            specific = self._find_product_specific_packaging(product, barcode)
            if specific:
                resolved = specific

        try:
            display_name = (resolved.display_name or "").strip() if resolved else ""
        except Exception:
            display_name = ""

        if display_name and not display_name.isdigit() and display_name != barcode:
            return display_name

        qty = self._get_packaging_qty(resolved)
        if qty <= 0 and product and barcode:
            specific = self._find_product_specific_packaging(product, barcode)
            qty = self._get_packaging_qty(specific) if specific else 0.0
            if specific:
                resolved = specific

        qty_label = int(qty) if qty and float(qty).is_integer() else qty
        if qty_label:
            return _("box %s") % qty_label

        if display_name and display_name != barcode:
            return display_name
        return _("Box")

    def _extract_packaging_from_record(self, rec):
        self.ensure_one()
        if not rec:
            return False

        if self._record_has_packaging_signature(rec):
            return rec

        for target in self._iter_related_records(rec):
            try:
                if self._record_has_packaging_signature(target):
                    return target
            except Exception:
                continue

        for target in self._iter_related_records(rec):
            try:
                for sub_target in self._iter_related_records(target):
                    try:
                        if self._record_has_packaging_signature(sub_target):
                            return sub_target
                    except Exception:
                        continue
            except Exception:
                continue

        return False

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        # Direct classic model search.
        if "product.packaging" in self.env:
            Packaging = self.env["product.packaging"]
            try:
                if "barcode" in Packaging._fields:
                    packaging = Packaging.search([("barcode", "=", barcode)], limit=1)
                    if packaging:
                        return packaging
            except Exception:
                pass
            try:
                for packaging in Packaging.search([]):
                    if self._record_matches_barcode(packaging, barcode):
                        return packaging
            except Exception:
                pass

        # Product-specific reverse lookup works for Odoo 19 units/packagings with barcode relations.
        product, packaging = self._find_product_and_packaging_by_barcode(barcode)
        if packaging:
            return packaging

        # Generic discovery through barcode models only as a weak fallback.
        try:
            for model_name in self.env:
                try:
                    Model = self.env[model_name]
                    if "barcode" not in Model._fields:
                        continue

                    rec = Model.search([("barcode", "=", barcode)], limit=1)
                    if not rec:
                        continue

                    extracted = self._extract_packaging_from_record(rec)
                    if extracted:
                        return extracted
                except Exception:
                    continue
        except Exception:
            pass

        return False

    def _find_route_product_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        if "route.product.barcode" not in self.env:
            return False

        Barcode = self.env["route.product.barcode"]

        domain = [("barcode", "=", barcode)]
        if "active" in Barcode._fields:
            domain.append(("active", "=", True))
        if "company_id" in Barcode._fields:
            domain.append(("company_id", "=", self.company_id.id))

        rec = Barcode.search(domain, limit=1)
        if rec:
            return rec

        domain = [("barcode", "=", barcode)]
        if "active" in Barcode._fields:
            domain.append(("active", "=", True))

        rec = Barcode.search(domain, limit=1)
        if rec:
            return rec

        rec = Barcode.search([("barcode", "=", barcode)], limit=1)
        if rec:
            return rec

        return False

    def _find_barcode_related_product(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        weak_fallback = False

        try:
            for model_name in self.env:
                try:
                    Model = self.env[model_name]
                    if "barcode" not in Model._fields:
                        continue

                    rec = Model.search([("barcode", "=", barcode)], limit=1)
                    if not rec:
                        continue

                    packaging = self._extract_packaging_from_record(rec)
                    if packaging and getattr(packaging, "product_id", False):
                        packaging_qty = self._get_packaging_qty(packaging) or 1.0
                        packaging_uom = (
                            self._get_packaging_uom(packaging, packaging.product_id)
                            or packaging.product_id.uom_id
                        )
                        return {
                            "product": packaging.product_id,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": packaging,
                            "default_scan_qty": packaging_qty,
                            "default_scanned_uom": packaging_uom,
                            "packaging_display_name": self._get_packaging_display_name(packaging, product=packaging.product_id, barcode=barcode),
                        }

                    if self._record_has_packaging_signature(rec) and "product_id" in rec._fields and rec.product_id:
                        qty = self._get_packaging_qty(rec) or 1.0
                        uom = self._get_packaging_uom(rec, rec.product_id) or rec.product_id.uom_id
                        return {
                            "product": rec.product_id,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": rec,
                            "default_scan_qty": qty,
                            "default_scanned_uom": uom,
                            "packaging_display_name": self._get_packaging_display_name(rec, product=rec.product_id, barcode=barcode),
                        }

                    if (
                        not weak_fallback
                        and "product_id" in Model._fields
                        and rec.product_id
                    ):
                        weak_fallback = {
                            "product": rec.product_id,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": rec,
                            "default_scan_qty": 1.0,
                            "default_scanned_uom": rec.product_id.uom_id,
                            "packaging_display_name": False,
                        }

                except Exception:
                    continue
        except Exception:
            pass

        return weak_fallback

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
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
                "packaging_display_name": False,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        packaging_product = getattr(packaging, "product_id", False) or False
        if packaging and not packaging_product:
            packaging_product, specific = self._find_product_and_packaging_by_barcode(barcode)
            if specific:
                packaging = specific
        if packaging and packaging_product:
            true_packaging = self._find_product_specific_packaging(packaging_product, barcode) or packaging
            packaging_qty = self._get_packaging_qty(true_packaging)
            if packaging_qty <= 0:
                packaging_qty = self._get_packaging_qty(packaging)
            if packaging_qty <= 0:
                packaging_qty = 1.0

            packaging_uom = self._get_packaging_uom(true_packaging, packaging_product)
            if not packaging_uom:
                packaging_uom = self._get_packaging_uom(packaging, packaging_product)
            if not packaging_uom:
                packaging_uom = packaging_product.uom_id

            return {
                "product": packaging_product,
                "scan_type": "box",
                "scan_type_label": _("Box Barcode"),
                "packaging": true_packaging,
                "packaging_display_name": self._get_packaging_display_name(true_packaging, product=packaging_product, barcode=barcode),
                "default_scan_qty": packaging_qty,
                "default_scanned_uom": packaging_uom,
            }

        generic = self._find_barcode_related_product(barcode)
        if generic:
            return generic

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = "piece"
            if "barcode_type" in route_barcode._fields and route_barcode.barcode_type:
                barcode_type = route_barcode.barcode_type

            qty_in_base_uom = 1.0
            if "qty_in_base_uom" in route_barcode._fields and route_barcode.qty_in_base_uom:
                qty_in_base_uom = route_barcode.qty_in_base_uom

            packaging = False
            packaging_display_name = False
            if barcode_type == "box":
                packaging = self._find_product_specific_packaging(route_barcode.product_id, barcode)
                packaging_display_name = self._get_packaging_display_name(packaging or route_barcode, product=route_barcode.product_id, barcode=barcode)
                if packaging:
                    qty_in_base_uom = self._get_packaging_qty(packaging) or qty_in_base_uom

            return {
                "product": route_barcode.product_id,
                "scan_type": barcode_type,
                "scan_type_label": _("Box Barcode" if barcode_type == "box" else "Piece Barcode"),
                "packaging": packaging or route_barcode,
                "packaging_display_name": packaging_display_name,
                "default_scan_qty": qty_in_base_uom,
                "default_scanned_uom": route_barcode.product_id.uom_id,
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

        raise UserError(
            _("Product '%s' has more than one available lot in stock. Please scan/select the lot first.")
            % product.display_name
        )

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

    def _process_scanned_barcode(
        self,
        barcode,
        scan_qty=1.0,
        scanned_uom=False,
        active_lot=False,
    ):
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
            raise UserError(
                _("Product '%s' is not currently available in the van stock.")
                % product.display_name
            )

        resolved_lot = self._resolve_product_active_lot(product, active_lot=active_lot)
        resolved_expiry_date = self._get_lot_expiry_date(resolved_lot) if resolved_lot else False

        line = self._find_visit_line_for_product(product)
        if line:
            line.write(
                {
                    "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                    "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
                }
            )
        else:
            line = RouteVisitLine.create([self._prepare_visit_line_from_scan(product, counted_increase)])

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
