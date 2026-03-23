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

    def _record_has_packaging_signature(self, rec):
        self.ensure_one()
        if not rec:
            return False

        has_product = "product_id" in rec._fields and bool(rec.product_id)
        has_qty = bool(self._get_packaging_qty_field_name(rec))

        if has_product and has_qty:
            return True

        # أحيانًا يكون السجل اسمه/موديله يشير للتغليف حتى لو الحقول مختلفة قليلًا
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

        # 1) السجل نفسه ربما يكون سجل تغليف أو يحمل كمية التغليف
        if self._record_has_packaging_signature(rec):
            return rec

        # 2) جرب أي سجل مرتبط
        for target in self._iter_related_records(rec):
            try:
                if self._record_has_packaging_signature(target):
                    return target
            except Exception:
                continue

        # 3) جرب طبقة ثانية من العلاقات
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

    def _normalize_barcode_value(self, value):
        self.ensure_one()
        return str(value or "").strip()

    def _record_contains_barcode(self, rec, barcode):
        self.ensure_one()
        barcode = self._normalize_barcode_value(barcode)
        if not rec or not barcode:
            return False

        direct_candidates = (
            "barcode",
            "barcodes",
            "barcode_text",
            "barcode_value",
            "code",
        )
        related_value_candidates = (
            "barcode",
            "name",
            "code",
            "display_name",
            "value",
        )

        for field_name, field in rec._fields.items():
            try:
                field_type = getattr(field, "type", None)

                if field_name in direct_candidates or "barcode" in field_name:
                    if field_type in ("char", "text"):
                        if self._normalize_barcode_value(rec[field_name]) == barcode:
                            return True

                    if field_type in ("many2one", "one2many", "many2many"):
                        related = rec[field_name]
                        related_records = related if field_type != "many2one" else related[:1]
                        for child in related_records:
                            for value_field in related_value_candidates:
                                if value_field in child._fields:
                                    if self._normalize_barcode_value(child[value_field]) == barcode:
                                        return True
            except Exception:
                continue

        return False

    def _resolve_product_from_packaging_record(self, packaging):
        self.ensure_one()
        if not packaging:
            return False

        if "product_id" in packaging._fields and packaging.product_id:
            return packaging.product_id

        if "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
            template = packaging.product_tmpl_id
            if "product_variant_id" in template._fields and template.product_variant_id:
                return template.product_variant_id
            if "product_variant_ids" in template._fields and template.product_variant_ids:
                return template.product_variant_ids[:1]

        for model_name in ("product.template", "product.product"):
            if model_name not in self.env:
                continue

            Model = self.env[model_name]
            relational_fields = []
            for field_name, field in Model._fields.items():
                try:
                    if getattr(field, "type", None) not in ("many2one", "one2many", "many2many"):
                        continue
                    if getattr(field, "comodel_name", None) != packaging._name:
                        continue
                    lowered = (field_name or "").lower()
                    if "pack" not in lowered and "package" not in lowered:
                        continue
                    relational_fields.append((field_name, field.type))
                except Exception:
                    continue

            for field_name, field_type in relational_fields:
                try:
                    domain = [(field_name, "=", packaging.id)]
                    if field_type in ("one2many", "many2many"):
                        domain = [(field_name, "in", packaging.id)]
                    found = Model.search(domain, limit=1)
                    if not found:
                        continue

                    if model_name == "product.template":
                        if "product_variant_id" in found._fields and found.product_variant_id:
                            return found.product_variant_id
                        if "product_variant_ids" in found._fields and found.product_variant_ids:
                            return found.product_variant_ids[:1]
                    return found
                except Exception:
                    continue

        return False

    def _build_packaging_scan_info(self, packaging):
        self.ensure_one()
        if not packaging:
            return False

        product = self._resolve_product_from_packaging_record(packaging)
        if not product:
            return False

        packaging_qty = self._get_packaging_qty(packaging)
        if packaging_qty <= 0:
            packaging_qty = 1.0

        packaging_uom = self._get_packaging_uom(packaging, product)
        if not packaging_uom:
            packaging_uom = product.uom_id

        return {
            "product": product,
            "scan_type": "box",
            "scan_type_label": _("Box Barcode"),
            "packaging": packaging,
            "default_scan_qty": packaging_qty,
            "default_scanned_uom": packaging_uom,
        }

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = self._normalize_barcode_value(barcode)
        if not barcode:
            return False

        candidate_models = []
        for model_name in ("product.packaging", "uom.uom"):
            if model_name in self.env:
                candidate_models.append(model_name)

        for model_name in candidate_models:
            Model = self.env[model_name]

            if "active" in Model._fields:
                search_domain = [("active", "=", True)]
            else:
                search_domain = []

            if "company_id" in Model._fields:
                search_domain = search_domain + [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", self.company_id.id),
                ]

            direct_hits = self.env[model_name]
            if "barcode" in Model._fields:
                try:
                    direct_domain = list(search_domain) + [("barcode", "=", barcode)]
                    direct_hits = Model.search(direct_domain, limit=5)
                except Exception:
                    direct_hits = self.env[model_name]

            for rec in direct_hits:
                info = self._build_packaging_scan_info(rec)
                if info:
                    return info

            try:
                for rec in Model.search(search_domain, limit=500):
                    if not self._record_contains_barcode(rec, barcode):
                        continue
                    info = self._build_packaging_scan_info(rec)
                    if info:
                        return info
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

                    # 1) أفضل حالة: استخرج سجل تغليف أو سجل يحمل qty حقيقية
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
                        }

                    # 2) لو السجل نفسه يحمل product + qty
                    if self._record_has_packaging_signature(rec):
                        qty = self._get_packaging_qty(rec) or 1.0
                        uom = self._get_packaging_uom(rec, rec.product_id) or rec.product_id.uom_id
                        return {
                            "product": rec.product_id,
                            "scan_type": "box",
                            "scan_type_label": _("Box Barcode"),
                            "packaging": rec,
                            "default_scan_qty": qty,
                            "default_scanned_uom": uom,
                        }

                    # 3) fallback ضعيف جدًا: فقط خزنه ولا ترجعه فورًا
                    # حتى لا يسرق الباركود قبل أن نجد كمية التغليف الحقيقية
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

        # 1) direct product barcode
        product = self.env["product.product"].search(
            [("barcode", "=", barcode)],
            limit=1,
        )
        if product:
            return {
                "product": product,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        # 2) original Odoo packaging / units FIRST
        packaging_info = self._find_product_packaging_by_barcode(barcode)
        if packaging_info:
            return packaging_info

        # 3) custom route barcode LAST
        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = "piece"
            if "barcode_type" in route_barcode._fields and route_barcode.barcode_type:
                barcode_type = route_barcode.barcode_type

            qty_in_base_uom = 1.0
            if "qty_in_base_uom" in route_barcode._fields and route_barcode.qty_in_base_uom:
                qty_in_base_uom = route_barcode.qty_in_base_uom

            if barcode_type == "box":
                raise UserError(
                    _(
                        "Barcode '%(barcode)s' is marked as a box barcode in Route Product Barcodes, "
                        "but no original Odoo Packaging/Unit barcode was found for it. "
                        "Please define this barcode on the product Packaging record first."
                    )
                    % {"barcode": barcode}
                )

            return {
                "product": route_barcode.product_id,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
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
