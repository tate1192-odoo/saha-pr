# Copyright(C) 2025 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    # Machine Master Relation
    machine_id = fields.Many2one("machine.master", string="Machine", tracking=True)

    # Machine Details (from master - related fields for quick access)
    machine_display_name = fields.Char(
        string="Machine Name", related="machine_id.display_name", store=True
    )
    machine_product = fields.Char(
        string="Machine Model", related="machine_id.machine_model", store=True
    )
    machine_option = fields.Char(
        string="Machine Option", related="machine_id.machine_option", store=True
    )
    machine_control_unit = fields.Char(
        string="Machine Control Unit", related="machine_id.control_unit", store=True
    )
    control_unit_serial = fields.Char(
        string="Control Unit Serial",
        related="machine_id.control_unit_serial",
        store=True,
    )
    machine_year = fields.Char(
        string="Machine Year", related="machine_id.machine_year", store=True
    )
    machine_serial = fields.Char(
        string="Machine Serial No", related="machine_id.serial_number", store=True
    )

    # Fault Information
    alarm_number = fields.Char(string="Alarm Number")
    machine_fault = fields.Text(string="Fault Description")

    # Warranty & Insurance (from master - related fields)
    start_warranty_date = fields.Date(
        string="Start Warranty", related="machine_id.start_warranty_date", store=True
    )
    end_warranty_date = fields.Date(
        string="End Warranty", related="machine_id.end_warranty_date", store=True
    )
    warranty_status = fields.Selection(
        string="Warranty Status", related="machine_id.warranty_status", store=True
    )

    machine_warranty = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        tracking=True,
        string="Warranty State",
        compute="_compute_machine_warranty",
        store=True,
    )
    machine_insurance = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        tracking=True,
        string="Insurance State",
        compute="_compute_machine_insurance",
        store=True,
    )

    # Spare Parts from this operation
    spare_part_ids = fields.One2many(
        "machine.spare.part", "operation_id", string="Spare Parts Used"
    )
    spare_part_count = fields.Integer(
        string="Spare Part Count", compute="_compute_spare_part_count"
    )
    spare_part_total = fields.Float(
        string="Spare Parts Total", compute="_compute_spare_part_total"
    )

    @api.depends("warranty_status")
    def _compute_machine_warranty(self):
        for rec in self:
            if rec.warranty_status == "active":
                rec.machine_warranty = "yes"
            else:
                rec.machine_warranty = "no" if rec.warranty_status else False

    @api.depends("machine_id")
    def _compute_machine_insurance(self):
        for rec in self:
            if rec.machine_id and rec.machine_id.insurance_status == "active":
                rec.machine_insurance = "yes"
            elif rec.machine_id:
                rec.machine_insurance = "no"
            else:
                rec.machine_insurance = False

    def _compute_spare_part_count(self):
        for rec in self:
            rec.spare_part_count = len(rec.spare_part_ids)

    def _compute_spare_part_total(self):
        for rec in self:
            rec.spare_part_total = sum(rec.spare_part_ids.mapped("subtotal"))

    # Actions
    def action_view_spare_parts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Spare Parts Used"),
            "res_model": "machine.spare.part",
            "view_mode": "list,form",
            "domain": [("operation_id", "=", self.id)],
            "context": {
                "default_operation_id": self.id,
                "default_machine_id": self.machine_id.id if self.machine_id else False,
            },
        }

    def action_add_spare_part(self):
        """Open wizard to add spare parts"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Spare Parts"),
            "res_model": "machine.spare.part.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_machine_id": self.machine_id.id if self.machine_id else False,
                "default_operation_id": self.id,
            },
        }

    def action_view_machine(self):
        self.ensure_one()
        if not self.machine_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Machine"),
            "res_model": "machine.master",
            "view_mode": "form",
            "res_id": self.machine_id.id,
        }
