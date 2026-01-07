from odoo import models, fields, api
from datetime import datetime, time

class RiwayatShiftKaryawan(models.Model):
    _name = 'riwayat.shift.karyawan'
    _description = 'Riwayat Shift Karyawan'
    _order = 'tanggal desc'

    # === Fields ===
    tanggal = fields.Date(string='Tanggal', required=True)
    karyawan_id = fields.Many2one('hr.employee', string='Karyawan', required=True)
    durasi_jam = fields.Char(string='Durasi (jam)', compute='_compute_durasi', store=True)
    
    shift_type = fields.Selection([
        ('pagi', 'Sore'),
        ('sore', 'Malam'),
        ('malam', 'Pagi'),
    ], string='Shift', compute='_compute_shift_type', store=True)

    kehadiran_id = fields.Many2one('hr.attendance', string='Worked Hours')
    

    status_kehadiran = fields.Selection([
        ('hadir', 'Hadir'),
        ('alfa', 'Alfa'),
        ('peringatan', '⚠'),
        ('izin_lembur', 'Lembur'),
    ], string='Status Kehadiran', compute='_compute_status_kehadiran', store=True)

    lembur_disetujui = fields.Selection([
        ('iya', 'Iya'),
        ('tidak', 'Tidak'),
    ], string='Persetujuan Lembur')


    # === Compute Fields ===
    @api.depends('kehadiran_id', 'lembur_disetujui')
    def _compute_durasi(self):
        for rec in self:
            attendance = rec.kehadiran_id
            if attendance and attendance.check_in and attendance.check_out:
                # ambil beda waktu check_in - check_out (bersih tanpa potongan)
                delta = attendance.check_out - attendance.check_in
                total_minutes = int(delta.total_seconds() // 60)

                jam = total_minutes // 60
                menit = total_minutes % 60
                rec.durasi_jam = f"{jam:02d}:{menit:02d}"
            else:
                rec.durasi_jam = "00:00"
            
    # === Compute Fields (ini yang asli) ===
    # @api.depends('kehadiran_id', 'lembur_disetujui')
    # def _compute_durasi(self):
    #     for rec in self:
    #         attendance = rec.kehadiran_id
    #         if attendance and attendance.worked_hours:
    #             total_minutes = int(attendance.worked_hours * 60)
    #             jam = total_minutes // 60
    #             menit = total_minutes % 60
    #             rec.durasi_jam = f"{jam:02d}:{menit:02d}"
    #         else:
    #             rec.durasi_jam = "00:00"

    @api.depends('kehadiran_id')
    def _compute_shift_type(self):
        for rec in self:
            attendance = rec.kehadiran_id
            rec.shift_type = False
            if attendance and attendance.check_in:
                ci_time = attendance.check_in.time()
                if ci_time >= time(22, 0) or ci_time <= time(6, 0):
                    rec.shift_type = 'malam'
                elif time(15, 0) <= ci_time < time(23, 0):
                    rec.shift_type = 'sore'
                elif ci_time <= time(17, 0):
                    rec.shift_type = 'pagi'

    @api.depends('kehadiran_id', 'lembur_disetujui')
    def _compute_status_kehadiran(self):
        for rec in self:
            attendance = rec.kehadiran_id
            if not attendance:
                rec.status_kehadiran = 'alfa'
            else:
                worked_minutes = int(attendance.worked_hours * 60)
                if worked_minutes < 480:
                    rec.status_kehadiran = 'peringatan'
                elif worked_minutes > 510:
                    rec.status_kehadiran = 'izin_lembur' if rec.lembur_disetujui == 'iya' else 'hadir'
                else:
                    rec.status_kehadiran = 'hadir'

    # === Business Logic ===
    @api.model
    def _create_riwayat_from_attendance(self, attendance, tanggal_shift=None):
        """
        Membuat riwayat shift baru dari setiap attendance.
        Tidak menimpa data sebelumnya.
        """
        if not attendance.check_out:
            return  # skip jika belum checkout

        riwayat = self.create({
            'tanggal': tanggal_shift or fields.Datetime.from_string(attendance.check_in).date(),
            'karyawan_id': attendance.employee_id.id,
            'kehadiran_id': attendance.id,
        })

        # Kirim notifikasi lembur jika > 8 jam 30 menit
        worked_minutes = int(attendance.worked_hours * 60)
        if worked_minutes > 510:
            karyawan_email = attendance.employee_id.work_email
            if karyawan_email:
                template = self.env.ref('Fits_Modul_Shift.email_template_lembur', raise_if_not_found=False)
                if template:
                    template.send_mail(
                        riwayat.id,
                        email_values={'email_to': karyawan_email},
                        force_send=True
                    )
        return riwayat

    # === Helper URL ===
    def get_lembur_confirm_url(self, is_approved):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/lembur/konfirmasi?id={self.id}&approve={'1' if is_approved else '0'}"
