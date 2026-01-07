from odoo import models, api

class JadwalShiftReport(models.AbstractModel):
    _name = 'report.Fits_Modul_Shift.report_jadwal_shift_template'
    _description = 'Report Jadwal Shift Karyawan'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Ambil semua jadwal shift dari jadwal.shift.karyawan tanpa filter form.
        Ini akan menampilkan semua data yang ada di calendar view.
        """
        # Ambil semua record aktif
        docs = self.env['jadwal.shift.karyawan'].search([], order='tanggal, employee_id')

        return {
            'doc_ids': docs.ids,
            'doc_model': 'jadwal.shift.karyawan',
            'docs': docs,
        }
