# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
import xmlrpc
from odoo.exceptions import UserError



class Guarantor(models.Model):
    _name = "loan.guarantor"
    _inherit = ['mail.thread']

    guarantor_id = fields.Many2one(comodel_name='hr.employee', string='Guarantor', domain=[('state', '=', 'onboard')])
    guarantor_for = fields.Many2one(comodel_name='hr.employee', string='Guarantor For', compute='_get_guarantor',
                                    readonly=True,
                                    domain=[('state', '=', 'onboard')], store=True)
    loan_amount = fields.Float(string='Loan Amount', compute='_get_guarantor', readonly=True)
    loan_installments = fields.Float(string='Loan Installments', compute='_get_guarantor', readonly=True)

    loan_id = fields.Many2one(comodel_name='loan.request', string='Loan Form')
    contract_type = fields.Selection(selection=[
        ('internal', 'Internal'),
        ('external', 'External')
    ], compute='_compute_contract_type', store=True)
    state = fields.Selection(string='Status', selection=[
        ('draft', 'Draft'),
        ('wf_guarantor_approve', 'WF Guarantor Approve'),
        ('wf_lm_approve', 'WF LM Approve'),
        ('approved', 'Approved'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    ], default='draft', readonly=True)
    line_manager_id = fields.Many2one('hr.employee', string="Line Manager", compute='_get_name', readonly=True,
                                      store=True, domain=[('state', '=', 'onboard')])
    lm_approve_date = fields.Datetime(string='LM Approving', default='')
    lm_reject_date = fields.Datetime(string='LM Reject', default='')
    guarantor_approve_date = fields.Datetime(string='Guarantor Approving', default='')
    guarantor_reject_date = fields.Datetime(string='Guarantor Reject', default='')
    check_access_right_line = fields.Boolean(compute="check_access_line", string='Access Right LM', readonly=True)
    check_access_loan_guarantor = fields.Boolean(compute="check_access_guarantor", string='Access Right Guarantor',
                                                 readonly=True)

    @api.one
    @api.depends('guarantor_id')
    def check_access_guarantor(self):
        if self.guarantor_id.user_id.id == self._uid or self.user_has_groups('loan.group_loan_admin') or self.user_has_groups('loan.group_welfare_approver'):
            self.check_access_loan_guarantor = True
        else:
            self.check_access_loan_guarantor = False

    @api.one
    @api.depends('line_manager_id')
    def check_access_line(self):
        if self.line_manager_id.user_id.id == self._uid or self.user_has_groups('loan.group_loan_admin') or self.user_has_groups('loan.group_welfare_approver'):
            self.check_access_right_line = True
        else:
            self.check_access_right_line = False

    @api.one
    @api.depends('guarantor_id')
    def _get_name(self):
        self.line_manager_id = self.guarantor_id.line_manager

    @api.one
    @api.depends('loan_id')
    def _get_guarantor(self):
        self.env.uid = 2
        self.guarantor_for = self.loan_id.requester_id
        self.loan_amount = self.loan_id.approved_amount
        self.loan_installments = self.loan_id.approved_installment

    @api.multi
    @api.depends('guarantor_id')
    def _compute_contract_type(self):
        for record in self:
            if record.guarantor_id:
                remote_server = self.env['remote.server'].search([('name', 'like', 'odoo'), ('disabled', '=', False)])
                server = xmlrpc.client.ServerProxy(remote_server['host'] + "/xmlrpc/object")

                employee_company = server.execute(remote_server['database'], 1, remote_server['password'],
                                                  'hr.config.settings',
                                                  'get_employee_company',
                                                  [record.guarantor_id.odoo_id])
                record.contract_type = 'internal' if employee_company[0]['employee_company'][1] == 'NAK' else 'external'

    def button_lm_approve(self):
        mail_obj = self.env['mail.mail']
        emp = self.env['hr.employee'].search([('user_id', '=', self.guarantor_for.user_id.id)])

        mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
        header_html = "<p>Dear Ms./Mr. %s, <br/>Your loan request was approved by your guarantor(%s).</p><p>Kind Regards</p>" % (
            emp.name, self.guarantor_id.name)
        mail = mail_obj.create({
            'body_html': header_html,
            'email_to': (emp.work_email),
            'subject': 'Loan Request',
            'email_from': 'Loan@nak-mci.ir',
            'mail_server_id': mail_server
        })
        mail.send()
        self.state = 'approved'

    def button_lm_reject(self):
        self.state = 'rejected'

    def button_guarantor_approve(self):
        mail_obj = self.env['mail.mail']
        emp = self.env['hr.employee'].search([('user_id', '=',  self.guarantor_id.line_manager.user_id.id)])

        mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
        header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request.</p><p>Kind Regards</p>" % (
            emp.name)
        mail = mail_obj.create({
            'body_html': header_html,
            'email_to': (emp.work_email),
            'subject': 'Loan Request',
            'email_from': 'Loan@nak-mci.ir',
            'mail_server_id': mail_server
        })
        mail.send()
        self.state = 'wf_lm_approve'
        # if self.env['loan.guarantor'].search_count(
        #         [('loan_id', '=', self.id), ('state', '=', 'approved')]) == self.loan_type.num_total_guarantor:
        #     self.state = 'wait_for_hr'

    def button_guarantor_reject(self):
        guarantor = self.env['loan.guarantor'].search(
            [('loan_id', '=', self.id), ('guarantor_id.user_id', '=', self.env.uid)])
        if guarantor:
            self.state = 'rejected'
        # self.state = 'draft'

    @api.one
    def unlink(self):
        for line in self:
            if line.state == 'approved':
                raise UserError(_('You cannot delete in %s state!') % (line.state))
            return super(Guarantor, self).unlink()
