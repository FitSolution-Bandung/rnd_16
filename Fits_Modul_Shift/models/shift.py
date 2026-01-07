from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import time, datetime, date, timedelta
import pytz


class ShiftKaryawan(models.Model):
    _name = 'shift.karyawan'
    _description = 'Shift Karyawan'
    _rec_name = 'name'
    _order = 'state, name'

    # === Fields ===
    name = fields.Char(string='Shift Name', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('selesai', 'Selesai')
    ], string='Status', default='draft', readonly=True)

    jam_mulai = fields.Float(
        string='Start time',
        required=True,
        widget="float_time"
    )
    jam_selesai = fields.Float(
        string='Start end',
        required=True,
        widget="float_time"
    )

    lintas_hari = fields.Boolean(
        string='Cross day',
        default=False,
        help="Centang jika shift melewati tengah malam"
    )

    jenis_shift = fields.Selection([
        ('pagi', 'Pagi'),
        ('sore', 'Sore'),
        ('malam', 'Malam'),
        ('custom', 'Custom')
    ], string='Shift type', default='pagi')

    warna = fields.Integer(string='Shift color')
    aktif = fields.Boolean(string='Active', default=True)
    deskripsi = fields.Text(string='Shift description')
    
     # NEW FIELD
    no_female = fields.Boolean(
        string="No Female",
        default=False,
        help="Centang jika shift ini tidak boleh diassign ke karyawan female"
    )
    
    is_middle = fields.Boolean(string="Middle", default=False, help="Centang jika Middle di perlukan")
    allowed_days = fields.Many2many('hari.minggu', string="Days", help="Centang jika Middle di batasi berdasarkan hari")
    
    show_allowed_days = fields.Boolean("Show Allowed Days", compute="_compute_show_allowed_days")

    
    # === Relations ===
    jadwal_ids = fields.One2many(
        'jadwal.shift.karyawan',
        'shift_id',
        string='Jadwal Karyawan'
    )

    karyawan_ids = fields.Many2many(
        'hr.employee',
        string='Daftar Karyawan (Hari Ini)',
        compute='_compute_karyawan_ids',
        store=False,   # tidak perlu disimpan, dinamis
    )

        # === Compute ===
    @api.depends('is_middle')
    def _compute_show_allowed_days(self):
        for rec in self:
            rec.show_allowed_days = rec.is_middle
    @api.depends('jenis_shift')
    def _compute_no_female(self):
        """Jika shift malam maka otomatis tidak boleh Female"""
        for rec in self:
            rec.no_female = True
    @api.depends('jadwal_ids', 'jenis_shift')
    def _compute_karyawan_ids(self):
        # Dapatkan semua shift confirmed terlebih dahulu
        all_shifts = self.env['shift.karyawan'].search([
            ('aktif', '=', True),
        ])
        
        # Dapatkan timezone user
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        now_utc = datetime.now(pytz.utc)
        now_user = now_utc.astimezone(user_tz)
        today_user = now_user.date()
        
        # Hitung rentang waktu untuk hari ini menurut timezone user
        start_of_day_user = user_tz.localize(
            datetime.combine(today_user, time.min)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        
        end_of_day_user = user_tz.localize(
            datetime.combine(today_user, time.max)
        ).astimezone(pytz.utc).replace(tzinfo=None)
        
        # Ambil semua attendance hari ini yang BELUM check out
        attendances = self.env['hr.attendance'].search([
            ('check_in', '>=', start_of_day_user),
            ('check_in', '<=', end_of_day_user),
            ('check_out', '=', False)  # Hanya yang belum check out
        ])
        
        # Mapping untuk menyimpan karyawan per shift
        shift_employees = {shift.id: self.env['hr.employee'] for shift in all_shifts}
        
        # Untuk setiap attendance, tentukan shift yang paling cocok
        for attendance in attendances:
            # Konversi check_in ke timezone user untuk mendapatkan waktu yang benar
            check_in_utc = attendance.check_in
            if timezone_aware(check_in_utc):
                check_in_user = check_in_utc.astimezone(user_tz)
                check_in_time = check_in_user.time()
            else:
                # Jika check_in tidak aware, asumsikan UTC dan konversi
                check_in_utc_aware = pytz.utc.localize(check_in_utc)
                check_in_user = check_in_utc_aware.astimezone(user_tz)
                check_in_time = check_in_user.time()
            
            # Konversi waktu check-in ke menit sejak tengah malam
            check_in_minutes = check_in_time.hour * 60 + check_in_time.minute
            
            best_shift = None
            min_time_diff = float('inf')
            
            for shift in all_shifts:
                # Konversi jam shift ke time object
                shift_start_time = shift.float_to_time(shift.jam_mulai)
                shift_end_time = shift.float_to_time(shift.jam_selesai)
                
                # Konversi ke menit sejak tengah malam
                shift_start_minutes = shift_start_time.hour * 60 + shift_start_time.minute
                shift_end_minutes = shift_end_time.hour * 60 + shift_end_time.minute
                
                time_diff = abs(check_in_minutes - shift_start_minutes)
                
                # Cek apakah check-in sesuai dengan shift
                if shift.lintas_hari:
                    # Untuk shift lintas hari (misal: 22:00-06:00)
                    # Check-in setelah jam mulai ATAU sebelum jam selesai
                    if (check_in_minutes >= shift_start_minutes or 
                        check_in_minutes < shift_end_minutes):
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_shift = shift
                else:
                    # Untuk shift normal (tidak lintas hari)
                    if shift_start_minutes <= check_in_minutes < shift_end_minutes:
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_shift = shift
            
            # Jika ditemukan shift yang cocok, tambahkan karyawan
            # if best_shift:
            #     shift_employees[best_shift.id] += attendance.employee_id
            if best_shift:
                # 🚫 Jika shift malam dan karyawan female → skip
                if best_shift.no_female and attendance.employee_id.gender == 'female':
                    continue
                shift_employees[best_shift.id] += attendance.employee_id
        
        # Set karyawan_ids untuk setiap shift
        for rec in self:
                rec.karyawan_ids = shift_employees.get(rec.id, self.env['hr.employee'])
            
    # === Constraints ===
    @api.constrains('jam_mulai', 'jam_selesai', 'lintas_hari')
    def _check_jam_shift(self):
        for rec in self:
            if rec.jam_mulai < 0 or rec.jam_mulai >= 24:
                raise ValidationError("Jam mulai harus antara 0-24")
            if rec.jam_selesai < 0 or rec.jam_selesai >= 24:
                raise ValidationError("Jam selesai harus antara 0-24")

            if not rec.lintas_hari and rec.jam_selesai <= rec.jam_mulai:
                raise ValidationError(
                    "Jam selesai harus setelah jam mulai untuk shift tidak lintas hari"
                )

    # @api.constrains('jadwal_ids')
    # def _check_limit_karyawan(self):
    #     for rec in self:
    #         if len(rec.jadwal_ids) > rec.maks_karyawan:
    #             raise ValidationError(
    #                 f"Maksimal {rec.maks_karyawan} karyawan di shift ini. "
    #                 f"Silakan pilih shift lain."
    #             )

    # === Onchange ===
    @api.onchange('jenis_shift')
    def _onchange_jenis_shift(self):
        shift_times = {
            'pagi': (0.0, 0.0),
            'sore': (0.0, 0.0),
            'malam': (0.0, .0),
        }
        if self.jenis_shift in shift_times:
            self.jam_mulai, self.jam_selesai = shift_times[self.jenis_shift]
            self.lintas_hari = (self.jenis_shift == 'malam')

    # === Helpers ===
    def float_to_time(self, float_time):
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return time(hours, minutes)

    # === Actions ===
    def action_selesai(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.write({
                    'state': 'selesai',
                    'aktif': False
                })

    def action_confirm(self):
        for rec in self:
            if rec.state == 'draft':
                rec.write({
                    'state': 'confirmed',
                    'aktif': True
                })

    def action_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'aktif': False
            })

    # === Display ===
    def name_get(self):
        result = []
        for shift in self:
            name = (
                f"{shift.name} "
                f"({self.float_to_time(shift.jam_mulai).strftime('%H:%M')}-"
                f"{self.float_to_time(shift.jam_selesai).strftime('%H:%M')})"
            )
            result.append((shift.id, name))
        return result


def timezone_aware(dt):
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None