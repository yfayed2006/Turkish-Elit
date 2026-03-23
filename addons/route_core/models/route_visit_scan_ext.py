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
        return record[qty_field] or 0.0

    def _get_packaging_uom(self, record, product=False):
        self.ensure_one()
        if not record:
            return product.uom_id if product else False

        uom_field = self._get_packaging_uom_field_name(record)
        if uom_field and record[uom_field]:
            return record[uom_field]

        return product.uom_id if product else False

    def _get_packaging_product(self, record):
        self.ensure_one()
        if not record:
            return False

        for field_name in ("product_id", "product_variant_id"):
            if field_name in record._fields and record[field_name]:
                return record[field_name]

        if "product_tmpl_id" in record._fields and record.product_tmpl_id:
            template = record.product_tmpl_id
            if "product_variant_id" in template._fields and template.product_variant_id:
                return template.product_variant_id
            if "product_variant_ids" in template._fields and template.product_variant_ids:
                return template.product_variant_ids[:1]

        for model_name in ("product.product", "product.template"):
            if model_name not in self.env:
                continue
            Model = self.env[model_name]
            for field_name, field in Model._fields.items():
                if getattr(field, "type", None) not in ("one2many", "many2many"):
                    continue
                if getattr(field, "comodel_name", None) != record._name:
                    continue
                try:
                    holder = Model.search([(field_name, "in", record.id)], limit=1)
                except Exception:
                    holder = False
                if not holder:
                    continue
                if model_name == "product.product":
                    return holder
                if "product_variant_id" in holder._fields and holder.product_variant_id:
                    return holder.product_variant_id
                if "product_variant_ids" in holder._fields and holder.product_variant_ids:
                    return holder.product_variant_ids[:1]

        return False

    def _get_packaging_display_name(self, record):
        self.ensure_one()
        if not record:
            return False

        for field_name in ("display_name", "name", "unit_name"):
            if field_name in record._fields:
                try:
                    value = record[field_name]
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                except Exception:
                    continue

        qty = self._get_packaging_qty(record) or 0.0
        product = self._get_packaging_product(record)
        base_uom = product.uom_id.display_name if product and product.uom_id else _("Units")
        if qty > 0:
            if float(qty).is_integer():
                qty_text = str(int(qty))
            else:
                qty_text = str(qty)
            return _("Box %(qty)s %(uom)s") % {"qty": qty_text, "uom": base_uom}
        return _("Box")

    def _record_has_packaging_signature(self, rec):
        self.ensure_one()
        if not rec:
            return False

        has_product = bool(self._get_packaging_product(rec))
        has_qty = bool(self._get_packaging_qty_field_name(rec))
        if has_product and has_qty:
            return True

        model_name = (getattr(rec, "_name", "") or "").lower()
        display_name = ""
        try:
            display_name = (rec.display_name or "").lower()
        except Exception:
            display_name = ""

        return has_product and (
            "pack" in model_name
            or "packaging" in model_name
            or "pack" in display_name
            or "pcs" in display_name
            or "box" in display_name
        )

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

    def _record_matches_barcode_value(self, rec, barcode):
        self.ensure_one()
        if not rec:
            return False

        barcode = (barcode or "").strip()
        if not barcode:
            return False

        simple_fields = ("barcode", "name", "code", "value")
        for field_name in simple_fields:
            if field_name not in rec._fields:
                continue
            try:
                value = rec[field_name]
                if isinstance(value, str) and value.strip() == barcode:
                    return True
            except Exception:
                continue

        for field_name, field in rec._fields.items():
            if getattr(field, "type", None) not in ("one2many", "many2many"):
                continue
            try:
                children = rec[field_name]
            except Exception:
                continue
            if not children:
                continue
            for child in children:
                for child_field in simple_fields:
                    if child_field not in child._fields:
                        continue
                    try:
                        value = child[child_field]
                        if isinstance(value, str) and value.strip() == barcode:
                            return True
                    except Exception:
                        continue
        return False

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

    def _build_packaging_scan_info(self, packaging):
        self.ensure_one()
        if not packaging:
            return False

        product = self._get_packaging_product(packaging)
        if not product:
            return False

        packaging_qty = self._get_packaging_qty(packaging) or 0.0
        if packaging_qty <= 0:
            packaging_qty = 1.0

        packaging_uom = self._get_packaging_uom(packaging, product) or product.uom_id

        return {
            "product": product,
            "scan_type": "box",
            "scan_type_label": _("Box Barcode"),
            "packaging": packaging,
            "packaging_display_name": self._get_packaging_display_name(packaging),
            "default_scan_qty": packaging_qty,
            "default_scanned_uom": packaging_uom,
        }

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        for model_name in ("product.packaging", "uom.uom"):
            if model_name not in self.env:
                continue
            Model = self.env[model_name]

            if "barcode" in Model._fields:
                try:
                    rec = Model.search([("barcode", "=", barcode)], limit=1)
                    if rec:
                        return rec
                except Exception:
                    pass

            try:
                records = Model.search([])
            except Exception:
                records = self.env[model_name]

            for rec in records:
                try:
                    if self._record_matches_barcode_value(rec, barcode):
                        return rec
                except Exception:
                    continue

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
            domain.append(("company_id", "in", [False, self.company_id.id]))
        return Barcode.search(domain, limit=1)

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
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        packaging_info = self._build_packaging_scan_info(packaging)
        if packaging_info:
            return packaging_info

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = "piece"
            if "barcode_type" in route_barcode._fields and route_barcode.barcode_type:
                barcode_type = route_barcode.barcode_type

            if barcode_type == "box":
                raise UserError(
                    _(
                        "Barcode '%(barcode)s' is marked as a box barcode in Route Product Barcode, "
                        "but no matching Odoo packaging was found for it. Please define this box barcode on the product packaging itself."
                    )
                    % {"barcode": barcode}
                )

            qty_in_base_uom = 1.0
            if "qty_in_base_uom" in route_barcode._fields and route_barcode.qty_in_base_uom:
                qty_in_base_uom = route_barcode.qty_in_base_uom

            return {
                "product": route_barcode.product_id,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "packaging_display_name": False,
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
                        "The scanned product does not belong to the active lot.

"
                        "Active Lot: %(lot)s
"
                        "Lot Product: %(lot_product)s
"
                        "Scanned Product: %(barcode_product)s

"
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
                _("Could not convert the scanned quantity from the selected UoM to the product base UoM.

%s")
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
