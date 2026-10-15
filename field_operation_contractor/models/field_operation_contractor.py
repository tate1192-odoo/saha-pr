from typing import TYPE_CHECKING

from odoo import api, fields, models

if TYPE_CHECKING:
    from odoo.fields import RecordDict


class FieldOperationContractor(models.Model):
    _name = "field.operation.contractor"
    _description = "Field Operation Contractor"

    name = fields.Char(
        string="Job",
        required=True,
    )
    active = fields.Boolean(default=True)
    contractor_type = fields.Selection(
        [("main", "Main Contractor"), ("sub", "Subcontractor")],
        string="Contractor Type",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contractor",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        required=True,
    )
    description = fields.Text(
        string="Job Description",
    )
    customer_ids = fields.One2many(
        "res.partner",
        "service_contractor_id",
        string="Customers",
    )
    customer_count = fields.Integer(
        compute="_compute_customer_count",
        string="# Customers",
    )

    @api.depends("name", "partner_id")
    def _compute_display_name(self) -> None:
        for job in self:
            partner_name = job.partner_id.name
            job_name = job.name
            if partner_name and job_name:
                job.display_name = f"{partner_name} - {job_name}"
            else:
                job.display_name = partner_name or job_name or ""

    @api.model_create_multi
    def create(self, vals_list: list["RecordDict"]) -> "FieldOperationContractor":
        records = super().create(vals_list)
        records._sync_partner_flag(records.partner_id, True)
        return records

    def write(self, vals: "RecordDict") -> bool:
        partner_changed = "partner_id" in vals
        old_partners = self.partner_id if partner_changed else self.env["res.partner"]
        result = super().write(vals)
        self._sync_partner_flag(self.partner_id, True)
        if partner_changed:
            removed = old_partners - self.partner_id
            self._clear_partner_flag(removed)
        return result

    def unlink(self) -> bool:
        partners = self.partner_id
        result = super().unlink()
        self._clear_partner_flag(partners)
        return result

    def _sync_partner_flag(self, partners, value: bool) -> None:
        """Set ``is_contractor`` on ``partners`` to ``value`` when it differs.

        ``is_contractor`` is a derived system flag, so the user editing a
        contractor job may lack write access on the linked partner (record
        rules or field groups). The write therefore runs as sudo, and only on
        partners whose value actually changes, to skip pointless writes and
        pointless access errors.
        """
        to_update = partners.sudo().filtered(lambda p: p.is_contractor != value)
        if to_update:
            to_update.write({"is_contractor": value})

    def _clear_partner_flag(self, partners) -> None:
        """Unset ``is_contractor`` for partners left without any job.

        Archived jobs count as remaining (``active_test=False``): archiving is
        not deletion, so a partner whose only job is archived is still a
        contractor. A single grouped query collects the remaining jobs of all
        candidate partners at once.
        """
        if not partners:
            return
        groups = (
            self.env["field.operation.contractor"]
            .with_context(
                active_test=False,
            )
            ._read_group(
                [("partner_id", "in", partners.ids)],
                ["partner_id"],
                ["__count"],
            )
        )
        with_jobs = {partner.id for partner, _count in groups}
        self._sync_partner_flag(
            partners.filtered(lambda p: p.id not in with_jobs),
            False,
        )

    @api.depends("customer_ids")
    def _compute_customer_count(self) -> None:
        for record in self:
            record.customer_count = len(record.customer_ids)

    def action_view_customers(self) -> dict:
        self.ensure_one()
        return {
            "name": "Customers",
            "res_model": "res.partner",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            "domain": [("service_contractor_id", "=", self.id)],
            "context": {"default_service_contractor_id": self.id},
        }
