from odoo import models, fields

class HREmployeeShift(models.Model):
    _inherit = 'hr.employee'

    shift_config_id = fields.Many2one(
        'shift.configuration.pattern',
        string='Shift Configuration'
    )

    shift_start_date = fields.Date(
        string='Start Date Shifting',
        help="Tanggal mulai karyawan mengikuti shift"
    )
