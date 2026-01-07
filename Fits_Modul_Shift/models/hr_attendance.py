from odoo import models, api, fields
from odoo.exceptions import ValidationError
from pytz import timezone, UTC

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _attendance_action_change(self, *args, **kwargs):
        res = super()._attendance_action_change(*args, **kwargs)

        for attendance in res:
            check_in = attendance.check_in
            check_out = attendance.check_out

            # Proses check-in (belum check-out)
            if check_in and not check_out:
                # Konversi ke timezone user (atau company)
                user_tz = self.env.user.tz or 'UTC'
                local_dt = fields.Datetime.context_timestamp(self, check_in)
                check_in_hour = local_dt.hour
                
             # Cari semua jadwal shift aktif hari ini (pakai tanggal lokal)
                jadwal_list = self.env['jadwal.shift.karyawan'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('tanggal', '=', local_dt.date()),
                    ('active', '=', True)
                ])

                if jadwal_list:
                    # Tentukan shift sekarang dari jam check-in
                    if 6 <= check_in_hour < 14:
                        shift_now = 'pagi'
                    elif 14 <= check_in_hour < 22:
                        shift_now = 'sore'
                    else:
                        shift_now = 'malam'

                    # Kumpulkan semua jenis_shift dari jadwal yang ada
                    jenis_shifts = []
                    for jadwal in jadwal_list:
                        if jadwal.shift_type == 'carter':
                            if jadwal.jenis_shift_pengaju:
                                jenis_shifts.append(jadwal.jenis_shift_pengaju)
                            elif jadwal.pengaju_id:
                                jenis_shifts.append(jadwal.pengaju_id.jenis_shift)
                        else:
                            jenis_shifts.append(jadwal.jenis_shift)

                    # Validasi: apakah shift_now ada di salah satu jadwal
                    if shift_now not in jenis_shifts:
                        raise ValidationError(
                            f"Karyawan {attendance.employee_id.name} dijadwalkan {', '.join(jenis_shifts)}, "
                            f"tapi mencoba check in di shift {shift_now}."
                        )
                    else:
                        # ✅ Kalau cocok, lolos validasi → bisa check-in
                        return True
                else:
                    # Kalau gak ada jadwal aktif → otomatis ditolak
                    raise ValidationError(
                        f"Karyawan {attendance.employee_id.name} tidak memiliki jadwal shift pada {local_dt.date()}."
                    )



            # Proses check-in dan check-out lengkap
            if check_in and check_out:
                if check_out < check_in:
                    raise ValidationError('"Check Out" tidak boleh lebih awal dari "Check In".')

                # Konversi check-in ke tanggal lokal untuk riwayat
                user_tz = self.env.user.tz or 'UTC'
                local_check_in = fields.Datetime.context_timestamp(self, check_in)

                self.env['riwayat.shift.karyawan']._create_riwayat_from_attendance(
                    attendance,
                    tanggal_shift=local_check_in.date()  # kirim tanggal lokal
                )

        return res


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    shift_type = fields.Selection([
    ('pagi', 'Pagi'),
    ('sore', 'Sore'),
    ('malam', 'Malam'),
], string='Shift', compute='_compute_shift_type', store=False)


    def _compute_shift_type(self):
        for rec in self:
            # Hanya tampilkan shift_type jika sudah check_out
            if not rec.check_in or not rec.check_out:
                rec.shift_type = False
                continue
            
            # Konversi ke timezone user
            local_check_in = fields.Datetime.context_timestamp(self, rec.check_in)
            check_in_hour = local_check_in.hour
            
            # check_in_hour = fields.Datetime.from_string(rec.check_in).hour

            if 6 <= check_in_hour < 14:
                rec.shift_type = 'pagi'
            elif 14 <= check_in_hour < 22:
                rec.shift_type = 'sore'
            else:
                rec.shift_type = 'malam'

    # ✅ FIX WORKED HOURS → jam real (tanpa minus 1 jam)
    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                # Konversi ke timezone user
                user_tz = self.env.user.tz or 'UTC'
                tz = timezone(user_tz)

                check_in_local = fields.Datetime.context_timestamp(attendance, attendance.check_in)
                check_out_local = fields.Datetime.context_timestamp(attendance, attendance.check_out)

                delta = check_out_local - check_in_local
                attendance.worked_hours = delta.total_seconds() / 3600.0
            else:
                attendance.worked_hours = 0.0