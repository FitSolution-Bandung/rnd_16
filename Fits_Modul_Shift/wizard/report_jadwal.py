from odoo import models, fields, api

class ReportJadwalWizard(models.TransientModel):
    _name = 'report.jadwal.wizard'
    _description = 'Filter Report Jadwal Shift'

    date_start = fields.Date(string="Start date", required=True)
    date_end = fields.Date(string="End Selesai", required=True)
    all_employee = fields.Boolean(string="Show All Employees", default=True)
    department_id = fields.Many2one('hr.department', string="Department")
    tag_ids = fields.Many2many('hr.employee.category', string="Tags Employee")
    employee_id = fields.Many2one('hr.employee', string="Employee")

    def action_print_report(self):
        """Cetak laporan PDF sesuai filter"""
        domain = [
            ('tanggal', '>=', self.date_start),
            ('tanggal', '<=', self.date_end)
        ]

        # 🔹 Logika filter (prioritas berdasarkan field yang diisi)
        if not self.all_employee:
            if self.employee_id:
                domain.append(('employee_id', '=', self.employee_id.id))
            elif self.department_id:
                domain.append(('employee_id.department_id', '=', self.department_id.id))
            elif self.tag_ids:
                domain.append(('employee_id.category_ids', 'in', self.tag_ids.ids))

        records = self.env['jadwal.shift.karyawan'].search(domain)

        if not records:
            raise ValueError("Tidak ada data shift yang ditemukan untuk filter yang dipilih.")

        return self.env.ref('Fits_Modul_Shift.action_report_jadwal_shift').report_action(records)
