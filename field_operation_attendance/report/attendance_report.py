from odoo import api, models


class ReportAttendance(models.AbstractModel):
    _name = "report.field_operation_attendance.report_attendance"
    _description = "Field Operation Attendance Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["field.operation.attendance.wizard"].browse(docids)
        if data is None:
            data = {}
        if "employees" not in data:
            data = docs[:1].get_attendance_data()
        return {
            "docs": docs,
            "data": data,
        }
