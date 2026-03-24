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
            "inverse_factor",
            "ratio",
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

        for field_name in ("uom_id", "unit_id", "contained_uom_id", "product_uom_id"):
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_qty_from_name(self, record):
        self.ensure_one()
        if not record:
            return 0.0

        import re

        texts = []
        for attr in ("display_name", "name"):
            try:
                value = getattr(record, attr, False)
                if value:
                    texts.append(str(value))
            except Exception:
                continue

        for text in texts:
            matches = re.findall(r"(\d+(?:\.\d+)?)", text)
            if matches:
                try:
                    return float(matches[-1])
                except Exception:
                    continue
        return 0.0

    def _get_packaging_qty(self, record):
        self.ensure_one()
        if not record:
            return 0.0

        if getattr(record, "_name", "") == "uom.uom":
            try:
                if "factor_inv" in record._fields and record.factor_inv:
                    return record.factor_inv or 0.0
            except Exception:
                pass
            try:
                if "factor" in record._fields and record.factor:
                    factor = record.factor or 0.0
                    if factor:
                        return 1.0 / factor
            except Exception:
                pass

        qty_field = self._get_packaging_qty_field_name(record)
        if qty_field:
            try:
                value = record[qty_field] or 0.0
            except Exception:
                value = 0.0

            if qty_field in ("factor_inv", "inverse_factor"):
                if value:
                    return value
            elif qty_field == "factor":
                if value:
                    return 1.0 / value
            elif value:
                return value

        return self._get_packaging_qty_from_name(record)

    def _get_packaging_uom(self, record, product=False):
        self.ensure_one()
        if not record:
            return product.uom_id if product else False

        if getattr(record, "_name", "") == "uom.uom":
            return record

        uom_field = self._get_packaging_uom_field_name(record)
        if uom_field:
            try:
                if record[uom_field]:
                    return record[uom_field]
            except Exception:
                pass

        return product.uom_id if product else False

    def _get_packaging_product(self, record):
        self.ensure_one()
        if not record:
            return False

        for field_name in ("product_id", "product_variant_id"):
            if field_name in record._fields:
                try:
                    if record[field_name]:
                        return record[field_name]
                except Exception:
                    pass

        if "product_tmpl_id" in record._fields:
            try:
                tmpl = record.product_tmpl_id
                if tmpl:
                    if "product_variant_id" in tmpl._fields and tmpl.product_variant_id:
                        return tmpl.product_variant_id
                    if "product_variant_ids" in tmpl._fields and tmpl.product_variant_ids:
                        return tmpl.product_variant_ids[:1]
            except Exception:
                pass

        # Reverse lookup: find a product/product template that relates to this packaging record.
        for model_name in ("product.product", "product.template"):
            if model_name not in self.env:
                continue
            Model = self.env[model_name]
            for field_name, field in Model._fields.items():
                if getattr(field, "type", None) not in ("many2many", "one2many", "many2one"):
                    continue
                if getattr(field, "comodel_name", None) != record._name:
                    continue
                try:
                    if field.type == "many2one":
                        holder = Model.search([(field_name, "=", record.id)], limit=1)
                    else:
                        holder = Model.search([(field_name, "in", record.id)], limit=1)
                except Exception:
                    holder = False
                if not holder:
                    continue
                if model_name == "product.product":
                    return holder
                try:
                    if "product_variant_id" in holder._fields and holder.product_variant_id:
                        return holder.product_variant_id
                    if "product_variant_ids" in holder._fields and holder.product_variant_ids:
                        return holder.product_variant_ids[:1]
                except Exception:
                    continue

        return False

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

    def _get_packaging_display_name(self, packaging, product=False, barcode=False):
        self.ensure_one()
        if not packaging:
            return False

        # Avoid showing a pure numeric barcode-like name as the packaging label.
        for attr in ("display_name", "name"):
            try:
                value = getattr(packaging, attr, False)
            except Exception:
                value = False
            if not value:
                continue
            value = str(value).strip()
            if not value:
                continue
            if value == (barcode or "").strip() or value.isdigit():
                continue
            return value

        qty = self._get_packaging_qty(packaging)
        if qty:
            qty_txt = int(qty) if float(qty).is_integer() else qty
            return _("Box %s") % qty_txt
        if product:
            return _("Packaging for %s") % product.display_name
        return _("Packaging")

    def _build_packaging_scan_info(self, packaging, barcode=False):
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
        packaging_display_name = self._get_packaging_display_name(packaging, product=product, barcode=barcode)

        return {
            "product": product,
            "scan_type": "box",
            "scan_type_label": _("Box Barcode"),
            "packaging": packaging,
            "packaging_qty": packaging_qty,
            "packaging_display_name": packaging_display_name,
            # quantity entered by user = number of boxes
            "default_scan_qty": 1.0,
            "default_scanned_uom": product.uom_id,
        }

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        candidate_models = [m for m in ("product.packaging", "uom.uom") if m in self.env]
        for model_name in candidate_models:
            Model = self.env[model_name]

            # direct barcode field
            if "barcode" in Model._fields:
                try:
                    domain = [("barcode", "=", barcode)]
                    if "company_id" in Model._fields:
                        domain = [("barcode", "=", barcode), "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
                    rec = Model.search(domain, limit=1)
                    if rec:
                        return rec
                except Exception:
                    pass

            # relation-based barcodes (Odoo 19 Barcodes field)
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
            domain.extend(["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)])
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
                "packaging_qty": 1.0,
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        packaging_info = self._build_packaging_scan_info(packaging, barcode=barcode)
        if packaging_info:
            return packaging_info

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = (route_barcode.barcode_type or "piece") if "barcode_type" in route_barcode._fields else "piece"
            qty_in_base_uom = route_barcode.qty_in_base_uom or 1.0 if "qty_in_base_uom" in route_barcode._fields else 1.0
            if barcode_type == "box":
                # native Odoo packaging is still preferred; this is fallback only
                return {
                    "product": route_barcode.product_id,
                    "scan_type": "box",
                    "scan_type_label": _("Box Barcode"),
                    "packaging": route_barcode,
                    "packaging_qty": qty_in_base_uom,
                    "packaging_display_name": _("Box %s") % (int(qty_in_base_uom) if float(qty_in_base_uom).is_integer() else qty_in_base_uom),
                    "default_scan_qty": 1.0,
                    "default_scanned_uom": route_barcode.product_id.uom_id,
                }
            return {
                "product": route_barcode.product_id,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "packaging_qty": 1.0,
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
        packaging_qty = scan_info.get("packaging_qty") or 1.0

        if scan_info.get("scan_type") == "box":
            # scan_qty = number of boxes, packaging_qty = units per box
            effective_scan_qty = (scan_qty or 0.0) * packaging_qty
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
            "packaging_qty": packaging_qty,
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
