# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LoanIrAttachment(models.Model):
    _name = 'loan.document'

    _inherit = 'ir.attachment'

    name = fields.Char(string='Name', required=False, invisible=True)

    loan_document_id = fields.Many2one('loan.request', string="Loan Document ID")
    document_type = fields.Selection([
        ('0', 'First Page of Certificate Card'),
        ('1', 'First Page of National Card'),('2', 'Cheque Image')], string="Document Type",
        required=True, default='0')

    @api.onchange('document_type')
    def _onchange_document_type(self):
        if self.document_type:
            self.name = dict(self._fields['document_type'].selection).get(self.document_type)