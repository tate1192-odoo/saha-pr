# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class FieldOperationFormsPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "forms_count" in counters:
            operation_form_model = request.env["field.operation.forms"]
            values["forms_count"] = (
                operation_form_model.search_count([])
                if operation_form_model.has_access("read")
                else 0
            )
        return values

    def _operation_forms_get_page_view_values(
        self, operation_forms, access_token, **kwargs
    ):
        values = {
            "page_name": "operation_forms_detail",
            "operation_forms": operation_forms,
            # The signature modals build their call URL from it; keep a usable value
            # when the page is opened without ?source=, otherwise the URL ends in
            # "/" and never matches the route.
            "source": kwargs.get("source") or "portal",
        }
        return self._get_page_view_values(
            operation_forms,
            access_token,
            values,
            "my_operation_forms_history",
            False,
            **kwargs,
        )

    @http.route(
        ["/my/operation_forms", "/my/operation_forms/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def operation_forms_list_view(
        self, page=1, date_begin=None, date_end=None, sortby=None, **kw
    ):
        values = self._prepare_portal_layout_values()
        operation_form_obj = request.env["field.operation.forms"]
        if not operation_form_obj.has_access("read"):
            return request.redirect("/my")

        searchbar_sortings = {
            "date": {"label": _("Date"), "order": "start_date desc"},
            "name": {"label": _("Name"), "order": "name desc"},
        }
        if sortby not in searchbar_sortings:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        pager = portal_pager(
            url="/my/operation_forms",
            url_args={"date_begin": date_begin, "date_end": date_end, "sortby": sortby},
            total=operation_form_obj.search_count([]),
            page=page,
            step=self._items_per_page,
        )
        operation_forms = operation_form_obj.search(
            [], order=order, limit=self._items_per_page, offset=pager["offset"]
        )
        request.session["my_operation_forms_history"] = operation_forms.ids[:100]
        values.update(
            {
                "date": date_begin,
                "operation_forms": operation_forms,
                "page_name": "operation_forms_list",
                "pager": pager,
                "default_url": "/my/operation_forms",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
            }
        )
        return request.render(
            "field_operation_forms.my_operation_forms_list_view", values
        )

    @http.route(
        ["/my/operation_forms_detail/<int:operation_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def operation_forms_detail_view(self, operation_id, access_token=None, **kw):
        try:
            operation_forms_sudo = self._document_check_access(
                "field.operation.forms", operation_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my/operation_forms_detail/")
        values = self._operation_forms_get_page_view_values(
            operation_forms_sudo, access_token, **kw
        )
        return request.render(
            "field_operation_forms.my_operation_forms_detail_view", values
        )

    @http.route(
        [
            "/my/operation_forms_detail/<int:operation_id>/form/customer_sign/<string:source>"
        ],
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def portal_operation_forms_customer_sign(
        self, operation_id, access_token=None, source=False, name=None, signature=None
    ):
        """Store the customer signature drawn on the portal page."""
        access_token = access_token or request.httprequest.args.get("access_token")
        try:
            operation_forms_sudo = self._document_check_access(
                "field.operation.forms", operation_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Invalid Form.")}

        try:
            operation_forms_sudo._portal_sign_customer(name, signature)
        except UserError as error:
            return {"error": error.args[0]}

        return {
            "force_refresh": True,
            "redirect_url": operation_forms_sudo.get_portal_url(
                query_string=f"&source={source}"
            ),
        }

    @http.route(
        [
            "/my/operation_forms_detail/<int:operation_id>/form/staff_sign/<string:source>"
        ],
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def portal_operation_forms_staff_sign(
        self, operation_id, access_token=None, source=False, name=None, signature=None
    ):
        """Store the staff signature and flag the form as signed."""
        access_token = access_token or request.httprequest.args.get("access_token")
        try:
            operation_forms_sudo = self._document_check_access(
                "field.operation.forms", operation_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Invalid Form.")}

        try:
            operation_forms_sudo._portal_sign_staff(name, signature)
        except UserError as error:
            return {"error": error.args[0]}

        return {
            "force_refresh": True,
            "redirect_url": operation_forms_sudo.get_portal_url(
                query_string=f"&source={source}"
            ),
        }
