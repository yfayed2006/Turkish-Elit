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

    def _parse_qty_from_packaging_name(self, name):
        self.ensure_one()
        name = (name or "").strip()
        if not name:
            return 0.0
        matches = re.findall(r"(\d+(?:\.\d+)?)", name)
        if not matches:
            return 0.0
        try:
            return float(matches[-1])
        except Exception:
            return 0.0

    def _get_packaging_qty(self, record):
        self.ensure_one()
        if not record:
            return 0.0

        qty_field = self._get_packaging_qty_field_name(record)
        if qty_field:
            raw_value = record[qty_field] or 0.0
            try:
                raw_value = float(raw_value)
            except Exception:
                raw_value = 0.0

            if qty_field == "factor_inv":
                return raw_value if raw_value > 0 else 0.0
            if qty_field == "factor":
                if raw_value > 1:
                    return raw_value
                if raw_value > 0:
                    return 1.0 / raw_value
                return 0.0
            if raw_value > 0:
                return raw_value

        for field_name in ("display_name", "name"):
            try:
                value = getattr(record, field_name, False) or record[field_name]
            except Exception:
                value = False
            qty = self._parse_qty_from_packaging_name(value)
            if qty > 0:
                return qty
        return 0.0

    def _get_packaging_uom(self, record, product=False):
        self.ensure_one()
        if not record:
            return product.uom_id if product else False

        uom_field = self._get_packaging_uom_field_name(record)
        if uom_field and record[uom_field]:
            return record[uom_field]
        return product.uom_id if product else False

    def _search_records_by_barcode(self, model_name, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode or model_name not in self.env:
            return False

        Model = self.env[model_name]

        for field_name, field in Model._fields.items():
            field_type = getattr(field, "type", None)
            if field_type not in ("char", "text") or "barcode" not in field_name.lower():
                continue
            try:
                rec = Model.search([(field_name, "=", barcode)], limit=1)
                if rec:
                    return rec
            except Exception:
                continue

        for field_name, field in Model._fields.items():
            field_type = getattr(field, "type", None)
            relation = getattr(field, "comodel_name", False)
            if field_type not in ("many2one", "one2many", "many2many") or not relation or relation not in self.env:
                continue

            RelModel = self.env[relation]
            rel_barcode_fields = []
            for rel_field_name, rel_field in RelModel._fields.items():
                rel_field_type = getattr(rel_field, "type", None)
                if rel_field_type in ("char", "text") and (
                    "barcode" in rel_field_name.lower()
                    or (relation.endswith("barcode") and rel_field_name == "name")
                ):
                    rel_barcode_fields.append(rel_field_name)

            for rel_barcode_field in rel_barcode_fields:
                try:
                    rel_rec = RelModel.search([(rel_barcode_field, "=", barcode)], limit=1)
                except Exception:
                    rel_rec = False
                if not rel_rec:
                    continue

                try:
                    if field_type == "many2one":
                        rec = Model.search([(field_name, "=", rel_rec.id)], limit=1)
                    else:
                        rec = Model.search([(field_name, "in", rel_rec.ids)], limit=1)
                    if rec:
                        return rec
                except Exception:
                    pass

                for back_name in ("packaging_id", "product_packaging_id", "uom_id", "unit_id"):
                    try:
                        if back_name in RelModel._fields and rel_rec[back_name] and rel_rec[back_name]._name == model_name:
                            return rel_rec[back_name]
                    except Exception:
                        continue
        return False

    def _find_products_linked_to_packaging(self, packaging):
        self.ensure_one()
        products = self.env["product.product"]
        if not packaging:
            return products

        if "product_id" in packaging._fields and packaging.product_id:
            return packaging.product_id
        if "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
            tmpl = packaging.product_tmpl_id
            return tmpl.product_variant_id or tmpl.product_variant_ids[:1]

        for model_name in ("product.product", "product.template"):
            Model = self.env[model_name]
            found = Model.browse()
            for field_name, field in Model._fields.items():
                relation = getattr(field, "comodel_name", False)
                field_type = getattr(field, "type", None)
                if relation != packaging._name:
                    continue
                if "pack" not in field_name.lower():
                    continue
                try:
                    if field_type == "many2one":
                        recs = Model.search([(field_name, "=", packaging.id)])
                    else:
                        recs = Model.search([(field_name, "in", packaging.ids)])
                except Exception:
                    recs = Model.browse()
                found |= recs
            if not found:
                continue
            if model_name == "product.template":
                products |= found.mapped("product_variant_id") | found.mapped("product_variant_ids")
            else:
                products |= found

        if len(products) > 1:
            visit_products = self.line_ids.mapped("product_id")
            narrowed = products.filtered(lambda p: p in visit_products)
            if len(narrowed) == 1:
                return narrowed
            available = products.filtered(lambda p: self._is_product_available_in_vehicle(p))
            if len(available) == 1:
                return available
        return products[:1]

    def _get_packaging_display_name(self, packaging, product=False):
        self.ensure_one()
        if not packaging:
            return False

        display_name = False
        for field_name in ("display_name", "name"):
            try:
                value = getattr(packaging, field_name, False) or packaging[field_name]
            except Exception:
                value = False
            if value:
                display_name = str(value).strip()
                break

        if display_name:
            compact = display_name.replace(" ", "")
            if compact.isdigit() or "/" in display_name or "LOT" in display_name.upper():
                display_name = False

        qty = self._get_packaging_qty(packaging)
        if display_name and qty > 0:
            if re.search(r"\d", display_name):
                return display_name
            qty_label = str(int(qty)) if float(qty).is_integer() else str(qty)
            return f"{display_name} {qty_label}"
        if qty > 0:
            qty_label = str(int(qty)) if float(qty).is_integer() else str(qty)
            return _("Box %s") % qty_label
        return display_name or _("Box")

    def _find_packaging_info_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        if "product.packaging" in self.env:
            packaging = self._search_records_by_barcode("product.packaging", barcode)
            if packaging:
                product = self._find_products_linked_to_packaging(packaging)
                if product:
                    qty = self._get_packaging_qty(packaging) or 1.0
                    uom = self._get_packaging_uom(packaging, product) or product.uom_id
                    return {
                        "record": packaging,
                        "product": product,
                        "qty": qty,
                        "uom": uom,
                        "display_name": self._get_packaging_display_name(packaging, product),
                    }

        if "uom.uom" in self.env:
            packaging = self._search_records_by_barcode("uom.uom", barcode)
            if packaging:
                product = self._find_products_linked_to_packaging(packaging)
                if product:
                    qty = self._get_packaging_qty(packaging) or 1.0
                    uom = self._get_packaging_uom(packaging, product) or product.uom_id
                    return {
                        "record": packaging,
                        "product": product,
                        "qty": qty,
                        "uom": uom,
                        "display_name": self._get_packaging_display_name(packaging, product),
                    }
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
            domain += ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
        rec = Barcode.search(domain, limit=1)
        if rec:
            return rec
        return Barcode.search([("barcode", "=", barcode)], limit=1)

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

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
                "packaging_display_name": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging_info = self._find_packaging_info_by_barcode(barcode)
        if packaging_info and packaging_info.get("product"):
            return {
                "product": packaging_info["product"],
                "scan_type": "box",
                "scan_type_label": _("Box Barcode"),
                "packaging": packaging_info["record"],
                "packaging_display_name": packaging_info.get("display_name"),
                "default_scan_qty": packaging_info.get("qty") or 1.0,
                "default_scanned_uom": packaging_info.get("uom") or packaging_info["product"].uom_id,
            }

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = route_barcode.barcode_type or "piece" if "barcode_type" in route_barcode._fields else "piece"
            qty_in_base_uom = route_barcode.qty_in_base_uom or 1.0 if "qty_in_base_uom" in route_barcode._fields else 1.0
            packaging_name = False
            if barcode_type == "box" and qty_in_base_uom > 0:
                qty_label = str(int(qty_in_base_uom)) if float(qty_in_base_uom).is_integer() else str(qty_in_base_uom)
                packaging_name = _("Box %s") % qty_label
            return {
                "product": route_barcode.product_id,
                "scan_type": barcode_type,
                "scan_type_label": _("Box Barcode" if barcode_type == "box" else "Piece Barcode"),
                "packaging": False,
                "packaging_display_name": packaging_name,
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

        effective_scan_qty = scan_qty or 1.0
        effective_scanned_uom = scanned_uom or scan_info.get("default_scanned_uom") or product.uom_id

        if scan_info.get("scan_type") == "box":
            boxes_qty = scan_qty or 1.0
            pieces_per_box = scan_info.get("default_scan_qty") or 1.0
            counted_increase = pieces_per_box * boxes_qty
            effective_scan_qty = boxes_qty
            effective_scanned_uom = product.uom_id
        else:
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
