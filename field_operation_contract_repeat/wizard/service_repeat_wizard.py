"""Contract source of the shared recurrence wizard.

``field_operation_repeat`` owns the dialog, the recurrence rules and the series
bookkeeping. This overlay only adds the contract: it fills the dialog from the
contract, writes the contract on the generated operations, keeps them one day
long (the Gantt view draws them between start and end) and skips the dates the
contract already has an operation for.
"""

from datetime import timedelta

import pytz

from odoo import _, api, fields, models

#: Status of the pre-generated contract operations.
DEFAULT_STATUS = "draft"


class ServiceRepeatWizard(models.TransientModel):
    _inherit = "service.repeat.wizard"

    contract_id = fields.Many2one(
        "field.operation.contract",
        string="Contract",
        help="Contract the operations are generated for; its scheduling data "
        "fills the dialog.",
    )
    skipped_count = fields.Integer(
        string="Skipped Dates",
        readonly=True,
        help="Number of dates left out by the last run because the contract "
        "already had an operation on them.",
    )

    # ------------------------------------------------------------------
    # Contract defaults
    # ------------------------------------------------------------------

    @api.model
    def _contract_defaults(self, contract):
        """Values the contract imposes on the dialog."""
        values = {
            "contract_id": contract.id,
            "partner_id": contract.partner_id.id,
            "user_id": (contract.user_id or self.env.user).id,
            "company_id": (contract.company_id or self.env.company).id,
            "subject": contract.subject or _("Scheduled Service"),
            "service_type_id": contract.service_type_ids[:1].id,
            "dtstart": contract.date_start or fields.Date.context_today(self),
            "skip_existing": True,
            "generated_status": DEFAULT_STATUS,
        }
        if contract.date_end:
            values.setdefault("rrule_end_type", "until")
            values["rrule_until"] = contract.date_end
        return values

    @api.model_create_multi
    def create(self, vals_list):
        """Fill the required fields of the dialog from its contract.

        An onchange does not run on ``create``, and the customer, the company or
        the subject are required: an RPC or test call creating the wizard with
        only ``contract_id`` used to die on the NOT NULL columns.
        """
        for vals in vals_list:
            if not vals.get("contract_id"):
                continue
            contract = self.env["field.operation.contract"].browse(vals["contract_id"])
            for name, value in self._contract_defaults(contract).items():
                vals.setdefault(name, value)
        return super().create(vals_list)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract_id = self.env.context.get("default_contract_id")
        if not contract_id:
            return res
        contract = self.env["field.operation.contract"].browse(contract_id).exists()
        if not contract:
            return res
        for name, value in self._contract_defaults(contract).items():
            if name in fields_list:
                res[name] = value
        return res

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        """Fill the dialog from the contract the user picks inside it.

        The contract form button hands the contract over in the context, but the
        field stays editable: picking another contract here must fill the same
        values, otherwise the required fields stay empty and the dialog cannot
        be saved.
        """
        if not self.contract_id:
            return
        for name, value in self._contract_defaults(self.contract_id).items():
            setattr(self, name, value)

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    def _planned_local_dates(self):
        """Local dates the contract already has an operation on."""
        self.ensure_one()
        if not self.contract_id:
            return set()
        timezone = self._user_timezone()
        operations = self.env["field.operation"].search(
            [("contract_id", "=", self.contract_id.id), ("start_date", "!=", False)]
        )
        return {
            pytz.utc.localize(operation.start_date).astimezone(timezone).date()
            for operation in operations
        }

    def _prepare_operation_values(self, operation_date):
        contract = self.contract_id
        if not contract:
            return super()._prepare_operation_values(operation_date)
        if self.skip_existing and operation_date.date() in self._planned_local_dates():
            self.skipped_count += 1
            return False
        values = super()._prepare_operation_values(operation_date)
        if not values:
            return values
        values.update(
            {
                "contract_id": contract.id,
                "service_type_id": (
                    self.service_type_id or contract.service_type_ids[:1]
                ).id,
                "status": self.generated_status,
                "start_date": self._local_to_utc(operation_date),
                # A contract operation is a whole day: the Gantt view draws it
                # between start_date and end_date.
                "end_date": self._local_to_utc(operation_date + timedelta(days=1)),
            }
        )
        return values

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def _notification(
        self, title, message, notification_type="warning", next_action=None
    ):
        """Client action showing ``message`` in a notification."""
        params = {
            "title": title,
            "message": message,
            "sticky": False,
            "type": notification_type,
        }
        if next_action:
            params["next"] = next_action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def _log_generation(self, created, skipped):
        """Leave an audit trail on the contract."""
        self.ensure_one()
        body = (
            _("%(created)s recurring operations were generated.") % {"created": created}
            if created
            else _("No new recurring operation was generated.")
        )
        parts = [body]
        if skipped:
            parts.append(
                _("%(skipped)s dates were skipped: an operation already exists.")
                % {"skipped": skipped}
            )
        self.contract_id.message_post(body=" ".join(parts))

    def action_generate_operations(self):
        """Generate the operations, then report the run on the contract."""
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            return super().action_generate_operations()
        self.skipped_count = 0
        Operation = self.env["field.operation"]
        before = Operation.search_count([("contract_id", "=", contract.id)])
        result = super().action_generate_operations()
        created = Operation.search_count([("contract_id", "=", contract.id)]) - before
        self._log_generation(created, self.skipped_count)
        if not created:
            message = (
                _(
                    "%(skipped)s operations already exist for this contract: "
                    "nothing was generated."
                )
                % {"skipped": self.skipped_count}
                if self.skipped_count
                else _(
                    "No operations were generated based on the given recurrence rules."
                )
            )
            return self._notification(_("No Operations Generated"), message)
        if self.skipped_count:
            return self._notification(
                _("Operations Generated"),
                _(
                    "%(created)s operations were generated, %(skipped)s were skipped "
                    "because they already exist for this contract."
                )
                % {"created": created, "skipped": self.skipped_count},
                next_action=result,
            )
        return result
