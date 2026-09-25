from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestLibraryBook(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env["library.book"].create({"title": "Test Book", "copies_total": 2})
        cls.borrower = cls.env["res.partner"].create({"name": "Test Borrower"})

    def test_all_copies_available_without_loans(self):
        self.assertEqual(self.book.copies_available, 2)

    def test_open_loan_reduces_availability(self):
        self.env["library.loan"].create({"book_id": self.book.id, "borrower_id": self.borrower.id})
        self.assertEqual(self.book.copies_available, 1)

    def test_returned_loan_restores_availability(self):
        loan = self.env["library.loan"].create({"book_id": self.book.id, "borrower_id": self.borrower.id})
        loan.action_return()
        self.assertEqual(self.book.copies_available, 2)

    def test_negative_copies_rejected(self):
        with self.assertRaises(ValidationError):
            self.book.copies_total = -1
            self.book.flush_recordset()
