from datetime import timedelta
import re
from html import unescape

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteVisitPayment(models.Model):
    _name = "route.visit.payment"
    _description = "Route Visit Payment"
    _order = "payment_date desc, id desc"
    _rec_name = "source_document_ref"

    source_type = fields.Selection(
        [
            ("visit", "Visit"),
            ("direct_sale", "Direct Sale"),
        ],
        string="Source Type",
        required=True,
        default="visit",
    )

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        ondelete="cascade",
        index=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Direct Sale Order",
        domain=[("route_order_mode", "=", "direct_sale")],
        ondelete="cascade",
        index=True,
    )

    settlement_visit_id = fields.Many2one(
        "route.visit",
        string="Settlement Visit",
        ondelete="set null",
        index=True,
        help="Direct-sales stop that grouped this payment allocation.",
    )

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    source_document_ref = fields.Char(
        string="Source Document",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    settlement_document_ref = fields.Char(
        string="Settlement Visit",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    payment_business_flow = fields.Selection(
        [
            ("consignment_visit", "Visit Collection"),
            ("direct_stop", "Direct Stop Settlement"),
            ("direct_sale_order", "Direct Sale Order"),
        ],
        string="Business Flow",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    payment_business_flow_short = fields.Char(
        string="Flow (Short)",
        compute="_compute_ui_labels",
        store=False,
        readonly=True,
    )


    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    payment_date = fields.Datetime(
        string="Payment Date",
        default=fields.Datetime.now,
        required=True,
    )
    collection_time_bucket = fields.Selection(
        [
            ("today", "Today"),
            ("last_7_days", "Last 7 Days"),
            ("last_30_days", "Last 30 Days"),
            ("this_month", "This Month"),
            ("older", "Older"),
        ],
        string="Collection Time",
        compute="_compute_collection_time_bucket",
        store=True,
        index=True,
        readonly=True,
    )


    payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
            ("cheque", "Cheque"),
            ("deferred", "Deferred"),
        ],
        string="Payment Mode",
        required=True,
        default="cash",
    )

    collection_type = fields.Selection(
        [
            ("full", "Full Payment"),
            ("partial", "Partial Payment + Carry Forward"),
            ("defer_date", "Defer To Specific Date"),
            ("next_visit", "Carry To Next Visit"),
        ],
        string="Collection Scenario",
        required=True,
        default="full",
    )


    collection_type_short = fields.Char(
        string="Collection Scenario (Short)",
        compute="_compute_ui_labels",
        store=False,
        readonly=True,
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    promise_date = fields.Date(string="Promise To Pay Date")
    promise_amount = fields.Monetary(
        string="Promise To Pay Amount",
        currency_field="currency_id",
        default=0.0,
    )
    effective_promise_amount = fields.Monetary(
        string="Effective Promise Amount",
        currency_field="currency_id",
        compute="_compute_effective_promise_amount",
        store=False,
    )
    promise_status = fields.Selection(
        [
            ("open", "Open"),
            ("due_today", "Due Today"),
            ("overdue", "Overdue"),
            ("closed", "Closed"),
        ],
        string="Promise Status",
        compute="_compute_promise_status",
        store=False,
    )

    remaining_due_amount = fields.Monetary(
        string="Unpaid Amount",
        currency_field="currency_id",
        compute="_compute_remaining_due_amount",
        store=False,
    )

    collection_due_bucket = fields.Selection(
        [
            ("fully_collected", "Fully Collected"),
            ("remaining_due", "Remaining Due"),
        ],
        string="Financial Status",
        compute="_compute_collection_filter_buckets",
        store=True,
        index=True,
        readonly=True,
    )

    collection_promise_bucket = fields.Selection(
        [
            ("no_promise", "No Promise"),
            ("open", "Open Promise"),
            ("due_today", "Promise Due Today"),
            ("overdue", "Overdue Promise"),
            ("closed", "Promise Closed"),
        ],
        string="Promise Filter",
        compute="_compute_collection_filter_buckets",
        store=True,
        index=True,
        readonly=True,
    )

    due_date = fields.Date(string="Deferred Due Date")

    deferred_payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
            ("cheque", "Cheque"),
        ],
        string="Expected Deferred Payment Mode",
        help="Expected method for collecting the carried-forward balance on a partial payment.",
    )
    deferred_reference = fields.Char(string="Deferred Reference")
    deferred_bank_name = fields.Char(string="Deferred Bank Name")
    deferred_pos_terminal = fields.Char(string="Deferred POS Terminal")
    deferred_cheque_number = fields.Char(string="Deferred Cheque Number")
    deferred_cheque_date = fields.Date(string="Deferred Cheque Date")
    deferred_cheque_holder_name = fields.Char(string="Deferred Cheque Holder")
    deferred_cheque_note = fields.Text(string="Deferred Cheque Details")

    reference = fields.Char(string="Reference")
    bank_name = fields.Char(string="Bank Name")
    pos_terminal = fields.Char(string="POS Terminal")
    cheque_number = fields.Char(string="Cheque Number")
    cheque_date = fields.Date(string="Cheque Date")
    cheque_holder_name = fields.Char(string="Cheque Holder")
    cheque_note = fields.Text(string="Cheque Details")
    note = fields.Text(string="Note")
    note_display_html = fields.Html(
        string="Rendered Note",
        compute="_compute_note_display_html",
        sanitize=False,
        store=False,
        readonly=True,
    )
    statement_visit_id = fields.Many2one(
        "route.visit",
        string="Statement Visit",
        compute="_compute_statement_visit_context",
        store=False,
        readonly=True,
    )
    can_open_statement = fields.Boolean(
        string="Can Open Statement",
        compute="_compute_statement_visit_context",
        store=False,
        readonly=True,
    )

    show_settlement_reference = fields.Boolean(
        string="Show Settlement Reference",
        compute="_compute_statement_visit_context",
        store=False,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    visit_remaining_due = fields.Monetary(
        string="Current Remaining Due",
        currency_field="currency_id",
        compute="_compute_visit_remaining_due",
        store=False,
    )

    @api.depends("payment_date")
    def _compute_collection_time_bucket(self):
        today = fields.Date.context_today(self)
        first_day = today.replace(day=1)
        for rec in self:
            if not rec.payment_date:
                rec.collection_time_bucket = False
                continue
            payment_dt = rec.payment_date
            if isinstance(payment_dt, str):
                payment_dt = fields.Datetime.to_datetime(payment_dt)
            payment_date = fields.Date.to_date(payment_dt)
            if not payment_date:
                rec.collection_time_bucket = False
            elif payment_date == today:
                rec.collection_time_bucket = "today"
            elif payment_date >= today - timedelta(days=6):
                rec.collection_time_bucket = "last_7_days"
            elif payment_date >= today - timedelta(days=29):
                rec.collection_time_bucket = "last_30_days"
            elif payment_date >= first_day:
                rec.collection_time_bucket = "this_month"
            else:
                rec.collection_time_bucket = "older"

    def name_get(self):
        result = []
        flow_labels = dict(self._fields["payment_business_flow"].selection)
        for rec in self:
            title = rec.source_document_ref or rec.settlement_document_ref or rec.reference or _("Payment")
            flow = flow_labels.get(rec.payment_business_flow)
            if flow and title != flow:
                title = f"{title} - {flow}"
            result.append((rec.id, title))
        return result

    @api.depends("payment_business_flow", "collection_type")
    def _compute_ui_labels(self):
        flow_labels = {
            "consignment_visit": _("Visit"),
            "direct_stop": _("Direct Stop"),
            "direct_sale_order": _("Direct Order"),
        }
        collection_labels = {
            "full": _("Full Pay"),
            "partial": _("Partial + Carry"),
            "defer_date": _("Defer Date"),
            "next_visit": _("Next Visit"),
        }
        for rec in self:
            rec.payment_business_flow_short = flow_labels.get(rec.payment_business_flow, rec.payment_business_flow or "")
            rec.collection_type_short = collection_labels.get(rec.collection_type, rec.collection_type or "")

    @api.depends(
        "source_type",
        "visit_id",
        "visit_id.outlet_id",
        "visit_id.area_id",
        "visit_id.user_id",
        "sale_order_id",
        "sale_order_id.name",
        "sale_order_id.route_outlet_id",
        "sale_order_id.route_outlet_id.area_id",
        "sale_order_id.user_id",
        "settlement_visit_id",
        "settlement_visit_id.name",
        "settlement_visit_id.visit_execution_mode",
    )
    def _compute_source_context(self):
        for rec in self:
            outlet = False
            area = False
            salesperson = False
            source_ref = False
            settlement_ref = False
            business_flow = "consignment_visit"

            if rec.source_type == "direct_sale" and rec.sale_order_id:
                outlet = rec.sale_order_id.route_outlet_id
                area = outlet.area_id if outlet else False
                salesperson = rec.sale_order_id.user_id
                source_ref = rec.sale_order_id.name
                business_flow = "direct_sale_order"
            elif rec.visit_id:
                outlet = rec.visit_id.outlet_id
                area = rec.visit_id.area_id
                salesperson = rec.visit_id.user_id
                source_ref = rec.visit_id.display_name or rec.visit_id.name

            if rec.settlement_visit_id:
                settlement_ref = rec.settlement_visit_id.display_name or rec.settlement_visit_id.name
                if getattr(rec.settlement_visit_id, "visit_execution_mode", False) == "direct_sales":
                    business_flow = "direct_stop"

            rec.outlet_id = outlet
            rec.area_id = area
            rec.salesperson_id = salesperson
            rec.source_document_ref = source_ref
            rec.settlement_document_ref = settlement_ref
            rec.payment_business_flow = business_flow


    @api.model
    def _route_clean_plain_text(self, value):
        if not value:
            return ""
        text = str(value)
        # Notes may be saved as literal HTML, escaped HTML, or double-escaped HTML
        # depending on whether they came from the wizard, receipt text, or old tests.
        # Unescape a few times before stripping tags so Completed Visit Summary never
        # shows raw <br/> / &lt;br/&gt; text inside payment cards.
        for _index in range(3):
            unescaped = unescape(text)
            if unescaped == text:
                break
            text = unescaped
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</\s*(div|p|li|tr|h[1-6])\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _get_clean_note_text(self):
        self.ensure_one()
        return self._route_clean_plain_text(self.note or "")

    @api.depends("note")
    def _compute_note_display_html(self):
        for rec in self:
            clean_note = rec._get_clean_note_text()
            rendered = escape(clean_note)
            rec.note_display_html = str(rendered).replace("\n", "<br/>") if rendered else False

    @api.depends("visit_id", "settlement_visit_id", "source_type", "source_document_ref", "settlement_document_ref")
    def _compute_statement_visit_context(self):
        for rec in self:
            statement_visit = rec.settlement_visit_id or rec.visit_id
            rec.statement_visit_id = statement_visit
            rec.can_open_statement = bool(statement_visit)
            rec.show_settlement_reference = bool(
                rec.settlement_document_ref
                and rec.settlement_document_ref != rec.source_document_ref
            )

    def action_open_statement_of_account(self):
        self.ensure_one()
        visit = self.statement_visit_id
        if not visit:
            raise ValidationError(_("Statement of Account is available only when this collection is linked to a visit."))
        if hasattr(visit, "action_open_statement_of_account"):
            return visit.with_context(
                statement_visit_id=visit.id,
                statement_visit_execution_mode=getattr(visit, "visit_execution_mode", False),
            ).action_open_statement_of_account()
        return {"type": "ir.actions.act_window_close"}

    def action_back_to_outlet_form(self):
        self.ensure_one()
        outlet = self.outlet_id
        if not outlet:
            outlet_id = self.env.context.get("route_outlet_back_id") or self.env.context.get("default_outlet_id")
            outlet = self.env["route.outlet"].browse(outlet_id).exists()
        if outlet:
            return outlet.action_open_pda_form()
        home = self.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = self.env.ref("route_core.view_route_pda_outlet_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Customer Profiles"),
            "res_model": "route.pda.home",
            "res_id": home.id,
            "view_mode": "form",
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def _get_target_model(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id
        return self.visit_id

    def _get_target_total_amount(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id.amount_total or 0.0

        if self.visit_id and getattr(self.visit_id, "visit_execution_mode", False) == "direct_sales":
            confirmed_payments = self.visit_id.payment_ids.filtered(lambda p: p.state == "confirmed") if self.visit_id.payment_ids else self.visit_id.payment_ids
            confirmed_amount = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
            return (self.visit_id.remaining_due_amount or 0.0) + confirmed_amount

        if self.visit_id:
            return self.visit_id.net_due_amount or 0.0
        return 0.0

    def _get_confirmed_target_payments(self, exclude_self=False):
        self.ensure_one()
        domain = [("state", "=", "confirmed")]
        if self.source_type == "direct_sale":
            domain.append(("sale_order_id", "=", self.sale_order_id.id or 0))
        else:
            domain.append(("visit_id", "=", self.visit_id.id or 0))

        payments = self.search(domain)
        if exclude_self and self.id:
            payments = payments.filtered(lambda p: p.id != self.id)
        return payments

    def _read_group_confirmed_amounts(self, target_field, target_ids):
        """Return confirmed collection totals by visit/order with one SQL query.

        The older compute path called ``search`` once per payment card.  On the
        salesperson Visit Collections screens this becomes expensive when many
        collection cards are shown.  This helper keeps the same business rule
        as ``_get_confirmed_target_payments`` but batches the sum calculation.
        """
        if not target_ids:
            return {}
        grouped = self.read_group(
            [("state", "=", "confirmed"), (target_field, "in", list(target_ids))],
            ["amount"],
            [target_field],
            lazy=False,
        )
        totals = {}
        for row in grouped:
            target_value = row.get(target_field)
            target_id = target_value[0] if isinstance(target_value, (tuple, list)) else target_value
            if target_id:
                totals[target_id] = row.get("amount") or 0.0
        return totals

    def _get_target_remaining_due_by_record(self, exclude_self=False):
        """Batch version of ``_get_target_remaining_due`` for compute methods."""
        payments = self
        result = {}

        visit_records = payments.filtered(lambda p: p.source_type != "direct_sale" and p.visit_id)
        order_records = payments.filtered(lambda p: p.source_type == "direct_sale" and p.sale_order_id)

        visit_ids = set(visit_records.mapped("visit_id").ids)
        order_ids = set(order_records.mapped("sale_order_id").ids)
        visit_confirmed = self._read_group_confirmed_amounts("visit_id", visit_ids)
        order_confirmed = self._read_group_confirmed_amounts("sale_order_id", order_ids)

        for rec in payments:
            if not rec._get_target_model():
                result[rec.id] = 0.0
                continue

            if rec.source_type == "direct_sale" and rec.sale_order_id:
                target_id = rec.sale_order_id.id
                total_amount = rec.sale_order_id.amount_total or 0.0
                confirmed_amount = order_confirmed.get(target_id, 0.0)
            elif rec.visit_id:
                target_id = rec.visit_id.id
                confirmed_amount = visit_confirmed.get(target_id, 0.0)
                if getattr(rec.visit_id, "visit_execution_mode", False) == "direct_sales":
                    total_amount = (rec.visit_id.remaining_due_amount or 0.0) + confirmed_amount
                else:
                    total_amount = rec.visit_id.net_due_amount or 0.0
            else:
                result[rec.id] = 0.0
                continue

            if exclude_self and rec.id and rec.state == "confirmed":
                confirmed_amount = max((confirmed_amount or 0.0) - (rec.amount or 0.0), 0.0)

            result[rec.id] = max((total_amount or 0.0) - (confirmed_amount or 0.0), 0.0)

        return result

    def _get_target_remaining_due(self, exclude_self=False):
        self.ensure_one()
        total_amount = self._get_target_total_amount()
        confirmed_amount = sum(self._get_confirmed_target_payments(exclude_self=exclude_self).mapped("amount"))
        return max((total_amount or 0.0) - (confirmed_amount or 0.0), 0.0)

    def _get_target_label(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return _("direct sale order")
        return _("visit")

    def _is_direct_stop_settlement_payment(self):
        self.ensure_one()
        return bool(
            self.settlement_visit_id
            and getattr(self.settlement_visit_id, "visit_execution_mode", False) == "direct_sales"
        )

    def _get_snapshot_payment_mode(self):
        self.ensure_one()
        if self.collection_type in ("defer_date", "next_visit"):
            return "deferred"
        return self.payment_mode or "cash"

    def _get_snapshot_promise_status(self):
        self.ensure_one()
        if self.state != "confirmed" or (self.promise_amount or 0.0) <= 0.0:
            return False
        if self._is_direct_stop_settlement_payment():
            today = fields.Date.context_today(self)
            if self.promise_date and self.promise_date < today:
                return "overdue"
            if self.promise_date and self.promise_date == today:
                return "due_today"
            return "open"
        return self.promise_status

    def _prepare_cheque_reference(self):
        for rec in self:
            if rec.payment_mode == "cheque" and rec.cheque_number and not rec.reference:
                rec.reference = rec.cheque_number

    def _validate_deferred_collection_plan(self):
        self.ensure_one()
        if self.collection_type != "partial":
            return
        if not self.deferred_payment_mode:
            return
        if self.deferred_payment_mode == "cheque":
            if not self.deferred_cheque_number:
                raise ValidationError(_("Please enter the deferred cheque number."))
            if not self.deferred_bank_name:
                raise ValidationError(_("Please enter the deferred cheque bank name."))
            if not self.deferred_cheque_date:
                raise ValidationError(_("Please enter the deferred cheque date."))

    def _validate_cheque_details(self):
        self.ensure_one()
        if self.payment_mode != "cheque":
            return
        if self.collection_type in ("defer_date", "next_visit"):
            return
        if not self.cheque_number:
            raise ValidationError(_("Please enter the cheque number."))
        if not self.bank_name:
            raise ValidationError(_("Please enter the cheque bank name."))
        if not self.cheque_date:
            raise ValidationError(_("Please enter the cheque date."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("payment_mode") == "cheque" and vals.get("cheque_number") and not vals.get("reference"):
                vals["reference"] = vals.get("cheque_number")
        records = super().create(vals_list)
        return records

    def write(self, vals):
        if vals.get("payment_mode") == "cheque" and vals.get("cheque_number") and not vals.get("reference"):
            vals = dict(vals)
            vals["reference"] = vals.get("cheque_number")
        result = super().write(vals)
        if "cheque_number" in vals or "payment_mode" in vals:
            self._prepare_cheque_reference()
        return result

    @api.onchange("payment_mode")
    def _onchange_payment_mode(self):
        for rec in self:
            if rec.payment_mode in ("cash", "deferred"):
                rec.bank_name = False
                rec.pos_terminal = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "bank":
                rec.pos_terminal = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "pos":
                rec.bank_name = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "cheque":
                rec.pos_terminal = False
                rec._prepare_cheque_reference()

    @api.onchange("cheque_number")
    def _onchange_cheque_number(self):
        self._prepare_cheque_reference()

    def _check_direct_stop_settlement_payment_rules(self):
        self.ensure_one()
        if self.amount < 0:
            raise ValidationError(_("Payment amount cannot be negative."))

        if self.collection_type in ("defer_date", "next_visit") and self.payment_mode != "deferred":
            raise ValidationError(_("Deferred scenarios must use payment mode Deferred."))

        if self.collection_type in ("full", "partial") and self.payment_mode == "deferred":
            raise ValidationError(_("Deferred payment mode is only allowed for defer-to-date or next-visit scenarios."))

        self._validate_cheque_details()
        self._validate_deferred_collection_plan()

        # Direct-stop settlements can be split across older unpaid visits plus the current stop.
        # The settlement wizard already validates the total collection against the direct-stop
        # balance before creating the draft lines. During batch confirmation, earlier lines in the
        # same settlement can reduce the target visits' remaining due, so comparing each draft
        # line again against the live target balance would incorrectly block valid allocations.
        if self.collection_type == "full":
            if self.amount <= 0:
                raise ValidationError(_("Full payment amount must be greater than zero."))

        elif self.collection_type == "partial":
            if self.amount <= 0:
                raise ValidationError(_("Partial payment amount must be greater than zero."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promised unpaid amount."))
            if not self.promise_date:
                raise ValidationError(_("Please set the promise to pay date for the carried-forward balance."))
            if not self.note:
                raise ValidationError(_("Please add a note for the carried-forward balance."))

        elif self.collection_type == "defer_date":
            if self.amount != 0:
                raise ValidationError(_("Deferred payment to a specific date must have amount = 0."))
            if not self.due_date:
                raise ValidationError(_("Please set the deferred due date."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promise to pay amount."))
            if not (self.promise_date or self.due_date):
                raise ValidationError(_("Please set the promise to pay date."))
            if not self.note:
                raise ValidationError(_("Please add a note explaining the deferment."))

        elif self.collection_type == "next_visit":
            if self.amount != 0:
                raise ValidationError(_("Carry to next visit must have amount = 0."))
            if self.due_date:
                raise ValidationError(_("Do not set a due date when carrying payment to the next visit."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promise to pay amount."))
            if not self.promise_date:
                raise ValidationError(_("Please set the promise to pay date for the next visit."))
            if not self.note:
                raise ValidationError(_("Please add a note explaining why payment is carried to next visit."))

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_visit_remaining_due(self):
        remaining_by_record = self._get_target_remaining_due_by_record()
        for rec in self:
            rec.visit_remaining_due = remaining_by_record.get(rec.id, 0.0)

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_remaining_due_amount(self):
        remaining_by_record = self._get_target_remaining_due_by_record()
        for rec in self:
            rec.remaining_due_amount = remaining_by_record.get(rec.id, 0.0)

    @api.depends(
        "state",
        "collection_type",
        "amount",
        "promise_amount",
        "promise_date",
        "due_date",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_collection_filter_buckets(self):
        today = fields.Date.context_today(self)
        remaining_by_record = self._get_target_remaining_due_by_record()
        for rec in self:
            remaining_due = remaining_by_record.get(rec.id, 0.0)

            rec.collection_due_bucket = "remaining_due" if (remaining_due or 0.0) > 0.0001 else "fully_collected"

            if rec.state != "confirmed" or (rec.promise_amount or 0.0) <= 0.0:
                rec.collection_promise_bucket = "no_promise"
            elif remaining_due <= 0.0001 and not rec._is_direct_stop_settlement_payment():
                rec.collection_promise_bucket = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.collection_promise_bucket = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.collection_promise_bucket = "due_today"
            else:
                rec.collection_promise_bucket = "open"


    @api.depends(
        "collection_type",
        "amount",
        "promise_amount",
        "state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_effective_promise_amount(self):
        remaining_excluding_self = self._get_target_remaining_due_by_record(exclude_self=True)
        for rec in self:
            if not rec._get_target_model():
                rec.effective_promise_amount = 0.0
                continue

            if rec._is_direct_stop_settlement_payment():
                rec.effective_promise_amount = rec.promise_amount or 0.0
                continue

            due_before_this_payment = remaining_excluding_self.get(rec.id, 0.0)
            due_before_this_payment = max(due_before_this_payment or 0.0, 0.0)

            if rec.collection_type == "partial":
                rec.effective_promise_amount = max(
                    due_before_this_payment - (rec.amount or 0.0), 0.0
                )
            elif rec.collection_type in ("defer_date", "next_visit"):
                rec.effective_promise_amount = due_before_this_payment
            else:
                rec.effective_promise_amount = 0.0

    @api.depends(
        "promise_amount",
        "promise_date",
        "state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_promise_status(self):
        today = fields.Date.context_today(self)
        remaining_by_record = self._get_target_remaining_due_by_record()
        for rec in self:
            if rec.state == "cancelled" or (rec.promise_amount or 0.0) <= 0:
                rec.promise_status = False
                continue

            if rec._is_direct_stop_settlement_payment():
                if rec.promise_date and rec.promise_date < today:
                    rec.promise_status = "overdue"
                elif rec.promise_date and rec.promise_date == today:
                    rec.promise_status = "due_today"
                else:
                    rec.promise_status = "open"
                continue

            remaining_due = remaining_by_record.get(rec.id, 0.0)
            if remaining_due <= 0:
                rec.promise_status = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.promise_status = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.promise_status = "due_today"
            else:
                rec.promise_status = "open"

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id")
        sale_order_id = self.env.context.get("default_sale_order_id")

        if sale_order_id:
            order = self.env["sale.order"].browse(sale_order_id)
            vals.setdefault("source_type", "direct_sale")
            vals.setdefault("sale_order_id", sale_order_id)
            vals.setdefault("payment_mode", order.route_payment_mode or "cash")
            if "amount" in fields_list:
                vals["amount"] = max(order._get_route_payment_remaining_due() if hasattr(order, "_get_route_payment_remaining_due") else (order.amount_total or 0.0), 0.0)
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "defer_date" if order.route_payment_mode == "deferred" else "full")
            if order.route_payment_mode == "deferred":
                vals.setdefault("due_date", order.route_payment_due_date)
                vals.setdefault("promise_date", order.route_payment_due_date)
                vals.setdefault("promise_amount", max(order._get_route_payment_remaining_due() if hasattr(order, "_get_route_payment_remaining_due") else (order.amount_total or 0.0), 0.0))
                vals.setdefault("amount", 0.0)
        elif visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            vals.setdefault("source_type", "visit")
            vals.setdefault("visit_id", visit_id)
            if "amount" in fields_list:
                vals["amount"] = max(visit.remaining_due_amount or 0.0, 0.0)
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "full")
        return vals

    @api.onchange("source_type")
    def _onchange_source_type(self):
        for rec in self:
            if rec.source_type == "direct_sale":
                rec.visit_id = False
            else:
                rec.sale_order_id = False

    def _sync_promise_fields(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0
            if rec.collection_type == "full":
                rec.promise_date = False
                rec.promise_amount = 0.0
            elif rec.collection_type == "partial":
                rec.promise_amount = max(due - (rec.amount or 0.0), 0.0)
            elif rec.collection_type == "defer_date":
                rec.promise_date = rec.due_date or rec.promise_date
                rec.promise_amount = due
            elif rec.collection_type == "next_visit":
                rec.promise_amount = due

    @api.onchange("visit_id", "sale_order_id", "source_type")
    def _onchange_payment_target_set_amount(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0
            if rec.source_type == "direct_sale" and rec.sale_order_id and rec.sale_order_id.route_payment_mode == "deferred" and rec.collection_type == "full":
                rec.collection_type = "defer_date"
                rec.payment_mode = "deferred"
            if rec.collection_type == "full":
                rec.amount = due
            elif rec.collection_type == "partial":
                if due > 0 and (rec.amount <= 0 or rec.amount >= due):
                    rec.amount = due / 2.0
            rec._sync_promise_fields()

    @api.onchange("collection_type", "amount", "due_date", "promise_date")
    def _onchange_collection_type(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0

            if rec.collection_type == "full":
                rec.amount = due
                rec.due_date = False
                if rec.payment_mode == "deferred":
                    rec.payment_mode = "cash"

            elif rec.collection_type == "partial":
                rec.due_date = False
                if rec.payment_mode == "deferred":
                    rec.payment_mode = "cash"
                if due <= 0:
                    rec.amount = 0.0
                elif rec.amount <= 0 or rec.amount >= due:
                    rec.amount = due / 2.0

            elif rec.collection_type == "defer_date":
                rec.amount = 0.0
                rec.payment_mode = "deferred"

            elif rec.collection_type == "next_visit":
                rec.amount = 0.0
                rec.due_date = False
                rec.payment_mode = "deferred"

            rec._sync_promise_fields()

    @api.constrains("source_type", "visit_id", "sale_order_id")
    def _check_source_target(self):
        for rec in self:
            if rec.source_type == "visit":
                if not rec.visit_id:
                    raise ValidationError(_("A Visit is required for payments with source type Visit."))
                if rec.sale_order_id:
                    raise ValidationError(_("Do not set a Direct Sale Order when the payment source type is Visit."))
            elif rec.source_type == "direct_sale":
                if not rec.sale_order_id:
                    raise ValidationError(_("A Direct Sale Order is required for payments with source type Direct Sale."))
                if rec.visit_id:
                    raise ValidationError(_("Do not set a Visit when the payment source type is Direct Sale."))
                if rec.sale_order_id.route_order_mode != "direct_sale":
                    raise ValidationError(_("Only Direct Sale orders can be used here."))

    @api.constrains(
        "amount",
        "collection_type",
        "due_date",
        "promise_date",
        "promise_amount",
        "visit_id",
        "sale_order_id",
        "payment_mode",
        "bank_name",
        "cheque_number",
        "cheque_date",
        "deferred_payment_mode",
        "deferred_bank_name",
        "deferred_cheque_number",
        "deferred_cheque_date",
    )
    def _check_payment_rules(self):
        for rec in self:
            if not rec._get_target_model():
                continue

            if rec._is_direct_stop_settlement_payment():
                rec._check_direct_stop_settlement_payment_rules()
                continue

            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed"))
            target_label = rec._get_target_label()

            if rec.amount < 0:
                raise ValidationError(_("Payment amount cannot be negative."))

            if rec.collection_type in ("defer_date", "next_visit") and rec.payment_mode != "deferred":
                raise ValidationError(_("Deferred scenarios must use payment mode Deferred."))

            if rec.collection_type in ("full", "partial") and rec.payment_mode == "deferred":
                raise ValidationError(_("Deferred payment mode is only allowed for defer-to-date or next-visit scenarios."))

            rec._validate_cheque_details()
            rec._validate_deferred_collection_plan()

            if rec.collection_type == "full":
                if due <= 0:
                    raise ValidationError(_("There is no remaining due amount on this %s.") % target_label)
                if rec.amount <= 0:
                    raise ValidationError(_("Full payment amount must be greater than zero."))
                if rec.amount > due:
                    raise ValidationError(_("Full payment cannot be more than the remaining due amount."))

            elif rec.collection_type == "partial":
                if due <= 0:
                    raise ValidationError(_("There is no remaining due amount on this %s.") % target_label)
                if rec.amount <= 0:
                    raise ValidationError(_("Partial payment amount must be greater than zero."))
                if rec.amount >= due:
                    raise ValidationError(
                        _("Partial payment must be less than the remaining due amount. Use Full Payment instead.")
                    )
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promised unpaid amount."))
                if not rec.promise_date:
                    raise ValidationError(_("Please set the promise to pay date for the carried-forward balance."))
                if not rec.note:
                    raise ValidationError(_("Please add a note for the carried-forward balance."))

            elif rec.collection_type == "defer_date":
                if rec.amount != 0:
                    raise ValidationError(_("Deferred payment to a specific date must have amount = 0."))
                if not rec.due_date:
                    raise ValidationError(_("Please set the deferred due date."))
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promise to pay amount."))
                if not (rec.promise_date or rec.due_date):
                    raise ValidationError(_("Please set the promise to pay date."))
                if not rec.note:
                    raise ValidationError(_("Please add a note explaining the deferment."))

            elif rec.collection_type == "next_visit":
                if rec.amount != 0:
                    raise ValidationError(_("Carry to next visit must have amount = 0."))
                if rec.due_date:
                    raise ValidationError(_("Do not set a due date when carrying payment to the next visit."))
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promise to pay amount."))
                if not rec.promise_date:
                    raise ValidationError(_("Please set the promise to pay date for the next visit."))
                if not rec.note:
                    raise ValidationError(_("Please add a note explaining why payment is carried to next visit."))

    def action_confirm(self):
        for rec in self:
            # Re-sync draft promise values against the latest remaining due before confirmation.
            # This prevents stale draft values from keeping an outdated promise amount when
            # visit totals changed after the draft was first saved.
            if rec.source_type == "visit" and not rec._is_direct_stop_settlement_payment():
                rec._sync_promise_fields()
            rec._check_payment_rules()
            rec.state = "confirmed"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"

    def unlink(self):
        for rec in self:
            if rec.state == "confirmed":
                raise ValidationError(_("You cannot delete a confirmed payment."))
        return super().unlink()

