# --- field_operation_contract_line.py ---
from odoo import api, fields, models


class FieldOperationContractLine(models.Model):
    _name = "field.operation.contract.line"
    _inherit = ["service.contract.recurring.mixin"]
    _description = "Field Operation Contract Line"
    _order = "sequence,id"

    name = fields.Text(string="Description")
    active = fields.Boolean(related="contract_id.active", store=True, readonly=True)
    sequence = fields.Integer(default=10)
    date_start = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.context_today,
    )
    date_end = fields.Date(string="End Date")
    total_service = fields.Float(string="Total Service")
    price_unit = fields.Float(string="Unit Price")
    discount = fields.Float(string="Discount (%)")
    tax_id = fields.Many2many(
        "account.tax", string="Taxes", domain=[("type_tax_use", "=", "sale")]
    )
    price_subtotal = fields.Monetary(
        compute="_compute_amounts", store=True, string="Subtotal"
    )
    price_tax = fields.Monetary(
        compute="_compute_amounts", store=True, string="Tax Amount"
    )
    price_total = fields.Monetary(
        compute="_compute_amounts", store=True, string="Total"
    )
    display_type = fields.Selection(
        [("line_section", "Section"), ("line_note", "Note")], default=False
    )
    currency_id = fields.Many2one(related="contract_id.currency_id")
    partner_id = fields.Many2one(
        related="contract_id.partner_id", precompute=True, store=True, string="Customer"
    )
    uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id", readonly=False
    )
    service_type_id = fields.Many2one("field.operation.type", string="Type")
    product_id = fields.Many2one(
        "product.product",
        required=False,
        index=True,
        domain="[('type', '=', 'service')]",
        string="Product",
    )
    contract_id = fields.Many2one(
        comodel_name="field.operation.contract",
        string="Contract",
        required=True,
        index=True,
        ondelete="cascade",
    )
    location_id = fields.Many2one("res.partner", string="Location")
    available_location_ids = fields.Many2many(
        "res.partner",
        compute="_compute_available_locations",
        readonly=False,
        store=True,
    )
    generated_occurrences = fields.Integer(string="Generated", default=0, copy=False)
    # default=None is required: without it the mixin's ``default=0`` leaks into
    # the merged field and prevents the compute from ever running (remaining
    # stayed 0, so no recurrence was ever generated).
    remaining_count = fields.Integer(
        string="Remaining",
        compute="_compute_remaining_count",
        readonly=False,
        store=True,
        default=None,
    )

    @api.depends("generated_occurrences", "total_service")
    def _compute_remaining_count(self):
        for line in self:
            line.remaining_count = max(
                0, line.total_service - line.generated_occurrences
            )

    @api.depends("tax_id", "price_unit", "total_service", "discount")
    def _compute_amounts(self):
        """Compute the line subtotal, tax and total (Odoo 19 compliant)."""
        for line in self:
            if line.display_type:
                line.price_subtotal = 0
                line.price_tax = 0
                line.price_total = 0
                continue

            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            currency = line.currency_id or self.env.company.currency_id

            taxes_computation = line.tax_id.compute_all(
                price_unit=price,
                quantity=line.total_service,
                product=line.product_id,
                partner=line.partner_id,
                currency=currency,
            )

            line.price_subtotal = currency.round(taxes_computation["total_excluded"])
            line.price_tax = currency.round(
                taxes_computation["total_included"]
                - taxes_computation["total_excluded"]
            )
            line.price_total = currency.round(taxes_computation["total_included"])

    @api.depends("contract_id.partner_id", "contract_id.location_ids")
    def _compute_available_locations(self):
        for line in self:
            locations = self.env["res.partner"]
            if line.contract_id and line.contract_id.partner_id:
                partner = line.contract_id.partner_id
                locations |= partner
                locations |= partner.child_ids.filtered(
                    lambda p: p.type in ("delivery", "other")
                )
            if line.contract_id and line.contract_id.location_ids:
                locations |= line.contract_id.location_ids
            line.available_location_ids = locations

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("display_type"):
                # Sections/notes still carry a NOT NULL date_start on the
                # column: fall back to the contract start (or today).
                if not vals.get("date_start") and vals.get("contract_id"):
                    contract = self.env["field.operation.contract"].browse(
                        vals["contract_id"]
                    )
                    vals["date_start"] = (
                        contract.date_start or fields.Date.context_today(self)
                    )
                continue
            if not vals.get("name"):
                if vals.get("product_id"):
                    product = self.env["product.product"].browse(vals["product_id"])
                    vals["name"] = product.get_product_multiline_description_sale()
                else:
                    vals["name"] = "Service Line"
            if not vals.get("location_id") and vals.get("contract_id"):
                contract = self.env["field.operation.contract"].browse(
                    vals["contract_id"]
                )
                if contract and contract.partner_id:
                    address_dict = contract.partner_id.address_get(["delivery"])
                    vals["location_id"] = address_dict.get("delivery")
        return super().create(vals_list)

    @api.onchange("contract_id")
    def _onchange_contract_id_location(self):
        for line in self:
            if line.contract_id and line.contract_id.partner_id:
                if (
                    not line.location_id
                    or line.location_id not in line.available_location_ids
                ):
                    address_dict = line.contract_id.partner_id.address_get(["delivery"])
                    line.location_id = address_dict.get("delivery")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.get_product_multiline_description_sale()
            self.price_unit = self.product_id.lst_price
            self.uom_id = self.product_id.uom_id
            self.tax_id = self.product_id.taxes_id
