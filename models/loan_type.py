# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LoanType(models.Model):
    _name = "loan.type"
    _inherit = ['mail.thread']

    name = fields.Char(string='Name',required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    max_amount = fields.Float(string='Maximum Allowable Amount',required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    max_installment = fields.Integer(string='Maximum Installments No.',required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    num_internal_guarantor = fields.Integer(string='Internal Guarantors No.',required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    num_external_guarantor = fields.Integer(string='External Guarantors No.',required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    num_total_guarantor = fields.Integer(string='Total Required Guarantors',track_visibility='onchange', readonly=True, compute='_get_total_guarantors')
    interest_rate = fields.Integer(string='Interest Rate',track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})

    # active = fields.Boolean(string='Active', default=True)
    eligible_employee = fields.Selection(selection=[
        ('internal', 'Internal'),
        ('external', 'External'),
        ('all', 'All')],required="True",track_visibility='onchange', readonly=True,states={'draft': [('readonly', False)]})
    state = fields.Selection(string='Status', selection=[
        ('draft','Draft'),
        ('running','Running'),
        ('closed', 'Closed'),
    ], default='draft', readonly=True,track_visibility='onchange', copy=False)

    @api.one
    def send_to_running(self):
        self.state = 'running'
    @api.one
    def send_to_close(self):
        self.state = 'closed'

    @api.one
    def _get_total_guarantors(self):
        self.num_total_guarantor = self.num_internal_guarantor + self.num_external_guarantor

