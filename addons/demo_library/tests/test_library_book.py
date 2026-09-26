from datetime import timedelta

from odoo import fields
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


class TestLibraryLoanDueDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env["library.book"].create({"title": "Due Date Book"})
        cls.borrower = cls.env["res.partner"].create({"name": "Due Date Borrower"})

    def _loan(self, **vals):
        return self.env["library.loan"].create(
            {"book_id": self.book.id, "borrower_id": self.borrower.id, **vals}
        )

    def test_due_date_defaults_to_two_weeks_out(self):
        loan = self._loan(date_out=fields.Date.from_string("2026-01-01"))
        self.assertEqual(loan.date_due, fields.Date.from_string("2026-01-15"))

    def test_past_due_open_loan_is_overdue(self):
        loan = self._loan(date_out=fields.Date.context_today(self.env.user) - timedelta(days=30))
        self.assertTrue(loan.is_overdue)

    def test_returned_loan_is_never_overdue(self):
        loan = self._loan(date_out=fields.Date.context_today(self.env.user) - timedelta(days=30))
        loan.action_return()
        self.assertFalse(loan.is_overdue)

    def test_due_before_start_rejected(self):
        with self.assertRaises(ValidationError):
            self._loan(
                date_out=fields.Date.from_string("2026-01-10"),
                date_due=fields.Date.from_string("2026-01-01"),
            )


class TestLibraryLoanReturnDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env["library.book"].create({"title": "Return Date Book"})
        cls.borrower = cls.env["res.partner"].create({"name": "Return Date Borrower"})

    def _loan(self):
        return self.env["library.loan"].create({"book_id": self.book.id, "borrower_id": self.borrower.id})

    def test_open_loan_has_no_return_date(self):
        self.assertFalse(self._loan().date_returned)

    def test_returning_stamps_today(self):
        loan = self._loan()
        loan.action_return()
        self.assertEqual(loan.date_returned, fields.Date.context_today(self.env.user))
