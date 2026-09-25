from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LibraryBook(models.Model):
    _name = "library.book"
    _description = "Library Book"
    _order = "title"

    title = fields.Char(required=True, index=True)
    isbn = fields.Char(string="ISBN")
    copies_total = fields.Integer(default=1)
    # Depends on every field actually read, including the dotted path through
    # the loans. A missing dependency here yields stale values in production only.
    copies_available = fields.Integer(compute="_compute_copies_available", store=True)
    loan_ids = fields.One2many("library.loan", "book_id", string="Loans")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("isbn_uniq", "unique(isbn)", "A book with this ISBN already exists."),
    ]

    @api.depends("copies_total", "loan_ids.state")
    def _compute_copies_available(self):
        for book in self:
            on_loan = len(book.loan_ids.filtered(lambda loan: loan.state == "out"))
            book.copies_available = book.copies_total - on_loan

    @api.constrains("copies_total")
    def _check_copies_total(self):
        for book in self:
            if book.copies_total < 0:
                raise ValidationError(self.env._("Total copies cannot be negative for %s", book.title))
