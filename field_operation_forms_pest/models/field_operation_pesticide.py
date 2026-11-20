from odoo import api, fields, models


class FieldOperationPesticide(models.Model):
    _inherit = "field.operation.pesticide"

    forms_id = fields.Many2one(
        "field.operation.forms",
        string="Forms",
        index=True,
        ondelete="set null",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("forms_id") and not vals.get("operation_id"):
                form = self.env["field.operation.forms"].browse(vals["forms_id"])
                vals["operation_id"] = form._ensure_pest_operation().id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("forms_id") and not vals.get("operation_id"):
            form = self.env["field.operation.forms"].browse(vals["forms_id"])
            vals["operation_id"] = form._ensure_pest_operation().id
        return super().write(vals)
