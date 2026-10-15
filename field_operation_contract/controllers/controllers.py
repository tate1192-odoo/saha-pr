import base64

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.tools.translate import _

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class FieldOperationContractPortal(CustomerPortal):
    """Portal controller for Field Operation Contracts"""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "contract_count" in counters:
            Contract = request.env["field.operation.contract"]
            values["contract_count"] = (
                Contract.search_count(self._get_partner_domain())
                if Contract.has_access("read")
                else 0
            )
        return values

    def _get_partner_domain(self):
        """Only the customer's own contracts (commercial partner + children)."""
        commercial_partner = request.env.user.partner_id.commercial_partner_id
        return [
            ("partner_id", "child_of", commercial_partner.id),
        ]

    @http.route(
        ["/my/contracts", "/my/contracts/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_contracts(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        filterby=None,
        **kwargs,
    ):
        values = self._prepare_portal_layout_values()
        Contract = request.env["field.operation.contract"]

        if not Contract.has_access("read"):
            return request.redirect("/my")

        searchbar_sortings = {
            "date": {"label": _("Date"), "order": "date_start desc"},
            "name": {"label": _("Reference"), "order": "name desc"},
            "state": {"label": _("Status"), "order": "state"},
        }
        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        searchbar_filters = {
            "all": {"label": _("All"), "domain": []},
            "draft": {"label": _("Draft"), "domain": [("state", "=", "draft")]},
            "confirmed": {
                "label": _("Confirmed"),
                "domain": [("state", "=", "confirmed")],
            },
            "expired": {"label": _("Expired"), "domain": [("state", "=", "expired")]},
            "cancel": {"label": _("Cancelled"), "domain": [("state", "=", "cancel")]},
        }
        if not filterby:
            filterby = "all"
        domain = self._get_partner_domain() + searchbar_filters[filterby]["domain"]

        if date_begin and date_end:
            domain += [
                ("create_date", ">=", date_begin),
                ("create_date", "<=", date_end),
            ]

        contract_count = Contract.search_count(domain)
        pager = portal_pager(
            url="/my/contracts",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "filterby": filterby,
            },
            total=contract_count,
            page=page,
            step=self._items_per_page,
        )

        contracts = Contract.search(
            domain, order=order, limit=self._items_per_page, offset=pager["offset"]
        )

        values.update(
            {
                "contracts": contracts,
                "page_name": "contract",
                "pager": pager,
                "default_url": "/my/contracts",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": searchbar_filters,
                "filterby": filterby,
                "date_begin": date_begin,
                "date_end": date_end,
            }
        )
        return request.render(
            "field_operation_contract.portal_my_contracts_list", values
        )

    @http.route(
        ["/my/contract/<int:contract_id>"], type="http", auth="user", website=True
    )
    def portal_contract_page(self, contract_id=None, access_token=None, **kwargs):
        try:
            contract_sudo = self._document_check_access(
                "field.operation.contract", contract_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        values = {
            "contract": contract_sudo,
            "page_name": "contract",
            "user": request.env.user,
        }
        return request.render("field_operation_contract.portal_contract_page", values)

    @http.route(
        ["/my/contract/<int:contract_id>/pdf"], type="http", auth="user", website=True
    )
    def portal_contract_report(
        self, contract_id, access_token=None, download=False, **kw
    ):
        try:
            contract_sudo = self._document_check_access(
                "field.operation.contract", contract_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        report = request.env.ref(
            "field_operation_contract.action_field_operation_contract_pdf"
        ).sudo()
        # sudo(): the customer is a portal user and the report reads pricing and tax
        # fields on the contract lines that portal users are not allowed to read.
        pdf = report._render_qweb_pdf(
            "field_operation_contract.action_field_operation_contract_pdf",
            [contract_sudo.id],
        )[0]
        pdfhttpheaders = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf)),
            (
                "Content-Disposition",
                '{}; filename="{}.pdf"'.format(
                    "attachment" if download else "inline", contract_sudo.name
                ),
            ),
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)

    @http.route(
        ["/my/contract/<int:contract_id>/accept"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_contract_accept(self, contract_id, access_token=None, **kwargs):
        """Accept contract (sign digitally)."""
        try:
            contract_sudo = self._document_check_access(
                "field.operation.contract", contract_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        if contract_sudo.state != "confirmed":
            return request.redirect(f"/my/contract/{contract_id}")

        signature_file = kwargs.get("signature_file")
        signatory_name = kwargs.get("signatory_name")

        if signature_file and signatory_name:
            if hasattr(signature_file, "read"):
                signature_file = base64.b64encode(signature_file.read())
            contract_sudo.write(
                {
                    "signature_file": signature_file,
                    "signatory_name": signatory_name,
                    "signature_status": True,
                    "signature_date": fields.Datetime.now(),
                }
            )

        return request.redirect(f"/my/contract/{contract_id}")
