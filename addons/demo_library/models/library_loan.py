from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

LOAN_DAYS = 14


class LibraryLoan(models.Model):
    _name = "library.loan"
    _description = "Library Loan"
    _order = "date_out desc, id desc"

    # ondelete is explicit on every Many2one -- the default (set null) is
    # rarely what you want.
    book_id = fields.Many2one("library.book", required=True, ondelete="cascade")
    borrower_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    date_out = fields.Date(default=fields.Date.context_today)
    date_due = fields.Date(compute="_compute_date_due", store=True, readonly=False)
    is_overdue = fields.Boolean(compute="_compute_is_overdue")
    date_returned = fields.Date(readonly=True)
    state = fields.Selection(
        [("out", "On Loan"), ("returned", "Returned")],
        default="out",
        required=True,
    )

    @api.depends("date_out")
    def _compute_date_due(self):
        for loan in self:
            loan.date_due = loan.date_out and loan.date_out + timedelta(days=LOAN_DAYS)

    @api.depends("date_due", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for loan in self:
            loan.is_overdue = bool(loan.state == "out" and loan.date_due and loan.date_due < today)

    @api.constrains("date_out", "date_due")
    def _check_dates(self):
        for loan in self:
            if loan.date_out and loan.date_due and loan.date_due < loan.date_out:
                raise ValidationError(self.env._("A loan cannot be due before it starts."))

    def action_return(self):
        for loan in self:
            if loan.state == "returned":
                raise UserError(self.env._("Loan for %s was already returned.", loan.book_id.title))
        # One write for the whole recordset -- never a write inside the loop.
        self.write({"state": "returned", "date_returned": fields.Date.context_today(self)})

    @api.model_create_multi
    def create(self, vals_list):
        # Overriding create returns super()'s result.
        return super().create(vals_list)
