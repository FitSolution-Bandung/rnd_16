from odoo import models, fields, api

class ShiftConfigurationPattern(models.Model):
    _name = 'shift.configuration.pattern'
    _description = 'Shift Configuration Pattern'

    name = fields.Char(string='Pattern Name', required=True, help="Contoh: 4-2")
    work_days = fields.Integer(string='Work Days', required=True, help="Jumlah hari kerja")
    off_days = fields.Integer(string='Off Days', required=True, help="Jumlah hari libur")

    shift_ids = fields.Many2many(
        'shift.karyawan',
        string='Shifts Config',
        help="Shift yang termasuk dalam pattern ini"
    )

    description = fields.Text(string="Description")
