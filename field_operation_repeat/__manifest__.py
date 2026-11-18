{
    "name": "Field Operation Repeat",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Recurring field operations: wizard, series and rescheduling",
    "description": """
Field Operation Repeat
======================

The recurrence layer of the field operation suite: it ships the recurring
operation wizard (``service.repeat.wizard``), turns a service into the source of
a series and keeps the series aligned when the plan is re-arranged.

Features
--------
* ``parent_id`` / ``child_ids``: a service can be the source of recurring
  periods, each period is a normal ``field.operation``.
* Rescheduling a period (calendar drag & drop included) moves the later
  periods of the same series by the same number of whole days.
* Executed periods (done / cancelled) are never moved, and moving one of them
  never reschedules the future.
* Conflicts of the moved periods are reported as a warning (bus toast and
  chatter) instead of blocking the move; services outside a series keep the
  blocking guard of the core module.
* The core recurrence wizard is extended with an optional source service: the
  customer, address, team, price, tags, description, time of day and duration
  can be copied from it, the new periods can be linked to it, and dates that
  already have a period can be skipped.

The module carries no client specific data: per customer wording, labels and
extra fields belong to the customer overlay module that depends on this one.
""",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "license": "AGPL-3",
    "sequence": 122,
    "depends": [
        "field_operation",
        # ``bus``: the series move reports its conflicts with a toast.
        "bus",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/field_operation_view.xml",
        "wizard/service_repeat_wizard_view.xml",
        "wizard/service_repeat_wizard_view_source.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
