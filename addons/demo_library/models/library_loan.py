from odoo import api, fields, models
from odoo.exceptions import UserError


class LibraryLoan(models.Model):
    _name = "library.loan"
    _description = "Library Loan"

    # ondelete is explicit on every Many2one -- the default (set null) is
    # rarely what you want.
    book_id = fields.Many2one("library.book", required=True, ondelete="cascade")
    borrower_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    date_out = fields.Date(default=fields.Date.context_today)
    date_due = fields.Date()
    date_returned = fields.Date(readonly=True)
    state = fields.Selection(
        [("out", "On Loan"), ("returned", "Returned")],
        default="out",
        required=True,
    )

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
