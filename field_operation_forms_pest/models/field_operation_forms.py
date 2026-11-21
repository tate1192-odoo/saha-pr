from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationForms(models.Model):
    _inherit = "field.operation.forms"

    @api.model
    def _default_picking_transfer(self):
        return self.env["stock.picking.type"].search(
            [
                ("warehouse_id.company_id", "=", self.env.company.id),
                ("code", "=", "outgoing"),
            ],
            limit=1,
        )

    @api.model
    def _default_location_id(self):
        company_user = self.env.user.company_id
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company_user.id)], limit=1
        )
        if warehouse:
            return warehouse.lot_stock_id.id

    @api.model
    def _default_out_location_id(self):
        company_id = self.env.context.get("default_company_id") or self.env.company.id
        return self.env["stock.location"].search(
            [("usage", "=", "customer"), ("company_id", "in", [company_id, False])],
            limit=1,
        )

    # Biocidal application details belong to the operation; the form shows and
    # edits the operation values so both documents stay in sync.
    hygiene = fields.Boolean(related="operation_id.hygiene", readonly=False)
    infestation = fields.Boolean(related="operation_id.infestation", readonly=False)
    insulation = fields.Boolean(related="operation_id.insulation", readonly=False)
    storage = fields.Boolean(related="operation_id.storage", readonly=False)
    efk_ift = fields.Boolean(related="operation_id.efk_ift", readonly=False)
    monitors = fields.Boolean(related="operation_id.monitors", readonly=False)
    others = fields.Boolean(related="operation_id.others", readonly=False)
    residence = fields.Char(related="operation_id.residence", readonly=False)
    place = fields.Char(related="operation_id.place", readonly=False)
    application_method = fields.Char(
        related="operation_id.application_method", readonly=False
    )
    security_precautions = fields.Html(
        related="operation_id.security_precautions", readonly=False
    )
    responsible_manager_id = fields.Many2one(
        related="operation_id.responsible_manager_id", readonly=False
    )
    application_place = fields.Selection(
        related="operation_id.application_place", readonly=False
    )
    pest_type_ids = fields.Many2many(
        related="operation_id.pest_type_ids", readonly=False, string="Pest Type"
    )

    pesticide_ids = fields.One2many(
        "field.operation.pesticide", "forms_id", string="Pesticide Product"
    )

    # Picking & Locations
    stock_picking_id = fields.Many2one("stock.picking", copy=False)
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Operation Type",
        copy=True,
        readonly=False,
        store=True,
        default=_default_picking_transfer,
        required=True,
        check_company=True,
        index=True,
    )
    source_location_id = fields.Many2one(
        "stock.location", string="Source Location", default=_default_location_id
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        default=_default_out_location_id,
    )

    picking_count = fields.Integer(
        compute="_compute_picking_count", string="Delivery Orders"
    )

    def _prepare_pest_operation_vals(self, service_type, overrides=None):
        self.ensure_one()
        overrides = overrides or {}

        def pick(key, value):
            return overrides[key] if key in overrides else value

        return {
            "subject": pick("subject", self.subject),
            "description": pick("description", self.description),
            "solution": pick("solution", self.solution),
            "service_type_id": service_type.id,
            "start_date": pick("start_date", self.start_date),
            "end_date": pick("end_date", self.end_date),
            "partner_id": pick("customer_id", self.customer_id.id),
            "contact_id": pick("contact_id", self.contact_id.id),
            "address_id": pick("address_id", self.address_id.id),
            "user_id": pick("user_id", self.user_id.id),
            "team_id": pick("team_id", self.team_id.id),
            "team_leader_id": pick("team_leader_id", self.team_leader_id.id),
            "company_id": pick("company_id", self.company_id.id) or self.env.company.id,
            "person_ids": pick("person_ids", [Command.set(self.person_ids.ids)]),
        }

    def _ensure_pest_operation(self):
        """Return the operation of this form, creating it when the form was
        entered directly in the service-form screen."""
        self.ensure_one()
        if self.operation_id:
            return self.operation_id

        service_type = self.service_type_id or self.env["field.operation.type"].search(
            [("type", "=", "pest")], limit=1
        )
        operation = self.env["field.operation"].create(
            self._prepare_pest_operation_vals(service_type)
        )
        self.operation_id = operation
        if self.customer_signature:
            operation.write(
                {
                    "form_signature": self.customer_signature,
                    "signed_by": self.customer_signed_by,
                    "signed_on": self.signed_on,
                }
            )
        if self.staff_signature:
            operation.write(
                {
                    "staff_signature": self.staff_signature,
                    "staff_signed_by": self.staff_signed_by,
                }
            )
        return operation

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("service_type_id") and not vals.get("operation_id"):
                service_type = self.env["field.operation.type"].browse(
                    vals["service_type_id"]
                )
                if service_type.type == "pest":
                    operation = self.env["field.operation"].create(
                        {
                            "subject": vals.get("subject"),
                            "description": vals.get("description"),
                            "solution": vals.get("solution"),
                            "service_type_id": service_type.id,
                            "start_date": vals.get("start_date"),
                            "end_date": vals.get("end_date"),
                            "partner_id": vals.get("customer_id"),
                            "contact_id": vals.get("contact_id"),
                            "address_id": vals.get("address_id"),
                            "user_id": vals.get("user_id"),
                            "team_id": vals.get("team_id"),
                            "team_leader_id": vals.get("team_leader_id"),
                            "company_id": vals.get("company_id") or self.env.company.id,
                        }
                    )
                    if vals.get("person_ids"):
                        operation.write({"person_ids": vals["person_ids"]})
                    vals["operation_id"] = operation.id
        return super().create(vals_list)

    def write(self, vals):
        old_operations = (
            {form.id: form.operation_id.id for form in self}
            if "operation_id" in vals
            else {}
        )
        if vals.get("service_type_id"):
            service_type = self.env["field.operation.type"].browse(
                vals["service_type_id"]
            )
            if service_type.type == "pest":
                for form in self:
                    if not form.operation_id:
                        form.operation_id = self.env["field.operation"].create(
                            form._prepare_pest_operation_vals(
                                service_type, overrides=vals
                            )
                        )
        result = super().write(vals)
        if "operation_id" in vals:
            for form in self:
                if old_operations.get(form.id) != form.operation_id.id:
                    form.pesticide_ids.write({"operation_id": form.operation_id.id})
        return result

    @api.depends("stock_picking_id")
    def _compute_picking_count(self):
        for form in self:
            form.picking_count = 1 if form.stock_picking_id else 0

    def action_transfer(self):
        """Create the delivery order carrying the pesticide lines of this form."""
        self.ensure_one()
        if not self.env.user.has_group("field_operation_forms.forms_user"):
            raise AccessError(_("You are not allowed to create the delivery order."))
        if not self.pesticide_ids:
            raise UserError(_("Add at least one pesticide line before the transfer."))
        if self.source_location_id == self.destination_location_id:
            raise UserError(
                _("Source and destination locations are the same: change one of them.")
            )
        picking = (
            self.env["stock.picking"]
            .sudo()
            .create(
                {
                    "partner_id": self.customer_id.id,
                    "picking_type_id": self.picking_type_id.id,
                    "location_id": self.source_location_id.id,
                    "location_dest_id": self.destination_location_id.id,
                    "origin": self.name,
                    "field_operation_form_id": self.id,
                    "move_ids": [
                        Command.create(
                            {
                                "product_id": line.product_id.id,
                                "product_uom": line.product_uom.id,
                                "product_uom_qty": line.product_qty,
                                "picked": True,
                                "location_id": self.source_location_id.id,
                                "location_dest_id": self.destination_location_id.id,
                            }
                        )
                        for line in self.pesticide_ids
                    ],
                }
            )
        )
        picking.action_confirm()
        self.stock_picking_id = picking
        return True

    def action_view_picking(self):
        """Open the delivery order created from this form."""
        self.ensure_one()
        if not self.stock_picking_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": self.stock_picking_id.display_name,
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.stock_picking_id.id,
            "type": "ir.actions.act_window",
        }
