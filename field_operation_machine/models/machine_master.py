# Copyright(C) 2025 - Today Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
from datetime import date, timedelta
from io import BytesIO

import qrcode

from odoo import _, api, fields, models


class MachineMaster(models.Model):
    _name = "machine.master"
    _description = "Machine Master"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc"

    name = fields.Char(string="Machine Name", required=True, tracking=True)
    display_name = fields.Char(
        string="Display Name", compute="_compute_display_name", store=True
    )
    product_id = fields.Many2one("product.template", string="Product", tracking=True)
    product_code = fields.Char(
        string="Product Code", related="product_id.default_code", store=True
    )
    machine_model = fields.Char(string="Model", tracking=True)
    machine_brand = fields.Char(string="Brand", tracking=True)
    machine_option = fields.Char(string="Option/Variant")
    machine_year = fields.Char(string="Manufacturing Year")
    serial_number = fields.Char(
        string="Serial Number", copy=False, tracking=True, index=True
    )
    barcode = fields.Char(string="Barcode", copy=False, index=True)
    control_unit = fields.Char(string="Control Unit")
    control_unit_serial = fields.Char(string="Control Unit Serial")
    qr_code = fields.Binary(
        string="QR Code", compute="_compute_qr_code", store=True, attachment=True
    )
    qr_data = fields.Char(string="QR Data", compute="_compute_qr_data", store=True)
    partner_id = fields.Many2one(
        "res.partner", string="Customer", tracking=True, index=True
    )
    installation_date = fields.Date(string="Installation Date")
    location = fields.Char(string="Location")
    start_warranty_date = fields.Date(string="Warranty Start Date", tracking=True)
    end_warranty_date = fields.Date(string="Warranty End Date", tracking=True)
    warranty_days_left = fields.Integer(
        string="Warranty Days Left", compute="_compute_warranty_status", store=True
    )
    warranty_status = fields.Selection(
        [("active", "Active"), ("expired", "Expired"), ("none", "No Warranty")],
        string="Warranty Status",
        compute="_compute_warranty_status",
        store=True,
    )
    insurance_company = fields.Char(string="Insurance Company")
    insurance_policy_no = fields.Char(string="Policy Number")
    start_insurance_date = fields.Date(string="Insurance Start Date")
    end_insurance_date = fields.Date(string="Insurance End Date")
    insurance_days_left = fields.Integer(
        string="Insurance Days Left", compute="_compute_insurance_status", store=True
    )
    insurance_status = fields.Selection(
        [("active", "Active"), ("expired", "Expired"), ("none", "No Insurance")],
        string="Insurance Status",
        compute="_compute_insurance_status",
        store=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("maintenance", "Under Maintenance"),
            ("inactive", "Inactive"),
            ("scrapped", "Scrapped"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    active = fields.Boolean(default=True)
    operation_ids = fields.One2many(
        "field.operation", "machine_id", string="Service Operations"
    )
    operation_count = fields.Integer(
        string="Operation Count", compute="_compute_operation_count"
    )
    maintenance_ids = fields.One2many(
        "machine.maintenance", "machine_id", string="Maintenance Records"
    )
    maintenance_count = fields.Integer(
        string="Maintenance Count", compute="_compute_maintenance_count"
    )
    spare_part_ids = fields.One2many(
        "machine.spare.part", "machine_id", string="Spare Parts"
    )
    spare_part_count = fields.Integer(
        string="Spare Part Count", compute="_compute_spare_part_count"
    )
    note = fields.Html(string="Notes")
    document_ids = fields.One2many("machine.document", "machine_id", string="Documents")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )

    @api.depends("name", "machine_model", "serial_number")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.name:
                parts.append(rec.name)
            if rec.machine_model:
                parts.append(f"({rec.machine_model})")
            if rec.serial_number:
                parts.append(f"[{rec.serial_number}]")
            rec.display_name = " ".join(parts) if parts else rec.name or ""

    @api.depends("serial_number", "barcode", "name")
    def _compute_qr_data(self):
        for rec in self:
            data = (
                f"MACHINE:{rec.id}|SN:{rec.serial_number or ''}"
                f"|BC:{rec.barcode or ''}|NAME:{rec.name}"
            )
            rec.qr_data = data

    @api.depends("qr_data")
    def _compute_qr_code(self):
        for rec in self:
            if rec.qr_data:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(rec.qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                rec.qr_code = base64.b64encode(buffer.getvalue())
            else:
                rec.qr_code = False

    @api.depends("end_warranty_date")
    def _compute_warranty_status(self):
        today = date.today()
        for rec in self:
            if rec.end_warranty_date:
                days_left = (rec.end_warranty_date - today).days
                rec.warranty_days_left = max(0, days_left)
                rec.warranty_status = "active" if days_left > 0 else "expired"
            else:
                rec.warranty_days_left = 0
                rec.warranty_status = "none"

    @api.depends("end_insurance_date")
    def _compute_insurance_status(self):
        today = date.today()
        for rec in self:
            if rec.end_insurance_date:
                days_left = (rec.end_insurance_date - today).days
                rec.insurance_days_left = max(0, days_left)
                rec.insurance_status = "active" if days_left > 0 else "expired"
            else:
                rec.insurance_days_left = 0
                rec.insurance_status = "none"

    def _compute_operation_count(self):
        for rec in self:
            rec.operation_count = len(rec.operation_ids)

    def _compute_maintenance_count(self):
        for rec in self:
            rec.maintenance_count = len(rec.maintenance_ids)

    def _compute_spare_part_count(self):
        for rec in self:
            rec.spare_part_count = len(rec.spare_part_ids)

    # Actions
    def action_activate(self):
        self.write({"state": "active"})

    def action_maintenance(self):
        self.write({"state": "maintenance"})

    def action_inactive(self):
        self.write({"state": "inactive"})

    def action_scrap(self):
        self.write({"state": "scrapped", "active": False})

    def action_view_operations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Service Operations"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }

    def action_view_maintenance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance Records"),
            "res_model": "machine.maintenance",
            "view_mode": "list,form",
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }

    def action_view_spare_parts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Spare Parts"),
            "res_model": "machine.spare.part",
            "view_mode": "list,form",
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }

    # Cron job for warranty/insurance notifications
    @api.model
    def _cron_notify_expiring_warranties(self):
        """Notify for warranties expiring in 30 days"""
        today = date.today()
        expiry_date = today + timedelta(days=30)

        machines = self.search(
            [
                ("end_warranty_date", "<=", expiry_date),
                ("end_warranty_date", ">=", today),
                ("warranty_status", "=", "active"),
            ]
        )

        for machine in machines:
            machine.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=machine.partner_id.user_id.id or self.env.user.id,
                note=_("Warranty for %s expires on %s")
                % (machine.display_name, machine.end_warranty_date),
            )

    @api.model
    def _cron_notify_expiring_insurance(self):
        """Notify for insurance expiring in 30 days"""
        today = date.today()
        expiry_date = today + timedelta(days=30)

        machines = self.search(
            [
                ("end_insurance_date", "<=", expiry_date),
                ("end_insurance_date", ">=", today),
                ("insurance_status", "=", "active"),
            ]
        )

        for machine in machines:
            machine.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=machine.partner_id.user_id.id or self.env.user.id,
                note=_("Insurance for %s expires on %s")
                % (machine.display_name, machine.end_insurance_date),
            )


class MachineDocument(models.Model):
    _name = "machine.document"
    _description = "Machine Document"

    name = fields.Char(string="Name", required=True)
    document_type = fields.Selection(
        [
            ("manual", "User Manual"),
            ("technical", "Technical Drawing"),
            ("catalog", "Parts Catalog"),
            ("certificate", "Certificate"),
            ("other", "Other"),
        ],
        string="Document Type",
        default="other",
    )
    file = fields.Binary(string="File", required=True)
    file_name = fields.Char(string="File Name")
    machine_id = fields.Many2one("machine.master", string="Machine")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
