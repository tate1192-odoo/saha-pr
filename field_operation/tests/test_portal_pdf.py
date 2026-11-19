"""The portal PDF download route belongs to the download handler."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.field_operation.controllers.portal import FieldOperationPortal


@tagged("field_operation", "post_install", "-at_install")
class TestPortalPdfRoute(TransactionCase):
    def test_download_route_is_bound_to_the_download_method(self):
        """The route must be carried by portal_operation_pdf.

        The http.route decorator used to sit on the _pdf_filename helper
        (staticmethod under it), so the URL was bound to the filename builder
        and every download answered with a 500.
        """
        endpoint = FieldOperationPortal.__dict__["portal_operation_pdf"]
        self.assertIn(
            "/my/operation_detail/<int:operation_id>/download_pdf",
            endpoint.original_routing["routes"],
        )
        self.assertFalse(
            hasattr(FieldOperationPortal.__dict__["_pdf_filename"], "original_routing"),
            "the filename helper must not carry the download route",
        )

    def test_pdf_filename_is_ascii_and_header_safe(self):
        partner = self.env["res.partner"].create({"name": "PDF Filename Test"})
        operation = self.env["field.operation"].create(
            {"subject": "PDF Filename Test", "partner_id": partner.id}
        )
        operation.name = '\u015e\u0130\u015e/04 "A"\nB'

        filename = FieldOperationPortal._pdf_filename(operation)

        self.assertTrue(filename.startswith("Field_Operation_"))
        self.assertTrue(filename.endswith(".pdf"))
        self.assertRegex(filename, r"^[A-Za-z0-9._-]+$")
