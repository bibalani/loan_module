# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc
from datetime import timedelta, datetime
import ssl
from random import random
from time import sleep
from requests import Session
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from zeep import Client
from zeep.transports import Transport
import random

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context


class LoanRequest(models.Model):
    _name = "loan.request"
    _inherit = ['mail.thread']

    name = fields.Char(string="Loan Number", readonly=True, required=True, copy=False, default='New')

    requester_id = fields.Many2one('hr.employee', string="Requester", required=True, readonly=True,
                                   states={'draft': [('readonly', False)]}, domain=[('state', '=', 'onboard')])
    staff_id = fields.Char(string='Staff ID', compute='_employee_info', store=True)
    loan_type = fields.Many2one(comodel_name='loan.type', required=True, readonly=True,
                                states={'draft': [('readonly', False)]}, domain=[('state', '=', 'running')])
    attachment_ids = fields.One2many('loan.document', 'loan_document_id',
                                     string="Attachments", readonly=True,
                                     states={'draft': [('readonly', False)], 'wait_for_cheque': [('readonly', False)]})
    installment_line_ids = fields.One2many('loan.installment.line', 'loan_request_id', string="Installment Lines")
    guarantor_ids = fields.One2many(comodel_name='loan.guarantor', inverse_name='loan_id', string='Guarantors',
                                    readonly=True,
                                    states={'draft': [('readonly', False)],
                                            'wait_for_guarantor': [('readonly', False)]})
    guarantor_user_ids = fields.Many2many(comodel_name='res.users', compute='_compute_guarantor_user_ids', store=True)
    approved_installment = fields.Integer(string='Approved Installments No.', readonly=True,
                                          states={'welfare_review': [('readonly', False)],
                                                  'wait_for_treasury': [('readonly', False)]})
    requested_amount = fields.Float(string='Requested Loan Amount', readonly=True,
                                    states={'draft': [('readonly', False)]})
    requested_installment = fields.Integer(string='Requested Installments No.', readonly=True,
                                           states={'draft': [('readonly', False)]})

    approved_amount = fields.Float(string='Approved Loan Amount', readonly=True,
                                   states={'welfare_review': [('readonly', False)],
                                           'wait_for_treasury': [('readonly', False)]})

    paid_installment = fields.Float(string='Paid Installments No.', compute='_compute_paid_installments')
    paid_installment_amount = fields.Float(string='Paid Installments',
                                           compute='_compute_paid_installments')
    remaining_installment = fields.Float(string='Remaining Installments No.',
                                         compute='_compute_remaining_installments')
    remaining_installment_amount = fields.Float(string='Remaining Installments',
                                                compute='_compute_remaining_installments')

    max_amount = fields.Float(string='Maximum Allowable Amount', readonly=True, compute='_loan_properties')

    max_installment = fields.Integer(string='Maximum Installments No.', readonly=True, compute='_loan_properties')
    line_manager = fields.Many2one('hr.employee', string="Line Manager", compute='_get_name', readonly=True, store=True,
                                   domain=[('state', '=', 'onboard')])
    hr_comment = fields.Text(string="HR Comment", readonly=True, states={'wait_for_hr': [('readonly', False)]})

    check_access_right_line = fields.Boolean(compute="check_access_line", string='Access Right LM', readonly=True)
    check_access_loan_requester = fields.Boolean(compute="check_access_requester", string='Access Right Requester',
                                                 readonly=True)
    welfare_rejection_comments = fields.Text(string="Welfare Review Rejection comments", track_visibility='onchange',
                                             readonly=True,
                                             states={'welfare_review': [('readonly', False)]})
    welfare_review_reject_date = fields.Datetime(string="Welfare Review Reject Date", readonly=True)
    welfare_review_approve_date = fields.Datetime(string="Welfare Review Approve Date", readonly=True)

    hr_reject_date = fields.Datetime(string="HR Reject Date", readonly=True)
    hr_approve_date = fields.Datetime(string="HR Approve Date", readonly=True)
    hr_rejection_comments = fields.Text(string="HR Rejection comments", track_visibility='onchange',
                                        readonly=True,
                                        states={'wait_for_hr': [('readonly', False)]})

    lm_reject_date = fields.Datetime(string="LM Reject Date", readonly=True)
    lm_approve_date = fields.Datetime(string="LM Approve Date", readonly=True)
    lm_rejection_comments = fields.Text(string="Lm Rejection comments", track_visibility='onchange',
                                        readonly=True,
                                        states={'wait_for_lm': [('readonly', False)]})

    cheque_reject_date = fields.Datetime(string="Cheque Reject Date", readonly=True)
    cheque_approve_date = fields.Datetime(string="Cheque Approve Date", readonly=True)
    cheque_rejection_comments = fields.Text(string="Cheque Rejection comments", track_visibility='onchange',
                                            readonly=True,
                                            states={'wait_for_cheque_received': [('readonly', False)]})

    treasury_reject_date = fields.Datetime(string="Treasury Reject Date", readonly=True)
    treasury_approve_date = fields.Datetime(string="Treasury Approve Date", readonly=True)
    treasury_rejection_comments = fields.Text(string="Treasury Rejection comments", track_visibility='onchange',
                                              readonly=True,
                                              states={'wait_for_treasury': [('readonly', False)]})

    check_access_right_welfare_admin = fields.Boolean(compute="check_access_welfare",
                                                      string='Access Right Welfare Admin', readonly=True)
    check_access_right_loan_admin = fields.Boolean(compute="check_access_loan_admin", string='Access Right Loan Admin',
                                                   readonly=True)
    loan_request_date = fields.Datetime(string="Request Date", readonly=True)
    hired_on = fields.Date(string="Hired On", compute='_employee_info')
    employee_company = fields.Char(string="Employee Company", compute='_employee_info')

    guarantee_cheque_bank = fields.Char(string="Bank Name", readonly=True,
                                        states={'wait_for_cheque_received': [('readonly', False)]})
    guarantee_cheque_bank_branch = fields.Char(string="Bank Branch", readonly=True,
                                               states={'wait_for_cheque_received': [('readonly', False)]})
    guarantee_cheque_serial = fields.Char(string="Cheque Serial", readonly=True,
                                          states={'wait_for_cheque_received': [('readonly', False)]})
    guarantee_cheque_amount = fields.Float(string="Cheque Amount", readonly=True,
                                           states={'wait_for_cheque_received': [('readonly', False)]})

    guarantee_cheque_return = fields.Boolean(string="Cheque Return", readonly=True,
                                             states={'close': [('readonly', False)]})
    guarantee_cheque_return_date = fields.Datetime(string="Cheque Return Date", readonly=True,
                                                   states={'close': [('readonly', False)]})

    check_cheque_returned = fields.Boolean(compute="check_cheque", string='Cheque Return', readonly=True)
    last_loan_amount = fields.Float(string='Last Loan Amount', readonly=True,
                                    states={'welfare_review': [('readonly', False)],
                                            'wait_for_treasury': [('readonly', False)]})

    last_loan_date = fields.Datetime(string="Last Loan Date", readonly=True,
                                     states={'welfare_review': [('readonly', False)],
                                             'wait_for_treasury': [('readonly', False)]})

    state = fields.Selection([
        ('draft', 'Draft'),
        ('welfare_review', 'Welfare Review'),
        ('wait_for_lm', 'Waiting For LM'),
        ('wait_for_guarantor', 'Waiting For Guarantor'),
        ('wait_for_hr', 'Waiting For HR'),
        ('wait_for_cheque', 'Waiting For Cheque'),
        ('wait_for_cheque_received', 'Waiting For Cheque Received'),
        ('wait_for_treasury', 'Waiting For Treasury'),
        ('paid', 'Paid'),
        ('rejected', 'Reject'),
        ('close', 'Close'),
        ('cancel', 'Cancel'),
    ],
        string='Status', default='draft', required=True, track_visibility='onchange')
    requester_contract_type = fields.Selection(selection=[
        ('internal', 'Internal'),
        ('external', 'External')
    ], compute='_compute_requester_contract_type', string='Employee Status',store=True)

    sheba_no = fields.Char(string='Sheba Number', readonly=True,
                                    states={'draft': [('readonly', False)]})

    @api.one
    @api.depends('guarantee_cheque_return')
    def check_cheque(self):
        if self.guarantee_cheque_return:
            self.check_cheque_returned = True
        else:
            self.check_cheque_returned = False

    def check_access_loan_admin(self):
        for record in self:
            self.env.cr.execute("""select g.name from (select gid from res_groups_users_rel where uid=%s)gu
               join (select id,name,category_id from res_groups)g on g.id=gu.gid join 
               (select id,name from ir_module_category)m on m.id = g.category_id
               where g.name ~* 'Loan Admin' and m.name ~* 'Loan' """, (self.env.uid,))
            welfare = self.env.cr.fetchone()
            if welfare:
                record.check_access_right_loan_admin = True

    def check_access_welfare(self):
        for record in self:
            self.env.cr.execute("""select g.name from (select gid from res_groups_users_rel where uid=%s)gu
               join (select id,name,category_id from res_groups)g on g.id=gu.gid join 
               (select id,name from ir_module_category)m on m.id = g.category_id
               where g.name ~* 'Welfare' and m.name ~* 'Loan' """, (self.env.uid,))
            welfare = self.env.cr.fetchone()
            if welfare:
                record.check_access_right_welfare_admin = True

    @api.multi
    @api.depends('requester_id')
    def _compute_requester_contract_type(self):
        for record in self:
            if record.requester_id:
                remote_server = self.env['remote.server'].search([('name', 'like', 'odoo'), ('disabled', '=', False)])
                server = xmlrpc.client.ServerProxy(remote_server['host'] + "/xmlrpc/object")

                employee_company = server.execute(remote_server['database'], 1, remote_server['password'],
                                                  'hr.config.settings',
                                                  'get_employee_company',
                                                  [record.requester_id.odoo_id])
                record.requester_contract_type = 'internal' if employee_company[0]['employee_company'][1] == 'NAK' else 'external'
    @api.multi
    @api.onchange('requester_id')
    def _compute_loan_type(self):
        filtered_objective = []
        general_cond = []

        for record in self:
            if self.requester_id:
                hr_employee = self.env['hr.employee']
                for rec in self:
                    emp_id = hr_employee.search([('id', '=', rec.requester_id.id)])
                if emp_id:
                    employee = hr_employee.browse(emp_id)[0]

                # remote_server = self.env['remote.server'].search([('name', 'like', 'ERP'), ('disabled', '=', False)])
                # server = xmlrpc.client.ServerProxy(remote_server['host'] + "/xmlrpc/object")
                #
                # for rec in self:
                #     employee_company = server.execute(remote_server['database'], 1, remote_server['password'],
                #                                       'hr.config.settings',
                #                                       'get_employee_company',
                #                                       [rec.requester_id.odoo_id])
                if employee.id.employee_company == 'NAK':
                    # self.env.cr.execute(
                    #     """select id,name from loan_type where eligible_employee in('internal','all')""")
                    # loan_type = self.env.cr.fetchall()
                    general_cond += self.env['loan.type'].search(
                        [('eligible_employee', 'in', ["all", "internal"])])
                else:
                    general_cond += self.env['loan.type'].search(
                        [('eligible_employee', 'in', ["all", "external"])])
                general_cond = [x.id for x in general_cond]

        return {'domain': {'loan_type': [('id', 'in', general_cond)]}}

    @api.one
    @api.depends('line_manager')
    def check_access_line(self):
        if self.line_manager.user_id.id == self._uid or self.user_has_groups('loan.group_loan_admin'):
            self.check_access_right_line = True
        else:
            self.check_access_right_line = False

    @api.one
    @api.depends('requester_id')
    def check_access_requester(self):
        if self.requester_id.user_id.id == self._uid or self.user_has_groups('loan.group_loan_admin')or self.user_has_groups('loan.group_welfare_approver'):
            self.check_access_loan_requester = True
        else:
            self.check_access_loan_requester = False

    @api.one
    @api.depends('requester_id')
    def _get_name(self):
        self.line_manager = self.requester_id.line_manager

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('loan.request') or 'New'
        res = super(LoanRequest, self).create(vals)
        return res

    # @api.one
    # @api.constrains('attachment_ids', 'state')
    # def check_ir_attachment(self):
    #     if self.state == 'draft':
    #         if not self.attachment_ids:
    #             raise ValidationError(
    #                 "Please upload required document(s) for your request.")
    #
    #         if len(self.attachment_ids) < 2:
    #             raise ValidationError("Please upload First Page of Certificate Card/First Page of National Card in attachments tab!")
    #     if self.state == 'wait_for_cheque' and self.check_access_requester:
    #         if len(self.attachment_ids) < 3:
    #             raise ValidationError("Please upload Cheque image in attachments tab!")

    # @api.model
    # def default_get(self, fields_list):
    #     res = super(LoanRequest, self).default_get(fields_list)
    #     config = self.env['loan.config'].search([], limit=1)
    #     upload_fields = [u.name for u in config.upload_fields]
    #     vals = []
    #     for field in upload_fields:
    #         vals.append((0, 0, {'name': field}))
    #     res.update({'attachment_ids': vals})
    #     res.update({'installment_line_ids': self.id})

        return res

    @api.depends('loan_type')
    def _loan_properties(self):
        for record in self:
            record.max_amount = record.loan_type.max_amount
            record.max_installment = record.loan_type.max_installment
            record.requested_installment = record.loan_type.max_installment
            record.requested_amount = record.loan_type.max_amount

    @api.depends('requester_id')
    def _employee_info(self):
        for record in self:
            record.staff_id = record.requester_id.staff_id
            record.employee_company = record.requester_id.employee_company
            record.hired_on = record.requester_id.hired_on

    @api.depends('guarantor_ids')
    def _compute_guarantor_user_ids(self):
        for record in self:
            emp_ids = [i.guarantor_id.id for i in record.guarantor_ids]
            user_ids = [i.user_id.id for i in self.env['hr.employee'].browse(emp_ids)]
            record.guarantor_user_ids = [(6, 0, user_ids)]

    def _compute_remaining_installments(self):
        if self.requester_id:
            for record in self:
                record.remaining_installment = record.approved_installment
                record.remaining_installment_amount = record.approved_amount

                self.env.cr.execute(
                    """ select count(1) as installment_count,sum(installment_amount) as paid_installments from loan_installment_line where state='publish' and employee_id=%s """,
                    (record.requester_id.id,))
                paid_installments = self.env.cr.dictfetchall()
                if paid_installments:
                    for pay in paid_installments:
                        if pay["paid_installments"] is None:
                            pay["paid_installments"] = 0
                        record.remaining_installment = abs(record.approved_installment - pay["installment_count"])
                        record.remaining_installment_amount = abs(record.approved_amount - pay["paid_installments"])

    def _compute_paid_installments(self):
        if self.requester_id:
            for record in self:
                self.env.cr.execute(
                    """ select count(1) as installment_count,sum(installment_amount) as paid_installments from loan_installment_line where state='publish' and employee_id=%s """,
                    (record.requester_id.id,))
                paid_installments = self.env.cr.dictfetchall()
                if paid_installments:
                    for pay in paid_installments:
                        record.paid_installment = pay["installment_count"]
                        record.paid_installment_amount = pay["paid_installments"]

    @api.multi
    def unlink(self):
        for line in self:
            if line.state != 'draft':
                raise UserError(_('You cannot delete in %s state!') % (line.state))
            else:
                if line.guarantor_ids:
                    line.guarantor_ids.unlink()
                return super(LoanRequest, self).unlink()

    def button_send_to_draft(self):
        self.state = 'draft'
        self.env.cr.execute(
            """update loan_guarantor set state='draft' where loan_id=%s  """, (self.id,))

    def button_cancel_request(self):
        'welfare_review', 'wait_for_lm', 'wait_for_guarantor', 'wait_for_hr'
        if self.state == 'welfare_review':
            self.state = 'draft'
        elif self.state == 'wait_for_lm':
            self.state = 'welfare_review'
        elif self.state == 'wait_for_guarantor':
            self.state = 'welfare_review'
        elif self.state == 'wait_for_hr':
            self.state = 'wait_for_guarantor'
        self.env.cr.execute(
            """update loan_guarantor set state='closed' where loan_id=%s  """, (self.id,))

    def button_send_request(self):
        guarantor_internal_count = self.env['loan.guarantor'].search_count(
            [('loan_id', '=', self.id), ('contract_type', '=', 'internal')])
        guarantor_external_count = self.env['loan.guarantor'].search_count(
            [('loan_id', '=', self.id), ('contract_type', '=', 'external')])

        guarantor_total_count = self.env['loan.guarantor'].search_count(
            [('loan_id', '=', self.id)])
        if guarantor_total_count < self.loan_type.num_total_guarantor:
            raise UserError(
                _(f'Total Number of Guarantors Must be {self.loan_type.num_total_guarantor}.Internal Guarantors:{self.loan_type.num_internal_guarantor} External Guarantors:{self.loan_type.num_external_guarantor}'))

        if guarantor_internal_count < self.loan_type.num_internal_guarantor:
            raise UserError(_(f'Number of Internal Guarantors Must be {self.loan_type.num_internal_guarantor}'))

        if guarantor_external_count < self.loan_type.num_external_guarantor:
            raise UserError(_(f'Number of External Guarantors Must be {self.loan_type.num_external_guarantor}'))

        if self.requested_amount > self.loan_type.max_amount:
            raise UserError(_(f'Requested loan amount should not exceed {self.loan_type.max_amount}'))

        if self.requested_installment > self.loan_type.max_installment:
            raise UserError(_(f'Requested loan instalment should not be greater than {self.loan_type.max_installment}'))

        if not self.attachment_ids:
            raise ValidationError(
                "Please upload required document(s) for your request.")

        # if len(self.attachment_ids) < 2:
        #     raise ValidationError("Please upload First Page of Certificate Card/First Page of National Card in attachments tab!")
        # for attachment in self.attachment_ids:
        #     if attachment.mimetype != 'image/jpeg':
        #         raise ValidationError("All attachments should have jpg format!")
        self.env.cr.execute(
            """select count(1) from loan_guarantor l1 cross join loan_guarantor l2  where l1.guarantor_id=l2.guarantor_for and l1.guarantor_for=l2.guarantor_id and l1.guarantor_id=%s""",
            (self.requester_id.id,))
        result = self.env.cr.fetchall()
        if result[0][0] >= 1:
            raise UserError(
                _(f'You are the guarantor of one of the selected guarantors. Please choose another person!'))
        loan_guarantor = self.env['loan.guarantor']
        hr_employee = self.env['hr.employee']

        for record in self.guarantor_ids:

            guarantor = loan_guarantor.browse(record.id)[0]
            self.env.cr.execute(
                """select guarantor_id from loan_guarantor where state='approved' and guarantor_id=%s group by guarantor_id having count(1)>3""",
                (guarantor.guarantor_id.id,))
            result = self.env.cr.fetchall()
            uids = hr_employee.search([('id', '=', guarantor.guarantor_id.id)])
            if uids:
                # find mobile number
                employee = hr_employee.browse(uids)[0]
                emp_name = employee.id.name
            if len(result) > 0:
                raise UserError(
                    _(f' {emp_name} is the guarantor of 3 employees. Please choose another person.'))
            if guarantor.guarantor_id.id == self.requester_id.id:
                raise UserError(
                    _(f' You cannot be the guarantor of yourself!'))

        # mail_obj = self.env['mail.mail']
        # group = self.env['res.groups'].search([('name', '=', 'Welfare Approver'), ('category_id', '=', 82)])
        # for g in group.users:
        #     emp = self.env['hr.employee'].search([('user_id', '=', g.id)])
        #
        #     mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Staff')]).id
        #     header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
        #         emp.name, self.requester_id.name)
        #     mail = mail_obj.create({
        #         'body_html': header_html,
        #         'email_to': (emp.work_email),
        #         'subject': 'Loan Request',
        #         'email_from': 'Staff-Service-Notification@nak-mci.ir',
        #         'mail_server_id': mail_server
        #     })
        #     mail.send()
        self.state = 'welfare_review'
        self.loan_request_date = datetime.now()

    def button_welfare_approve(self):
        if self.requested_amount:
            if not self.approved_amount:
                raise UserError(
                    _(f'Please enter approved loan amount.'))
        if self.requested_installment:
            if not self.approved_installment:
                raise UserError(
                    _(f'Please enter approved number of loan installments.'))

        if self.approved_amount > self.loan_type.max_amount:
            raise UserError(_(f'Approved loan amount should not exceed {self.loan_type.max_amount}'))

        if self.approved_installment > self.loan_type.max_installment:
            raise UserError(_(f'Approved loan instalment should not be greater than {self.loan_type.max_installment}'))

        mail_obj = self.env['mail.mail']
        emp = self.env['hr.employee'].search([('user_id', '=', self.line_manager.user_id.id)])

        mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
        header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
            emp.name, self.requester_id.name)
        mail = mail_obj.create({
            'body_html': header_html,
            'email_to': (emp.work_email),
            'subject': 'Loan Request',
            'email_from': 'Loan@nak-mci.ir',
            'mail_server_id': mail_server
        })
        mail.send()
        self.welfare_review_approve_date = datetime.now()
        self.state = 'wait_for_lm'

    def button_welfare_reject(self):
        if not self.welfare_rejection_comments:
            raise UserError(_('Please describe rejection reasons in Comments tab !'))
        self.welfare_review_reject_date = datetime.now()
        self.state = 'rejected'

    def button_lm_approve(self):
        if self.requester_id.line_manager.user_id.id != self._uid:
            raise UserError(_('You are not the line manager of current employee!'))

        self.state = 'wait_for_guarantor'
        self.lm_approve_date = datetime.now()
        self.env.cr.execute(
            """update loan_guarantor set state='wf_guarantor_approve' where loan_id=%s  """, (self.id,))
        hr_employee = self.env['hr.employee']
        loan_guarantor = self.env['loan.guarantor']

        for record in self.guarantor_ids:
            guarantor = loan_guarantor.browse(record.id)[0]
            uids = hr_employee.search([('id', '=', guarantor.guarantor_id.id)]).id
            if uids:
                emp = hr_employee.browse(uids)[0]
                mail_obj = self.env['mail.mail']
                # emp = self.env['hr.employee'].search([('user_id', '=', self.line_manager.user_id.id)])

                mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
                header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
                    emp.name, self.requester_id.name)
                mail = mail_obj.create({
                    'body_html': header_html,
                    'email_to': (emp.work_email),
                    'subject': 'Loan Request',
                    'email_from': 'Loan@nak-mci.ir',
                    'mail_server_id': mail_server
                })
                mail.send()

    def button_lm_reject(self):
        if not self.lm_rejection_comments:
            raise UserError(_('Please describe rejection reasons in Comments tab !'))
        self.state = 'rejected'
        self.lm_reject_date = datetime.now()

    def button_line_approve(self):
        self.state = 'hr'

    def button_line_reject(self):
        self.state = 'rejected'

    def button_hr_approve(self):
        self.state = 'finance'

    def button_hr_reject(self):
        self.state = 'rejected'

    def button_finance_approve(self):
        self.state = 'done'

    def button_finance_reject(self):
        self.state = 'rejected'

    def button_send_to_hr(self):
        self.env.cr.execute(
            """select count(1) from loan_guarantor where loan_id =%s and state='approved'""", (self.id,))
        result = self.env.cr.fetchall()
        if result[0][0] == self.loan_type.num_total_guarantor:
            self.state = 'wait_for_hr'
        else:
            raise UserError(_('All guarantors should approve the loan request to proceed !'))
        mail_obj = self.env['mail.mail']
        group = self.env['res.groups'].search([('name', 'ilike', 'HR Welfare Approver'), ('category_id', '=', 82)]).users
        for g in group:
            emp = self.env['hr.employee'].search([('user_id', '=', g.id)])

            mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
            header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
                emp.name, self.requester_id.name)
            mail = mail_obj.create({
                'body_html': header_html,
                'email_to': (emp.work_email),
                'subject': 'Loan Request',
                'email_from': 'Loan@nak-mci.ir',
                'mail_server_id': mail_server
            })
            mail.send()

    def button_send_to_cheque(self):
        self.state = 'wait_for_cheque'
        self.hr_approve_date = datetime.now()
        mail_obj = self.env['mail.mail']
        emp = self.env['hr.employee'].search([('user_id', '=', self.requester_id.user_id.id)])

        mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Loan')]).id
        header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
            emp.name, self.requester_id.name)
        mail = mail_obj.create({
            'body_html': header_html,
            'email_to': (emp.work_email),
            'subject': 'Loan Request',
            'email_from': 'Loan@nak-mci.ir',
            'mail_server_id': mail_server
        })
        mail.send()

    def button_send_to_cheque_received(self):
        loan_doc = self.env['loan.document'].search(
            [('loan_document_id', '=', self.id), ('name', 'like', "Cheque Image")])
        if not loan_doc:
            raise ValidationError("Please upload Cheque image in attachments tab!")
        self.state = 'wait_for_cheque_received'
        self.cheque_approve_date = datetime.now()
        # mail_obj = self.env['mail.mail']
        # group = self.env['res.groups'].search([('name', '=', 'Welfare Approver'), ('category_id', '=', 82)])
        # for g in group.users:
        #     emp = self.env['hr.employee'].search([('user_id', '=', g.id)])
        #
        #     mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Staff')]).id
        #     header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
        #         emp.name, self.requester_id.name)
        #     mail = mail_obj.create({
        #         'body_html': header_html,
        #         'email_to': (emp.work_email),
        #         'subject': 'Loan Request',
        #         'email_from': 'Staff-Service-Notification@nak-mci.ir',
        #         'mail_server_id': mail_server
        #     })
        #     mail.send()

    def button_hr_reject(self):
        if not self.hr_rejection_comments:
            raise UserError(_('Please describe rejection reasons in Comments tab !'))
        self.state = 'rejected'
        self.hr_reject_date = datetime.now()

    def button_send_to_treasury(self):
        # mail_obj = self.env['mail.mail']
        # group = self.env['res.groups'].search([('name', 'ilike', 'Treasury Approver'), ('category_id', '=', 82)]).users
        # for g in group:
        #     emp = self.env['hr.employee'].search([('user_id', '=', g.id)])
        #
        #     mail_server = self.env['ir.mail_server'].search([('name', 'ilike', 'Staff')]).id
        #     header_html = "<p>Dear Ms./Mr. %s, <br/>Kindly please check and proceed the Loan Request of %s.</p><p>Kind Regards</p>" % (
        #         emp.name, self.requester_id.name)
        #     mail = mail_obj.create({
        #         'body_html': header_html,
        #         'email_to': (emp.work_email),
        #         'subject': 'Loan Request',
        #         'email_from': 'Staff-Service-Notification@nak-mci.ir',
        #         'mail_server_id': mail_server
        #     })
        #     mail.send()
        self.state = 'wait_for_treasury'
        # self.cheque_approve_date=datetime.now()

    def button_cheque_reject(self):
        if not self.cheque_rejection_comments:
            raise UserError(_('Please describe rejection reasons in Comments tab !'))
        self.state = 'rejected'
        self.cheque_reject_date = datetime.now()

    def button_treasury_reject(self):
        if not self.treasury_rejection_comments:
            raise UserError(_('Please describe rejection reasons in Comments tab !'))
        self.state = 'rejected'
        self.treasury_reject_date = datetime.now()

    def button_force_close(self):
        self.env.cr.execute("""
                  update loan_guarantor set state='closed' where loan_id=%s;
                  """ % (self.id))
        self.state = 'close'

    def button_send_to_paid(self):
        self.treasury_approve_date = datetime.now()
        self.send_sms()
        self.state = 'paid'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(LoanRequest, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                       submenu=submenu)
        user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        fields = res.get('fields')
        emp_ids = ''
        filtered_users = []
        filtered_loan_types = []
        if fields.get('requester_id'):
            if self.user_has_groups('base.group_user'):
                filtered_users += self.env['hr.employee'].search(
                    [('state', '=', 'onboard'), ('id', 'not in', tuple(emp_ids)), ('id', '=', user.id)])

            filtered_users_ids = [x.id for x in filtered_users]
            res['fields']['requester_id']['domain'] = [('id', 'in', filtered_users_ids)]

        return res

    def send_sms(self):
        hr_employee = self.env['hr.employee']
        uids = hr_employee.search([('user_id', '=', self.requester_id.user_id.id)])
        if uids:
            # find mobile number
            employee = hr_employee.browse(uids)[0]
            mobile = employee.id.mobile_phone
            if mobile:
                # generate code
                digit_code = '0123456789'
                random_code = ''.join(random.SystemRandom().choice(digit_code) for i in range(6))
                # random_code = str(random.randint(6, 1e6))
                RECIPIENT_NUMBER = mobile
                MESSGAE_TEXT = "Your loan request has been approved.{0} will be paid.".format(self.approved_amount)
                self.env.cr.execute(
                    """ select username,domain,url,password,sender_number from sms_server_settings where name ilike '%sms%' and disabled=false; """)
                rec = self.env.cr.dictfetchall()
                if rec:
                    USER_NAME = rec[0]['username']
                    URL = rec[0]['url']
                    PASSWORD = rec[0]['password']
                    DOMAIN = rec[0]['domain']
                    SENDER_NUMBER = rec[0]['sender_number']

                    UDH = ""
                    ENCODING = ""
                    CHECKING_MESSAGE_ID = "13"
                    startTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    session = Session()
                    # basic auth
                    session.auth = HTTPBasicAuth(USER_NAME + '/' + DOMAIN, PASSWORD)
                    # soap
                    wsdl = 'https://sms.magfa.com/api/soap/sms/v2/server?wsdl'
                    client = Client(wsdl=wsdl, transport=Transport(session=session))
                    messages = client.get_type('ns1:stringArray');
                    senders = client.get_type('ns1:stringArray');
                    recipients = client.get_type('ns1:stringArray');
                    uids = client.get_type('ns1:longArray');
                    encodings = client.get_type('ns1:intArray');
                    udhs = client.get_type('ns1:stringArray');
                    priorities = client.get_type('ns1:intArray');
                    response = client.service.send(messages(item=[MESSGAE_TEXT]), senders(item=[SENDER_NUMBER]),
                                                   recipients(item=[mobile]),
                                                   uids(item=[]), encodings(item=[]), udhs(item=[]),
                                                   priorities(item=[]))
                    EndTime = datetime.now() + timedelta(minutes=5)

                    if response:
                        # self.env.cr.execute(
                        #     "UPDATE hr_employee SET registration_code=%s ,registration_date=%s WHERE id=%s",
                        #     (random_code, EndTime, employee.id[0].id,))
                        sleep(3)
            else:
                raise UserError("Your mobile number is not set.please contact HR department.")

        return {
            "type": "ir.actions.do_nothing",
        }


class LoanInstallment(models.Model):
    _name = "loan.installment"
    name = fields.Char(string='Name')
    pay_period_id = fields.Many2one('hr.pay.period', string="Pay Period", required=True, readonly=True,
                                    states={'draft': [('readonly', False)]}, domain=[('state', '=', 'open')])
    installment_line_ids = fields.One2many(comodel_name='loan.installment.line', inverse_name='loan_installment_id',
                                           readonly=True,
                                           states={'draft': [('readonly', False)]},
                                           string='Installment Line', ondelete='cascade')
    employee_ids = fields.Many2many('hr.employee', 'loan_installment_employee_rel', 'installment_id', 'employee_id',
                                    string='Employees', states={'draft': [('readonly', False)]}, readonly=True,
                                    copy=False, domain=[('state', '=', 'onboard')])

    state = fields.Selection([
        ('draft', 'Draft'),
        ('publish', 'Publish')
    ],
        string='Status', default='draft', required=True, track_visibility='onchange')

    @api.model
    def create(self, values):
        values['name'] = self.env['ir.sequence'].get('loan_installment_sq_code')
        return super(LoanInstallment, self).create(values)

    def button_fetch_employees(self):
        self.env.cr.execute("""
        DELETE FROM loan_installment_employee_rel WHERE installment_id = %s;
        """ % (self.id,))
        self.env.cr.execute(
            """select distinct(requester_id) from loan_request where state='paid'""")
        employees = self.env.cr.dictfetchall()
        for emp in employees:
            self.env.cr.execute("""
                      INSERT INTO loan_installment_employee_rel
                      (installment_id, employee_id)
                      VALUES(%s, %s);
                      """ % (self.id, emp['requester_id']))
        return True

    def button_calculate_installments(self):
        self.env.cr.execute(
            """ SELECT employee_id from loan_installment_line WHERE pay_period_id=%s GROUP BY pay_period_id, employee_id HAVING count(*)>1""",
            (self.pay_period_id.id,))
        check_duplicate = self.env.cr.dictfetchall()
        if check_duplicate:
            raise UserError(_('There are duplicate records in other installment list !'))

        self.env.cr.execute("""
        DELETE FROM loan_installment_line WHERE loan_installment_id = %s;
        """ % (self.id,))
        self.env.cr.execute(
            """ select loan_request.id,requester_id,approved_installment,approved_amount,loan_type.interest_rate from loan_request inner join loan_type on loan_request.loan_type=loan_type.id  where loan_request.state='paid'""")
        employees = self.env.cr.dictfetchall()
        interest_rate = 0
        installment_amount = 0
        for emp in employees:
            interest_rate = emp['approved_amount'] * emp['interest_rate']
            installment_amount = ((emp['approved_amount'] + interest_rate) / emp['approved_installment'])

            self.env.cr.execute("""
                      INSERT INTO loan_installment_line
                      (pay_period_id,employee_id,loan_installment_id,state,installment_amount,loan_request_id)
                      VALUES(%s, %s,%s,'%s',%s,%s);
                      """ % (
                self.pay_period_id.id, emp['requester_id'], self.id, "draft", installment_amount, emp['id']))
        return True

    def button_publish(self):

        self.env.cr.execute(
            """ SELECT employee_id,loan_request_id,installment_amount,pay_period_id from loan_installment_line WHERE pay_period_id=%s and loan_installment_id=%s""",
            (self.pay_period_id.id, self.id,))
        employees = self.env.cr.dictfetchall()
        remote_server = self.env['remote.server'].search([('name', 'like', 'odoo'), ('disabled', '=', False)])
        server = xmlrpc.client.ServerProxy(remote_server['host'] + "/xmlrpc/object")

        for emp in employees:

            self.env.cr.execute(
                """ SELECT approved_installment,loan_type,approved_amount from loan_request WHERE id=%s""",
                ((emp["loan_request_id"]),))
            approved_installments = self.env.cr.dictfetchall()

            self.env.cr.execute(
                """ select count(1) as installment_count,sum(installment_amount) as paid_installments from loan_installment_line where state='publish' and employee_id=%s and loan_request_id=%s """,
                (emp["employee_id"], emp["loan_request_id"]))
            paid_installments = self.env.cr.dictfetchall()
            service_fee = True

            for approved in approved_installments:
                loan_type = self.env['loan.type'].search(
                    [('id', '=', int(approved["loan_type"]))])
                emp_odoo_id = self.env['hr.employee'].search(
                    [('id', '=', emp["employee_id"])])
                approved_ins_count = 0
                check_loan_type = server.execute(remote_server['database'], 1, remote_server['password'],
                                                 'nak.payroll.item',
                                                 'search',
                                                 [('name', 'ilike', loan_type.name)])
                if check_loan_type:
                    if paid_installments:
                        for pay in paid_installments:
                            paid = pay["installment_count"]
                            if paid > 1:
                                service_fee = False

                    loan_piv = server.execute(remote_server['database'], 1, remote_server['password'],
                                              'hr.config.settings',
                                              'loan_piv_for_cloud',
                                              emp_odoo_id.odoo_id, loan_type.name, emp["installment_amount"],
                                              self.pay_period_id.name, service_fee,
                                              )
                else:
                    raise UserError(_('Loan Type does not exist in ERP/HR system!'))

                approved_ins_count = approved["approved_installment"]

            if paid_installments:
                for pay in paid_installments:
                    paid = pay["installment_count"]
                    if paid == approved_ins_count:
                        self.env.cr.execute("""
                                  update loan_request set state='close' where id=%s;
                                  """ % (emp["loan_request_id"]))

                        self.env.cr.execute("""
                                  update loan_guarantor set state='closed' where loan_id=%s;
                                  """ % (emp["loan_request_id"]))
        self.env.cr.execute("""
                  update loan_installment_line set state='publish' where loan_installment_id=%s;
                  """ % (self.id))
        self.write({'state': 'publish'})
        return True


class LoanInstallmentLine(models.Model):
    _name = "loan.installment.line"

    pay_period_id = fields.Many2one('hr.pay.period', string="Pay Period", required=True,
                                    states={'draft': [('readonly', False)]}, domain=[('state', '!=', 'closed')])
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, readonly=True,
                                  states={'draft': [('readonly', False)]}, domain=[('state', '=', 'onboard')])
    loan_installment_id = fields.Many2one(comodel_name='loan.installment', string='Loan Installment')
    loan_request_id = fields.Many2one('loan.request', string="Loan Request")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('publish', 'Publish')
    ],
        string='Status', default='draft', required=True, track_visibility='onchange')
    installment_amount = fields.Float(string='Installment Amount', readonly=True,
                                      states={'draft': [('readonly', False)]})
