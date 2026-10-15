from odoo import fields, models


class TeamLocationHistory(models.Model):
    """One GPS position sample recorded for a field operation team.

    Rows are appended by the GPS tracking controller and only ever grow: there
    is no retention or purge policy, so the table grows without bound (roughly
    a few hundred rows per active team per day). Cleaning it up is a deployment
    concern handled outside this module.
    """

    _name = "team.location.history"
    _description = "GPS Location History"
    _order = "timestamp desc"

    team_id = fields.Many2one(
        "field.operation.team", required=True, ondelete="cascade", index=True
    )
    latitude = fields.Float(digits=(10, 7), required=True)
    longitude = fields.Float(digits=(10, 7), required=True)
    accuracy = fields.Float()
    timestamp = fields.Datetime(default=fields.Datetime.now, index=True)
    battery_level = fields.Integer()
