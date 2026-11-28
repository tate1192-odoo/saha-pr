from odoo import api, fields, models
from odoo.exceptions import UserError


class FieldOperationResequenceWizard(models.TransientModel):
    _name = "field.operation.resequence.wizard"
    _description = "Resequence Field Operations"

    total_count = fields.Integer(string="Total Records", readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "total_count" in fields_list:
            self.check_access("create")
            values["total_count"] = self._check_global_access()
        return values

    def _get_sequence(self):
        sequences = (
            self.env["ir.sequence"].sudo().search([("code", "=", "field.operation")])
        )
        if len(sequences) != 1:
            raise UserError(
                self.env._("Exactly one Field Operation sequence is required.")
            )

        sequence = sequences
        if (
            not sequence.active
            or sequence.company_id
            or sequence.use_date_range
            or sequence.number_increment != 1
        ):
            raise UserError(
                self.env._(
                    "The Field Operation sequence must be active, global, "
                    "without date ranges, and use an increment of 1."
                )
            )
        return sequence

    def _check_global_access(self):
        operation_model = self.env["field.operation"].with_context(active_test=False)
        groups = operation_model.sudo()._read_group([], ["company_id"], ["__count"])
        inaccessible = [
            company
            for company, _count in groups
            if company and company not in self.env.companies
        ]
        if inaccessible:
            company_names = ", ".join(company.display_name for company in inaccessible)
            raise UserError(
                self.env._(
                    "Resequencing requires access to every company with field "
                    "operations: %(companies)s",
                    companies=company_names,
                )
            )

        total_count = operation_model.sudo().search_count([])
        if operation_model.search_count([]) != total_count:
            raise UserError(
                self.env._(
                    "Record rules hide some field operations. Resequencing is "
                    "only allowed when every operation is visible."
                )
            )
        return total_count

    def action_resequence(self):
        self.ensure_one()
        self.check_access("write")

        sequence = self._get_sequence()
        sequence.lock_for_update()
        sequence.invalidate_recordset(["number_next_actual"])
        next_number_before = sequence.number_next_actual

        expected_count = self._check_global_access()
        operation_model = self.env["field.operation"].with_context(active_test=False)
        records = operation_model.search([], order="create_date asc, id asc")
        if len(records) != expected_count:
            raise UserError(
                self.env._(
                    "The field operation list changed while the wizard was "
                    "opening. Run the resequence again."
                )
            )

        records.lock_for_update()
        for number, record in enumerate(records, start=1):
            record.write({"name": sequence.get_next_char(number)})

        if operation_model.search_count([]) != expected_count:
            raise UserError(
                self.env._(
                    "A field operation was created during the resequence. "
                    "Run the operation again when the system is idle."
                )
            )

        # Standard PostgreSQL sequences advance outside the transaction. Refuse
        # to reset the counter if another transaction consumed a number.
        sequence.invalidate_recordset(["number_next_actual"])
        if sequence.number_next_actual != next_number_before:
            raise UserError(
                self.env._(
                    "Field Operation numbers were generated concurrently. "
                    "Run the resequence again when the system is idle."
                )
            )

        sequence.write({"number_next": len(records) + 1})
        return {"type": "ir.actions.client", "tag": "reload"}
