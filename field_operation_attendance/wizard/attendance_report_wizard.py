import base64
import csv
import io
import logging
from calendar import monthrange
from datetime import date, datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

_logger = logging.getLogger(__name__)


class AttendanceReportWizard(models.TransientModel):
    _name = "field.operation.attendance.wizard"
    _description = "Monthly Attendance Report Wizard"

    @api.model
    def _month_selection(self):
        return [
            ("1", _("January")),
            ("2", _("February")),
            ("3", _("March")),
            ("4", _("April")),
            ("5", _("May")),
            ("6", _("June")),
            ("7", _("July")),
            ("8", _("August")),
            ("9", _("September")),
            ("10", _("October")),
            ("11", _("November")),
            ("12", _("December")),
        ]

    @api.model
    def _year_selection(self):
        current_year = fields.Date.context_today(self).year
        return [(str(y), str(y)) for y in range(current_year - 2, current_year + 5)]

    month = fields.Selection(
        "_month_selection",
        string="Month",
        required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    year = fields.Selection(
        "_year_selection",
        string="Year",
        required=True,
        default=lambda self: str(fields.Date.context_today(self).year),
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        domain=[("active", "=", True)],
        help="Leave empty to include every active employee of the company.",
    )

    count_date_range = fields.Boolean(
        string="Count All Days in Range",
        default=False,
        help="If checked, every day between the job start and end dates is "
        "counted as a worked day. If unchecked, only the start day is counted.",
    )

    theme = fields.Selection(
        [("light", "Light Theme"), ("dark", "Dark Theme")],
        string="Theme",
        default="light",
        required=True,
    )

    def _get_date_range(self):
        """Return the first day, last day and length of the selected month."""
        self.ensure_one()
        try:
            month_int = int(self.month)
            year_int = int(self.year)
        except (TypeError, ValueError) as e:
            _logger.warning(
                "Invalid period parameters: month=%r, year=%r", self.month, self.year
            )
            raise UserError(
                _("Invalid date parameters. Please check month and year values.")
            ) from e

        if not 1 <= month_int <= 12 or not 2000 <= year_int <= 2100:
            _logger.warning(
                "Out-of-range period requested: month=%s, year=%s", month_int, year_int
            )
            raise UserError(
                _("Invalid date parameters. Please check month and year values.")
            )

        first_day = date(year_int, month_int, 1)
        days_in_month = monthrange(year_int, month_int)[1]
        last_day = date(year_int, month_int, days_in_month)
        return first_day, last_day, days_in_month

    def _get_status_domain(self):
        return [("status", "=", "done")]

    def _to_utc_boundary(self, day, end_of_day):
        """Return a day's local boundary as a naive UTC datetime.

        ``field.operation`` datetimes are stored in UTC while the period is
        chosen in the user timezone, so the boundaries are built locally then
        converted back, mirroring ``odoo.orm.domains._value_to_datetime``.
        """
        local_boundary = datetime.combine(day, time.max if end_of_day else time.min)
        tz = self.env.tz
        if tz == pytz.utc:
            return local_boundary
        return tz.localize(local_boundary).astimezone(pytz.utc).replace(tzinfo=None)

    def _get_operation_domain(self, period_start, period_end):
        """Return the domain of every done job overlapping the period.

        Only jobs starting inside the month used to be returned, so a job
        spanning two months was dropped from one of them. The real interval is
        matched instead: a job starts before the period ends and ends after it
        begins (a job covering the whole month included; a job without an end
        date is single-day and matched on its start date).

        The search is sudo-ed with an explicit company filter: otherwise the
        record rules of the user running the report change the operations
        returned and two users get different totals for the same month.
        """
        return self._get_status_domain() + [
            ("company_id", "=", self.env.company.id),
            "|",
            "|",
            "&",
            ("start_date", ">=", period_start),
            ("start_date", "<=", period_end),
            "&",
            ("end_date", ">=", period_start),
            ("end_date", "<=", period_end),
            "&",
            ("start_date", "<=", period_start),
            ("end_date", ">=", period_end),
        ]

    def _get_employees(self):
        """Return the employees covered by the report.

        An empty ``employee_ids`` is a deliberate choice: the report then covers
        every active employee of the current company (plus employees shared
        across companies, ``company_id = False``). The lookup is sudo-ed and
        scoped to the company so the roster does not depend on the record rules
        of the user running the report.
        """
        self.ensure_one()
        if self.employee_ids:
            return self.employee_ids
        return (
            self.env["hr.employee"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("company_id", "in", [self.env.company.id, False]),
                ]
            )
        )

    def get_attendance_data(self):
        self.ensure_one()
        first_day, last_day, days_in_month = self._get_date_range()
        period_start = self._to_utc_boundary(first_day, end_of_day=False)
        period_end = self._to_utc_boundary(last_day, end_of_day=True)

        employees = self._get_employees()
        if not employees:
            raise UserError(_("No employees found matching the selected criteria."))

        operations = (
            self.env["field.operation"]
            .sudo()
            .search(self._get_operation_domain(period_start, period_end))
        )

        employee_data = self._initialize_employee_data(employees, days_in_month)
        employee_data = self._process_operations(
            operations, employee_data, first_day, last_day, period_start, period_end
        )

        sorted_employees = self._finalize_employee_data(employee_data)
        totals = self._calculate_totals(sorted_employees, days_in_month)
        day_headers = self._generate_day_headers(days_in_month)

        return {
            "employees": sorted_employees,
            "month_name": dict(self._month_selection()).get(self.month),
            "year": int(self.year),
            "days_in_month": days_in_month,
            "day_headers": day_headers,
            "totals": totals,
            "theme": self.theme,
        }

    def _initialize_employee_data(self, employees, days_in_month):
        employee_data = {}
        for emp in employees:
            employee_data[emp.id] = {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "job_title": emp.job_title or "",
                "days": {str(day): 0 for day in range(1, days_in_month + 1)},
                "total_jobs": 0,
                "work_days": 0,
                "weekend_days": 0,
                "total_days": 0,
                "total_hours": 0.0,
            }
        return employee_data

    def _process_operations(
        self, operations, employee_data, first_day, last_day, period_start, period_end
    ):
        weekend_days = {
            header["day"]
            for header in self._generate_day_headers(last_day.day)
            if header["is_weekend"]
        }
        for operation in operations:
            if not operation.start_date:
                continue

            work_start = operation.start_date.date()
            days_to_count = self._get_days_to_count(
                work_start, operation, first_day, last_day
            )
            hours = self._get_clipped_hours(operation, period_start, period_end)

            for employee in operation.person_ids:
                emp_data = employee_data.get(employee.id)
                if emp_data is not None:
                    self._update_employee_data(emp_data, days_to_count, hours)

        for emp_data in employee_data.values():
            worked_days = [
                int(day) for day, count in emp_data["days"].items() if count > 0
            ]
            emp_data["total_days"] = len(worked_days)
            emp_data["weekend_days"] = sum(
                1 for day in worked_days if day in weekend_days
            )
            emp_data["work_days"] = emp_data["total_days"] - emp_data["weekend_days"]

        return employee_data

    def _get_days_to_count(self, work_start, operation, first_day, last_day):
        """Return the period day numbers a job covers, cut down to the period.

        The job interval is intersected with the reported period on real dates
        instead of day-of-month numbers, so a job spanning two months only
        contributes the days belonging to this one, and an operation running
        from late February into March no longer collapses into the wrong month.
        """
        if not work_start:
            return []

        work_end = work_start
        if self.count_date_range and operation.end_date:
            try:
                work_end = operation.end_date.date()
            except (AttributeError, TypeError, ValueError):
                _logger.warning(
                    "Unreadable end date on operation %s, counting its start day only.",
                    operation.id,
                )

        work_end = max(work_end, work_start)
        start = max(first_day, work_start)
        end = min(last_day, work_end)
        if end < start:
            return []
        return list(range(start.day, end.day + 1))

    def _get_clipped_hours(self, operation, period_start, period_end):
        """Return the hours of a job that fall inside the period.

        The metric follows the counted days: the real ``end - start`` duration
        is cut to the period boundaries, so a job spanning two months only
        contributes the part belonging to the reported month.
        """
        start = operation.start_date
        if not start:
            return 0.0

        end = max(operation.end_date or start, start)
        clipped_start = max(start, period_start)
        clipped_end = min(end, period_end)
        if clipped_end <= clipped_start:
            return 0.0
        return (clipped_end - clipped_start).total_seconds() / 3600.0

    def _update_employee_data(self, emp_data, days_to_count, hours):
        for day in days_to_count:
            day_key = str(day)
            if day_key in emp_data["days"]:
                emp_data["days"][day_key] = 1

        emp_data["total_jobs"] += 1
        emp_data["total_hours"] += hours

    def _finalize_employee_data(self, employee_data):
        return sorted(employee_data.values(), key=lambda x: x["employee_name"])

    def _calculate_totals(self, sorted_employees, days_in_month):
        day_totals = {str(day): 0 for day in range(1, days_in_month + 1)}
        total_jobs = 0
        total_hours = 0.0
        work_days = 0
        weekend_days = 0
        total_days = 0

        for emp_data in sorted_employees:
            for day, count in emp_data["days"].items():
                day_totals[day] += count
            total_jobs += emp_data["total_jobs"]
            total_hours += emp_data["total_hours"]
            work_days += emp_data["work_days"]
            weekend_days += emp_data["weekend_days"]
            total_days += emp_data["total_days"]

        return {
            "days": day_totals,
            "total_jobs": total_jobs,
            "total_hours": total_hours,
            "work_days": work_days,
            "weekend_days": weekend_days,
            "total_days": total_days,
        }

    def _generate_day_headers(self, days_in_month):
        weekday_names = [
            _("Mon"),
            _("Tue"),
            _("Wed"),
            _("Thu"),
            _("Fri"),
            _("Sat"),
            _("Sun"),
        ]
        day_headers = []

        for day in range(1, days_in_month + 1):
            weekday = date(int(self.year), int(self.month), day).weekday()
            day_headers.append(
                {
                    "day": day,
                    "weekday": weekday_names[weekday],
                    "is_weekend": weekday >= 5,
                }
            )

        return day_headers

    def action_print_pdf(self):
        self.ensure_one()
        data = self.get_attendance_data()
        return self.env.ref(
            "field_operation_attendance.action_report_attendance"
        ).report_action(self, data=data)

    def action_export_xlsx(self):
        self.ensure_one()

        if xlsxwriter is None:
            return self._export_csv_fallback()

        try:
            return self._export_with_xlsxwriter()
        except xlsxwriter.exceptions.XlsxWriterException as e:
            _logger.warning("Excel export failed, falling back to CSV: %s", e)
            return self._export_csv_fallback()

    def _export_with_xlsxwriter(self):
        data = self.get_attendance_data()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        formats = self._create_excel_formats(workbook)
        sheet = workbook.add_worksheet(f"{data['month_name']} {data['year']}")

        self._write_excel_header(sheet, data, formats)
        self._write_excel_data(sheet, data, formats)
        self._adjust_excel_columns(sheet, data)

        workbook.close()
        output.seek(0)

        return self._create_excel_attachment(output, data)

    def _create_excel_formats(self, workbook):
        return {
            "header": workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#4a90d9",
                    "font_color": "white",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "subheader": workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#e0e0e0",
                    "border": 1,
                    "align": "center",
                    "font_size": 8,
                }
            ),
            "weekend": workbook.add_format(
                {"bg_color": "#ffdddd", "border": 1, "align": "center"}
            ),
            "worked": workbook.add_format(
                {
                    "bg_color": "#c8e6c9",
                    "border": 1,
                    "align": "center",
                    "bold": True,
                }
            ),
            "cell": workbook.add_format({"border": 1, "align": "center"}),
            "text": workbook.add_format({"border": 1, "align": "left"}),
            "total": workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#e0e0e0",
                    "border": 1,
                    "align": "center",
                }
            ),
            "title": workbook.add_format(
                {"bold": True, "font_size": 14, "align": "center"}
            ),
        }

    def _write_excel_header(self, sheet, data, formats):
        sheet.merge_range(
            0,
            0,
            0,
            data["days_in_month"] + 4,
            f"FIELD WORK REPORT - {data['month_name']} {data['year']}",
            formats["title"],
        )

        row = 3
        sheet.write(row, 0, "Employee", formats["header"])
        for dh in data["day_headers"]:
            sheet.write(row, dh["day"], dh["day"], formats["header"])
        sheet.write(row, data["days_in_month"] + 1, "Days", formats["header"])
        sheet.write(row, data["days_in_month"] + 2, "Jobs", formats["header"])
        sheet.write(row, data["days_in_month"] + 3, "Hours", formats["header"])
        sheet.write(row, data["days_in_month"] + 4, "Signature", formats["header"])

        row += 1
        sheet.write(row, 0, "", formats["subheader"])
        for dh in data["day_headers"]:
            fmt = formats["weekend"] if dh["is_weekend"] else formats["subheader"]
            sheet.write(row, dh["day"], dh["weekday"], fmt)
        for col in range(data["days_in_month"] + 1, data["days_in_month"] + 4):
            sheet.write(row, col, "", formats["subheader"])

    def _write_excel_data(self, sheet, data, formats):
        row = 5

        for emp in data["employees"]:
            self._write_employee_row(sheet, row, emp, data, formats)
            row += 1

        self._write_total_row(sheet, row, data, formats)

    def _write_employee_row(self, sheet, row, employee, data, formats):
        sheet.write(row, 0, employee["employee_name"], formats["text"])

        for dh in data["day_headers"]:
            job_count = employee["days"].get(str(dh["day"]), 0)
            if job_count > 0:
                sheet.write(row, dh["day"], job_count, formats["worked"])
            elif dh["is_weekend"]:
                sheet.write(row, dh["day"], "", formats["weekend"])
            else:
                sheet.write(row, dh["day"], "", formats["cell"])

        sheet.write(
            row, data["days_in_month"] + 1, employee["total_days"], formats["total"]
        )
        sheet.write(
            row, data["days_in_month"] + 2, employee["total_jobs"], formats["total"]
        )
        sheet.write(
            row,
            data["days_in_month"] + 3,
            round(employee["total_hours"], 1),
            formats["total"],
        )
        sheet.write(row, data["days_in_month"] + 4, "", formats["text"])

    def _write_total_row(self, sheet, row, data, formats):
        sheet.write(row, 0, "TOTAL", formats["total"])

        for dh in data["day_headers"]:
            total_count = data["totals"]["days"].get(str(dh["day"]), 0)
            if total_count > 0:
                sheet.write(row, dh["day"], total_count, formats["worked"])
            elif dh["is_weekend"]:
                sheet.write(row, dh["day"], "", formats["weekend"])
            else:
                sheet.write(row, dh["day"], "", formats["cell"])

        sheet.write(
            row,
            data["days_in_month"] + 1,
            data["totals"]["total_days"],
            formats["total"],
        )
        sheet.write(
            row,
            data["days_in_month"] + 2,
            data["totals"]["total_jobs"],
            formats["total"],
        )
        sheet.write(
            row,
            data["days_in_month"] + 3,
            round(data["totals"]["total_hours"], 1),
            formats["total"],
        )
        sheet.write(row, data["days_in_month"] + 4, "", formats["total"])

    def _adjust_excel_columns(self, sheet, data):
        sheet.set_column(0, 0, 25)
        for col in range(1, data["days_in_month"] + 1):
            sheet.set_column(col, col, 4)
        for col in range(data["days_in_month"] + 1, data["days_in_month"] + 4):
            sheet.set_column(col, col, 8)
        sheet.set_column(data["days_in_month"] + 4, data["days_in_month"] + 4, 20)

    def _create_excel_attachment(self, output, data):
        name = f"Field_Work_{data['month_name']}_{data['year']}.xlsx"
        return self._create_attachment(
            name,
            output.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _create_csv_attachment(self, csv_content, data):
        name = f"Field_Work_{data['month_name']}_{data['year']}.csv"
        return self._create_attachment(name, csv_content.encode("utf-8"), "text/csv")

    def _create_attachment(self, name, content, mimetype):
        """Create or refresh the wizard's downloadable attachment.

        Re-using the record instead of inserting a new one on every click keeps
        ``ir.attachment`` from growing without bound; binding it to the wizard
        (``res_model`` / ``res_id``) lets the ORM purge it together with the
        transient record.
        """
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("name", "=", name),
                ],
                limit=1,
            )
        )

        values = {
            "name": name,
            "type": "binary",
            "datas": base64.b64encode(content),
            "mimetype": mimetype,
            "res_model": self._name,
            "res_id": self.id,
        }
        if attachment:
            attachment.write(values)
        else:
            attachment = self.env["ir.attachment"].sudo().create(values)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _export_csv_fallback(self):
        data = self.get_attendance_data()
        output = io.StringIO()
        writer = csv.writer(
            output, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )

        self._write_csv_header(writer, data)
        self._write_csv_data(writer, data)

        csv_content = output.getvalue()
        output.close()

        return self._create_csv_attachment(csv_content, data)

    def _write_csv_header(self, writer, data):
        header = (
            ["Employee", "Job Title"]
            + [str(dh["day"]) for dh in data["day_headers"]]
            + ["Days", "Jobs", "Hours"]
        )
        writer.writerow(header)

        day_names = [dh["weekday"] for dh in data["day_headers"]]
        writer.writerow(["", ""] + day_names)

    def _write_csv_data(self, writer, data):
        for emp in data["employees"]:
            self._write_csv_employee_row(writer, emp, data)

        self._write_csv_total_row(writer, data)

    def _write_csv_employee_row(self, writer, employee, data):
        row = [employee["employee_name"], employee["job_title"]]

        for dh in data["day_headers"]:
            job_count = employee["days"].get(str(dh["day"]), 0)
            row.append("X" if job_count > 0 else "")

        row.extend(
            [
                employee["total_days"],
                employee["total_jobs"],
                round(employee["total_hours"], 1),
            ]
        )
        writer.writerow(row)

    def _write_csv_total_row(self, writer, data):
        total_row = ["TOTAL", ""]

        for dh in data["day_headers"]:
            total_count = data["totals"]["days"].get(str(dh["day"]), 0)
            total_row.append(str(total_count) if total_count > 0 else "")

        total_row.extend(
            [
                data["totals"]["total_days"],
                data["totals"]["total_jobs"],
                round(data["totals"]["total_hours"], 1),
            ]
        )
        writer.writerow(total_row)
