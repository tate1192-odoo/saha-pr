# Field Operation Attendance Report

> Monthly per-employee work schedule (timesheet view) derived from field service
> jobs — wizard, PDF report and Excel/CSV export.
> Softteknik Bilişim · Odoo 19 · AGPL-3 · version `19.0.1.1.0`
> Module: `apps/saha_legacy/field_operation_attendance` · 19 files · 1 new
> model (TransientModel) + 1 report model (AbstractModel)

This document is derived from the module source (manifest + wizard + report +
views + tests + i18n). Business rules that have no evidence in the code are
marked `<!-- TO BE FILLED -->`.

## 1. Overview

For the selected month/year it builds a per-employee day matrix from **field
jobs** (`field.operation`): how many jobs each employee did on which day, the
total job count, the total hours and the worked-day counts.

- **Data source:** `field.operation` records with `status = 'done'` whose
  interval overlaps the chosen month, and their `person_ids` (`hr.employee`)
  assignments (`get_attendance_data`). The lookup is `sudo()`-ed with an
  explicit `company_id` filter so the totals do not depend on the record rules
  of the user running the report.
- **Wizard (`field.operation.attendance.wizard`):** month, year, employee
  selection (empty = every active employee of the company), `count_date_range`
  (count every day between the job start and end dates, otherwise only the start
  day) and `theme` (light/dark).
- **PDF:** landscape A4 report (`action_report_attendance` →
  `field_operation_attendance.report_attendance`); for every day of the month a
  day number and short weekday name, weekend highlighting, per-employee
  **weekday / weekend / total** day counts, hours and a signature column, plus a
  totals row.
- **Excel/CSV:** `action_export_xlsx` — produces XLSX when `xlsxwriter` is
  installed, otherwise (or on an `XlsxWriterException`) falls back to CSV; the
  output is an `ir.attachment` exposed through
  `/web/content/<id>?download=true`.
- **Menu and button:** Reporting → **Monthly Work Schedule**; the wizard action
  is also available from the `field.operation` cog menu for the report group
  (see §4).

Out of scope: `hr.attendance` (check-in/check-out) is never used; there is no
leave, overtime or shift accounting. The "attendance" in the module name is a
**timesheet** ("puantaj") view; it does not exchange data with the Odoo
Attendance app.

<!-- TO BE FILLED: should a "worked day" be counted as a business day or a calendar day for labour/timesheet purposes? -->

## 2. Dependencies

| Module | Why |
|---|---|
| `field_operation` | `field.operation` (job + `person_ids` + `start_date` + `end_date` + `total_work` + `status` + `company_id`), the `field_operation.service_group_user` group and the `menu_field_operation_reports` menu, `model_field_operation` (action binding) |
| `hr` | `hr.employee` roster and `job_title` |

Python: `xlsxwriter` is used by `action_export_xlsx` behind a `try/except
ImportError` and is **declared** in the manifest as an `external_dependencies`
entry (`{'python': ['xlsxwriter']}`); when it is missing the export silently
falls back to CSV. Timezone conversion uses `pytz`, which ships with Odoo core.

## 3. Models

| Model | `_description` | File |
|---|---|---|
| `field.operation.attendance.wizard` | Monthly Attendance Report Wizard | `wizard/attendance_report_wizard.py` (TransientModel) |
| `report.field_operation_attendance.report_attendance` | Field Operation Attendance Report | `report/attendance_report.py` (AbstractModel) |

Wizard fields: `month` (Selection, 12 months, default = current month), `year`
(Selection, `current year - 2 … + 4`), `employee_ids` (`hr.employee`,
`active=True` domain), `count_date_range` (default `False`), `theme`
(`light`/`dark`, default `light`). There is no `@api.constrains`; validation is
performed inside `_get_date_range` (month 1-12, year 2000-2100) and raises a
`UserError` on an invalid value.

The report model `_get_report_values` calls `docs[:1].get_attendance_data()`
when `data` is empty.

### 3.1 `get_attendance_data()` contract (`data` dict)

| Key | Type | Meaning |
|---|---|---|
| `employees` | list[dict] | one entry per employee, sorted by name |
| `month_name` | str | translated month label (e.g. `March`) |
| `year` | int | selected year |
| `days_in_month` | int | number of days in the month |
| `day_headers` | list[dict] | `{'day': 1..N, 'weekday': 'Mon'..'Sun', 'is_weekend': bool}` |
| `totals` | dict | `days` (per-day counts), `total_jobs`, `total_hours`, `work_days`, `weekend_days`, `total_days` |
| `theme` | str | `light` or `dark` |

Each entry of `employees` carries: `employee_id`, `employee_name`, `job_title`,
`days` (`{'1': 0/1, …}`), `total_jobs`, `total_hours`, and the worked-day
breakdown `work_days` (weekdays), `weekend_days`, `total_days`.

## 4. Roles and Security

ACL (`security/ir.model.access.csv`, single line):

| Model | Group | `perm_read,write,create,unlink` |
|---|---|---|
| `field.operation.attendance.wizard` | `field_operation.service_group_user` | 1,1,1,1 |

- No new group is defined; the `field_operation` groups are reused.
- **No record rule** (the module ships no `ir.rule` file).
- The wizard action bound to `field.operation` carries
  `group_ids = field_operation.service_group_user`, i.e. the same group that
  holds the wizard ACL. Before this the binding was unrestricted: any user able
  to read `field.operation` (for example the **Field Worker** group) saw the
  action in the model cog menu but got an `AccessError` on click, because only
  `service_group_user` is granted the wizard. Restricting `group_ids` keeps the
  visible action aligned with the ACL.
- The report action is **not** bound to any model (see §5): it is launched from
  the wizard only.

## 5. Main Flow

Menu path: **Field Operation → Reporting → Monthly Work Schedule**

| Record | Type | Detail |
|---|---|---|
| `view_attendance_report_wizard_form` | `ir.ui.view` | `form string="Monthly Field Work Schedule"`; footer: Print PDF (`action_print_pdf`), Export Excel (`action_export_xlsx`), Cancel |
| `action_attendance_report_wizard` | `ir.actions.act_window` | `res_model=field.operation.attendance.wizard`, `view_mode=form`, `target=new`, `binding_model_id=model_field_operation`, `group_ids=field_operation.service_group_user` |
| `menu_attendance_report_wizard` | `menuitem` | parent `field_operation.menu_field_operation_reports`, sequence 100 |
| `action_report_attendance` | `ir.actions.report` | `report_name=field_operation_attendance.report_attendance`, `paperformat_id=paperformat_attendance_landscape`, `print_report_name` resolving to `Field_Work_Report_<MonthName>_<Year>.pdf` |

`print_report_name` is rendered with `safe_eval` against `{'object', 'time'}`
only (Odoo `web/controllers/report.py`), so the wizard `data` dict is not
reachable there. The filename therefore resolves the month **label** from the
field definition
(`dict(object.fields_get(['month'])['month']['selection']).get(object.month, object.month)`)
instead of printing the raw selection code (`3`). When the label cannot be
resolved it falls back to the code.

The report action is **not** bound to a model: a `Print` menu entry on a
TransientModel is meaningless (transient records have no print action), and the
report is always launched programmatically from the wizard via `report_action`.

Calculation steps (code order): `_get_date_range` → timezone boundaries
(`_to_utc_boundary`) → `_get_employees` → `field.operation.search`
(`_get_operation_domain`: `status='done'`, company filter, jobs overlapping the
period) → `_initialize_employee_data` → `_process_operations`
(`_get_days_to_count` + `_get_clipped_hours` + `_update_employee_data`) →
`_finalize_employee_data` (sort by name) → `_calculate_totals` →
`_generate_day_headers`.

## 6. Column Mapping

The output layout (PDF/XLSX/CSV) is the same:

| Column | Source |
|---|---|
| Employee (+ a separate Job Title column in CSV/XLSX) | `hr.employee.name`, `hr.employee.job_title` |
| 1..N (days of the month) | `days[str(day)]` → 1/0; XLSX prints `Σ` when worked, CSV prints `X`; the weekend columns get a distinct format |
| Weekdays | `work_days` — worked days falling on Monday-Friday |
| Weekend | `weekend_days` — worked days falling on Saturday/Sunday |
| Total Days | `total_days` = `work_days` + `weekend_days` (days with at least one job) |
| Jobs | `total_jobs` — number of jobs assigned to the employee |
| Hours | `total_hours` — sum of `field.operation` durations **clipped to the period**, 1 decimal |
| Signature | empty signature column (the code does not fill it) |

### 6.1 Weekend marking

`_generate_day_headers` produces one header per day with `is_weekend` set from
`.weekday() >= 5`. The report marks weekend days in the header (day-number and
weekday cells use the `weekend-header` CSS class driven by `is_weekend`) and
paints weekend result cells with `weekend-cell`. The employee row additionally
splits the worked days into **Weekdays / Weekend / Total** so payroll can tell
ordinary days from weekend work; the legend documents the colours.

### 6.2 Period clipping

Jobs may span more than one month. Both the counted days and the counted hours
are **intersected with the reported period**:

- `_get_days_to_count` matches the real interval
  `max(first_day, work_start) … min(last_day, work_end)` and returns that range
  of day numbers, so a February→March job only contributes March's days to the
  March report.
- `_get_clipped_hours` returns
  `(min(end, period_end) - max(start, period_start)) / 3600`, so the hours also
  belong to the reported month only.
- `_get_operation_domain` selects every job overlapping the period (start inside
  the period, or end inside the period, or spanning the whole period), not only
  jobs starting within the month.

The period boundaries are built in the user timezone and converted to naive UTC
(`_to_utc_boundary`) to mirror `field.operation`'s UTC storage.

## 7. Search Filters

None — the wizard is a form action and defines no list/search view. Filtering is
done with the wizard fields (`month`, `year`, `employee_ids`,
`count_date_range`). The data query has a fixed status filter:
`_get_status_domain()` → `[('status', '=', 'done')]`.

## 8. i18n

- `i18n/field_operation_attendance.pot` and `i18n/tr.po`: **59 entries** each,
  all translated in `tr.po`; project header `Odoo Server 19.0`; no compiled
  `tr.mo` is shipped.
- The translatable surface is the wizard `_()` texts (month names,
  `Mon..Sun`, the two `UserError` messages), the field labels/help/selection
  labels, the view strings and the report template (including the **Signature**
  column, the **Legend** block and the `count_date_range` help).
- **New / changed registrations** in this revision: `Signature`, `Weekdays`,
  `Total Days` report columns; the "Legend" block and the `count_date_range`
  help were added to the `.pot` (they previously existed only in `tr.po`); the
  dead `xlsxwriter library is not installed …` entry was removed and the header
  bumped from `Odoo Server 18.0` to `19.0`.
- Validation: both files parse with `polib` (`polib.pofile`) and `tr.po`
  compiles to a readable `.mo`.

## 9. Test Coverage

`tests/test_attendance_report_wizard.py` — `TestAttendanceReportWizard(TransactionCase)`.
The suite exercises the wizard (defaults, `_month_selection`/`_year_selection`,
`_get_date_range` valid/invalid month and year, `_get_employees`,
`_get_status_domain`, `_initialize_employee_data`, `_generate_day_headers`,
`_calculate_totals`, `_get_days_to_count`, `_update_employee_data`,
`_finalize_employee_data`, `_process_operations`, the PDF/export action return
types, the attachment helpers and the CSV fallback).

**Known gaps (honest):** the tests are largely mock/unit level — `action_print_pdf`
does **not** render the real report (no `_render_qweb_pdf` / QWeb template test
exists), so the report template is verified only by inspection, not by an actual
render. The wizard belongs to a separate work-stream; this document does not
claim test coverage for behaviour changed outside the report/view/i18n layer.

## 10. Developer Notes

- **No migration:** there is no `migrations/` directory.
- **No cron.** `report/report_menu.xml` defines only the report record
  (`action_report_attendance`).
- **Data file:** the single data file is `data/paperformat.xml`
  (`noupdate="1"`), defining `paperformat_attendance_landscape` (A4, landscape,
  90 dpi). The v18-era `default=True` field was removed — it is not read in
  Odoo 19 (the paper format is selected through `paperformat_id` on the report).
- **Report body:** `report/attendance_report.xml` → `template id="report_attendance"`,
  `t-call="web.basic_layout"`, helper CSS classes `attendance-table`,
  `worked-cell`, `weekend-cell`, `total-row`, `legend-*`; prints "No data
  available" when the data dict is empty. The template renders only the keys the
  wizard actually produces (`employees`, `month_name`, `year`, `day_headers`,
  `totals`, `theme`); the previously unused `days_in_month` local and the dead
  `team_name`/`day_details` data were dropped.
- **XLSX/CSV layout note:** the XLSX/CSV writers keep their own column set
  (`Days` = `total_days`, `Jobs`, `Hours`); the PDF splits the day count into
  `Weekdays`/`Weekend`/`Total Days`.
- **i18n:** see §8.
- **Static:** `static/description/` holds `icon.png`, `icon.svg`, `index.html`.
