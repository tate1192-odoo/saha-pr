{
    "name": "Field Operation Map",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Map and Route functionality for Field Operation",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "base_geolocalize",
        # soft_web_map registers the leaflet_map view type; it lives in
        # apps/soft/soft_web_map and is not part of this repository.
        "soft_web_map",
    ],
    "data": [
        "views/field_operation_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "uninstall_hook": "uninstall_hook",
}
