from odoo import fields, models, _
from odoo.exceptions import UserError
import re


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

    def _get_packaging_qty_from_name(self, record):
        self.ensure_one()
        if not record:
            return 0.0
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
        if uom_field and record[uom_field]:
            return record[uom_field]

        return product.uom_id if product else False

    def _get_packaging_display_name(self, packaging, product=False):
        self.ensure_one()
        if not packaging:
            return False
        for attr in ("display_name", "name"):
            try:
                value = getattr(packaging, attr, False)
                if value:
                    return value
            except Exception:
                continue
        qty = self._get_packaging_qty(packaging)
        if qty:
            try:
                qty_txt = int(qty) if float(qty).is_integer() else qty
            except Exception:
                qty_txt = qty
            return _("Box %s") % qty_txt
        if product:
            return _("Packaging for %s") % product.display_name
        return _("Packaging")

    def _record_has_packaging_signature(self, rec):
        self.ensure_one()
        if not rec:
            return False

        has_product = "product_id" in rec._fields and bool(rec.product_id)
        has_qty = bool(self._get_packaging_qty_field_name(rec)) or bool(self._get_packaging_qty_from_name(rec))

        if has_product and has_qty:
            return True

        model_name = getattr(rec, "_name", "") or ""
        display_name = ""
        try:
            display_name = (rec.display_name or "").lower()
        except Exception:
            display_name = ""

        if has_product and (
            "pack" in model_name
            or "packaging" in model_name
            or "pack" in display_name
            or "pcs" in display_name
            or "box" in display_name
        ):
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

        if "product.packaging" in self.env:
            Packaging = self.env["product.packaging"]
            try:
                domain = [("barcode", "=", barcode)]
                if "company_id" in Packaging._fields:
                    domain = [
                        ("barcode", "=", barcode),
                        "|",
                        ("company_id", "=", False),
                        ("company_id", "=", self.company_id.id),
                    ]
                packaging = Packaging.search(domain, limit=1)
                if packaging:
                    return packaging
            except Exception:
                pass

        try:
            for model_name in self.env:
                try:
                    Model = self.env[model_name]
                    has_barcode = "barcode" in Model._fields
                    has_barcodes = "barcodes" in Model._fields
                    if not has_barcode and not has_barcodes:
                        continue

                    rec = False
                    if has_barcode:
                        rec = Model.search([("barcode", "=", barcode)], limit=1)
                    if not rec and has_barcodes:
                        rec = Model.search([("barcodes", "=", barcode)], limit=1)
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
        if not barcode or "route.product.barcode" not in self.env:
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
        rec = Barcode.search([("barcode", "=", barcode)], limit=1)
        return rec or False

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
                    has_barcode = "barcode" in Model._fields
                    has_barcodes = "barcodes" in Model._fields
                    if not has_barcode and not has_barcodes:
                        continue

                    rec = False
                    if has_barcode:
                        rec = Model.search([("barcode", "=", barcode)], limit=1)
                    if not rec and has_barcodes:
                        rec = Model.search([("barcodes", "=", barcode)], limit=1)
                    if not rec:
                        continue

                    packaging = self._extract_packaging_from_record(rec)
                    if packaging and getattr(packaging, "product_id", False):
                        product = packaging.product_id
                        packaging_qty = self._get_packaging_qty(packaging) or 1.0
                        packaging_uom = self._get_packaging_uom(packaging, product) or product.uom_id
                        return {
                            "product": product,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": packaging,
                            "packaging_display_name": self._get_packaging_display_name(packaging, product=product),
                            "default_scan_qty": packaging_qty,
                            "default_scanned_uom": packaging_uom,
                        }

                    if self._record_has_packaging_signature(rec) and getattr(rec, "product_id", False):
                        product = rec.product_id
                        qty = self._get_packaging_qty(rec) or 1.0
                        uom = self._get_packaging_uom(rec, product) or product.uom_id
                        return {
                            "product": product,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": rec,
                            "packaging_display_name": self._get_packaging_display_name(rec, product=product),
                            "default_scan_qty": qty,
                            "default_scanned_uom": uom,
                        }

                    if not weak_fallback and "product_id" in Model._fields and rec.product_id:
                        weak_fallback = {
                            "product": rec.product_id,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": rec,
                            "packaging_display_name": self._get_packaging_display_name(rec, product=rec.product_id),
                            "default_scan_qty": 1.0,
                            "default_scanned_uom": rec.product_id.uom_id,
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
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging = self._find_product_packaging_by_barcode(barcode)
        if packaging and getattr(packaging, "product_id", False):
            product = packaging.product_id
            packaging_qty = self._get_packaging_qty(packaging) or 1.0
            packaging_uom = self._get_packaging_uom(packaging, product) or product.uom_id
            return {
                "product": product,
                "scan_type": "box",
                "scan_type_label": _("Box Barcode"),
                "packaging": packaging,
                "packaging_display_name": self._get_packaging_display_name(packaging, product=product),
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
            return {
                "product": route_barcode.product_id,
                "scan_type": barcode_type,
                "scan_type_label": _("Box Barcode" if barcode_type == "box" else "Piece Barcode"),
                "packaging": route_barcode,
                "packaging_display_name": self._get_packaging_display_name(route_barcode, product=route_barcode.product_id),
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
            line.write(
                {
                    "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                    "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
                }
            )
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
