{
    "name": "Field Operation Attendance Report",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Monthly field operation attendance report for employees",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 125,
    "depends": [
        "field_operation",
        "hr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/paperformat.xml",
        "views/attendance_report_wizard.xml",
        "report/report_menu.xml",
        "report/attendance_report.xml",
    ],
    "demo": [],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
