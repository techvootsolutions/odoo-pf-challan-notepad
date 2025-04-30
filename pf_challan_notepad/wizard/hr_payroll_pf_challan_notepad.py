import base64
import calendar
from odoo import api, fields, models

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class PFChallanNotepadWizard(models.TransientModel):
    _name = 'pf.challan.notepad.wizard'
    _description = 'Indian Payroll: Employee PF Challan Notepad'

    def _get_employee_ids_domain(self):
        employees = self.env['hr.payslip'].search([]).employee_id.filtered(lambda e: e.company_id.country_id.code == "IN").ids
        return [('id', 'in', employees)]

    month = fields.Selection(MONTH_SELECTION, default='1', required=True)
    year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    employee_ids = fields.Many2many('hr.employee', 'emp_pf_challan_notepad_rel', 'pf_challan_notepad_id', 'employee_id', string='Employees', required=True,
                                    store=True, readonly=False, domain=_get_employee_ids_domain)

    @api.model
    def _get_employee_pf_data(self, year, month, employee_ids):
        # Get the relevant records based on the year and month
        if not employee_ids:
            employee_ids = self.env['hr.employee'].search([])

        result = []
        end_date = calendar.monthrange(year, int(month))[1]

        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employee_ids.ids),
            ('date_from', '>=', f'{year}-{month}-1'),
            ('date_to', '<=', f'{year}-{month}-{end_date}'),
            ('state', 'in', ('done', 'paid'))
        ])

        if not payslips:
            return []

        payslip_data = []
        for payslip in payslips:
            # Get the UAN (can be stored in employee contract or employee model)
            uan = payslip.employee_id.l10n_in_uan or 'N/A'

            # Get the gross salary, basic amount, and contributions
            gross_salary = payslip.line_ids.filtered(lambda l: l.code == 'GROSS').total
            basic_amount = payslip.line_ids.filtered(lambda l: l.code == 'BASIC').total
            pf_deduction_employee = payslip.line_ids.filtered(lambda l: l.code == 'PF Employee').total
            pension_employer = payslip.line_ids.filtered(lambda l: l.code == 'Pension-Employeer').total
            pf_employer = payslip.line_ids.filtered(lambda l: l.code == 'PF-Employeer').total

            # Append data to the list as a dictionary
            payslip_data.append({
                'uan': uan,
                'employee_name': payslip.employee_id.name,
                'gross_salary': gross_salary,
                'basic_amount': basic_amount,
                'pf_deduction_employee': pf_deduction_employee,
                'pension_employer': pension_employer,
                'pf_employer': pf_employer,
            })

        return payslip_data

    def action_export_text(self):
        report_data = self._get_employee_pf_data(self.year, self.month, self.employee_ids)

        # Prepare the TXT content
        txt_content = ""
        for data in report_data:
            txt_content += f"{data['uan']}#~#{data['employee_name']}#~#{int(round(data['gross_salary']))}#~#{int(round(data['basic_amount']))}#~#{int(round(data['basic_amount']))}#~#{int(round(data['basic_amount']))}#~#{abs(int(round(data['pf_deduction_employee'])))}#~#{int(round(data['pension_employer']))}#~#{int(round(data['pf_employer']))}#~#0#~#0\n"

        txt_data = base64.b64encode(txt_content.encode('utf-8'))

        # Create an attachment in Odoo
        month_description = dict(self._fields['month']._description_selection(self.env))
        attachment = self.env['ir.attachment'].create({
            'name': f'{month_description.get(self.month)}-{self.year} PF Challan Notepad.txt',
            'datas': txt_data,
            'type': 'binary',
            'mimetype': 'text/plain',
        })

        # Return the file to the user for download
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
