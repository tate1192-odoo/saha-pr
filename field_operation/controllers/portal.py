import binascii
import re
import unicodedata

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

#: Upper bound for the base64 signature payload accepted from the portal
#: (the file is stored as an attachment).
MAX_SIGNATURE_LENGTH = 512 * 1024


class FieldOperationPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "operation_count" in counters:
            operation_model = request.env["field.operation"]
            # Count only the customer's own services
            domain = self._get_filter_domain({})
            operation_count = (
                operation_model.search_count(domain)
                if operation_model.has_access("read")
                else 0
            )
            values["operation_count"] = operation_count
        return values

    def _operation_get_page_view_values(self, operation, access_token, **kwargs):
        values = {
            "page_name": "operation_detail",
            "operation": operation,
        }
        return self._get_page_view_values(
            operation, access_token, values, "my_operations_history", False, **kwargs
        )

    def _get_filter_domain(self, kw):
        # A customer only sees their own services or their company's (children included)
        commercial_partner = request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", commercial_partner.id)]

    @http.route(
        ["/my/list_operations", "/my/list_operations/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def operation_list_view(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        search=None,
        status_filter=None,
        date_from=None,
        date_to=None,
        view_mode=None,
        **kw,
    ):
        values = self._prepare_portal_layout_values()
        operation_obj = request.env["field.operation"]

        if not operation_obj.has_access("read"):
            return request.redirect("/my")

        domain = self._get_filter_domain(kw)

        if search:
            domain += [
                "|",
                "|",
                ("name", "ilike", search),
                ("subject", "ilike", search),
                ("description", "ilike", search),
            ]

        if status_filter:
            domain.append(("status", "=", status_filter))

        if date_from:
            domain.append(("start_date", ">=", date_from))
        if date_to:
            domain.append(("end_date", "<=", date_to + " 23:59:59"))

        searchbar_sortings = {
            "date": {"label": _("Date"), "order": "start_date desc"},
            "name": {"label": _("Name"), "order": "name desc"},
        }

        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        operation_count = operation_obj.search_count(domain)
        pager = portal_pager(
            url="/my/list_operations",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "search": search,
                "status_filter": status_filter,
                "date_from": date_from,
                "date_to": date_to,
                "view_mode": view_mode,
            },
            total=operation_count,
            page=page,
            step=self._items_per_page,
        )

        operations = operation_obj.search(
            domain, order=order, limit=self._items_per_page, offset=pager["offset"]
        )

        request.session["my_operations_history"] = operations.ids[:100]

        values.update(
            {
                "date": date_begin,
                "operations": operations,
                "page_name": "operation_list",
                "pager": pager,
                "default_url": "/my/list_operations",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                # Filter values
                "search": search,
                "status_filter": status_filter,
                "date_from": date_from,
                "date_to": date_to,
                "view_mode": view_mode,
            }
        )
        return request.render("field_operation.my_field_operation_list_view", values)

    @http.route(
        ["/my/operation_detail/<int:operation_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def operation_detail_view(self, operation_id, access_token=None, **kw):
        try:
            operation_sudo = self._document_check_access(
                "field.operation", operation_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        vals = self._operation_get_page_view_values(operation_sudo, access_token, **kw)
        return request.render("field_operation.my_field_operation_detail_view", vals)

    @http.route(
        ["/my/operation_detail/<int:operation_id>/operation_sign"],
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def portal_operation_sign(
        self, operation_id, access_token=None, name=None, signature=None
    ):
        access_token = access_token or request.httprequest.args.get("access_token")
        try:
            operation_sudo = self._document_check_access(
                "field.operation", operation_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Invalid Form.")}

        # Only a completed service can be signed
        if operation_sudo.status != "done":
            return {"error": _("Only completed operations can be signed.")}

        if not signature:
            return {"error": _("Signature is missing.")}
        if len(signature) > MAX_SIGNATURE_LENGTH:
            return {"error": _("Signature is too large.")}

        try:
            operation_sudo.write(
                {
                    "signed_by": name,
                    "form_signature": signature,
                    "signed_on": fields.Datetime.now(),
                    "signed": True,
                }
            )
        except (TypeError, binascii.Error):
            return {"error": _("Invalid signature data.")}

        query_string = "&message=sign_ok"
        return {
            "force_refresh": True,
            "redirect_url": operation_sudo.get_portal_url(query_string=query_string),
        }

    # PDF download route
    @http.route(
        ["/my/operation_detail/<int:operation_id>/download_pdf"],
        type="http",
        auth="public",
        website=True,
    )
    @staticmethod
    def _pdf_filename(operation):
        """Return an ASCII, header-safe file name for the service PDF.

        ``field.operation.name`` is editable by the user: a Turkish character in
        it raises UnicodeEncodeError while the header is encoded, and a quote or
        a newline would break out of the quoted Content-Disposition value.
        """
        ascii_name = (
            unicodedata.normalize("NFKD", operation.name or "")
            .encode("ascii", "ignore")
            .decode()
        )
        return "Field_Operation_%s.pdf" % (
            re.sub(r"[^A-Za-z0-9._-]", "_", ascii_name) or str(operation.id)
        )

    def portal_operation_pdf(self, operation_id, access_token=None, **kw):
        try:
            operation_sudo = self._document_check_access(
                "field.operation", operation_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        pdf_content, content_type = (
            request.env["ir.actions.report"]
            .sudo()
            ._render_qweb_pdf(
                "field_operation.field_operation_action_pdf",
                [operation_id],
                data={"report_type": "pdf"},
            )
        )
        if content_type != "pdf":
            return request.redirect("/my")

        if isinstance(pdf_content, dict):
            pdf_content = pdf_content.get(operation_id, {}).get("stream")
            if pdf_content:
                pdf_content = pdf_content.read()
        if not pdf_content:
            return request.redirect("/my")

        pdf_http_headers = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf_content)),
            (
                "Content-Disposition",
                f'attachment; filename="{self._pdf_filename(operation_sudo)}"',
            ),
        ]

        return request.make_response(pdf_content, headers=pdf_http_headers)
