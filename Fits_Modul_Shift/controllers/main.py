from odoo import http
from odoo.http import request

class ShiftKaryawanController(http.Controller):
 class LemburController(http.Controller):
    
    @http.route(['/my/shifts'], type='http', auth='user', website=True)
    def my_shifts(self, **kwargs):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.uid)], limit=1)
        shifts = request.env['jadwal.shift.karyawan'].sudo().search([
            ('employee_id', '=', employee.id)
        ])
        return request.render('Fits_Modul_Shift.portal_my_shifts', {
            'employee': employee,
            'shifts': shifts
        })

    @http.route('/lembur/konfirmasi', type='http', auth='public', website=True)
    def lembur_konfirmasi_form(self, id=None, approve=None, **kwargs):
        try:
            record_id = int(id)
            record = request.env['riwayat.shift.karyawan'].sudo().browse(record_id)
            if not record.exists():
                return request.not_found()
        except (ValueError, TypeError):
            return request.not_found()

        # Jika parameter approve disediakan di URL, langsung proses
        if approve in ('1', '0'):
            if approve == '1':
                record.lembur_disetujui = 'iya'
                msg = "Anda telah menyetujui lembur."
            else:
                record.lembur_disetujui = 'tidak'
                msg = "Anda telah menolak lembur."

            return request.render("Fits_Modul_Shift.template_lembur_form", {
                'message': msg,
                'record': record,
            })

        # Jika tidak, tampilkan form konfirmasi
        return request.render("Fits_Modul_Shift.konfirmasi_lembur_template", {
            'record': record,
        })

    @http.route('/lembur/konfirmasi/submit', type='http', auth='public', website=True, csrf=False)
    def konfirmasi_lembur(self, record_id=None, approve=None, **kwargs):
        try:
            record_id = int(record_id)
            record = request.env['riwayat.shift.karyawan'].sudo().browse(record_id)
            if not record.exists():
                return request.not_found()
        except (ValueError, TypeError):
            return request.not_found()

        if approve == '1':
            record.lembur_disetujui = 'iya'
            msg = "Anda telah menyetujui lembur."
        elif approve == '0':
            record.lembur_disetujui = 'tidak'
            msg = "Anda telah menolak lembur."
        else:
            msg = "Anda telah menyetujui lembur."

        return request.render("Fits_Modul_Shift.konfirmasi_lembur_template", {
            'message': msg,
            'record': record,
        })
