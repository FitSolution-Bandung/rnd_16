from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class JadwalShift(models.Model):
    _name = 'jadwal.shift.karyawan'
    _description = 'Jadwal Shift per Karyawan'
    _rec_name = 'name'
    _order = 'tanggal ASC'

    name = fields.Char(
        string='Nama Jadwal',
        compute='_compute_name',
        store=True
    )

    tanggal = fields.Date(
        string='Shift Date',
        
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        
    )

    shift_id = fields.Many2one(
        'shift.karyawan',
        string='Shifts',
        
    )

    # Tambahan: Mode Kerja (WFH/WFO)
    mode_kerja = fields.Selection(
        [
            ('wfh', 'WFH'),
            ('wfo', 'WFO')
        ],
        string='Working mode',
        default='wfo',
        
    )

    # Relasi ke Tukar Shift sebagai Pengaju
    tukar_shift_pengaju_ids = fields.One2many(
        'tukar.shift.karyawan',
        'jadwal_shift_pengaju',
        string='Sebagai Pengaju'
    )

    # Relasi ke Tukar Shift sebagai Pengganti
    tukar_shift_pengganti_ids = fields.One2many(
        'tukar.shift.karyawan',
        'jadwal_shift_pengganti',
        string='Sebagai Pengganti'
    )
    
    jenis_shift = fields.Selection(
    related='shift_id.jenis_shift',
    string='Jenis Shift',
    readonly=True,
    store=True
    )

    shift_type = fields.Selection([
    ('normal', 'Normal'),
    ('carter', 'Carter'),
], string='Tipe Shift', default='normal')
    
    status = fields.Selection([
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('selesai', 'Selesai'),
    # add other states as needed
], string='Status', default='draft')
    
    jenis_shift_pengaju = fields.Selection([
        ('pagi', 'Pagi'),
        ('sore', 'Sore'),
        ('malam', 'Malam'),
    ], string='Shift Pengaju')
    
    pengaju_id = fields.Many2one('hr.employee', string='Pengaju Shift')
    active = fields.Boolean(default=True)
    
    def print_pdf(self):
        """Print PDF untuk jadwal shift yang dipilih"""
        # Gunakan self sebagai recordset
        return self.env.ref('Fits_Modul_Shift.action_report_jadwal_shift').report_action(self)

  
    @api.depends('employee_id', 'shift_id', 'mode_kerja')
    def _compute_name(self):
        for record in self:
            nama_karyawan = record.employee_id.name or 'Karyawan'
            nama_shift = record.shift_id.name or 'Shift'
            # Ambil jam mulai & selesai dari float
            def float_to_time_str(f):
                if f is None:
                    return ''
                hours = int(f)
                minutes = int(round((f - hours) * 60))
                return f"{hours:02d}:{minutes:02d}"
            
            jam_mulai = float_to_time_str(record.shift_id.jam_mulai)
            jam_selesai = float_to_time_str(record.shift_id.jam_selesai)
            # mode = dict(self._fields['mode_kerja'].selection).get(record.mode_kerja, '')
            record.name = f"{nama_karyawan} - {nama_shift} ({jam_mulai} - {jam_selesai})"

    @api.model
    def create(self, vals):
        record = super(JadwalShift, self).create(vals)

        # Kalau shift_type = carter, nonaktifkan jadwal pengaju
        if record.shift_type == 'carter' and record.pengaju_id:
            jadwal_pengaju = self.search([
                ('employee_id', '=', record.pengaju_id.id),
                ('tanggal', '=', record.tanggal),
                 ('active', '=', True)
            ], limit=1)

            if jadwal_pengaju:
                # Simpan shift pengaju di Carter
                record.write({'jenis_shift_pengaju': jadwal_pengaju.jenis_shift})
                # Nonaktifkan jadwal pengaju
                jadwal_pengaju.write({'active': False})

        return record

    def get_shift_type_from_jadwal(self):
        """Return shift type string sesuai jadwal shift"""
        self.ensure_one()
        return self.jenis_shift  # langsung dari related shift

    @api.constrains('shift_id', 'employee_id')
    def _check_limit_shift(self):
     for rec in self:
        if rec.shift_id:
            # Hitung karyawan di shift ini sesuai jenis shift
            karyawan_count = self.search_count([
                ('shift_id', '=', rec.shift_id.id),
                ('jenis_shift', '=', rec.jenis_shift)
            ])
            # if karyawan_count > 10:
            #     raise ValidationError("Maksimal 10 karyawan di shift ini. Silakan pilih shift lain.")
            
    def open_wizard_massal(self):
     return {
        'type': 'ir.actions.act_window',
        'name': 'Bulk Entry Schedule Shifts',
        'res_model': 'jadwal.shift.wizard',
        'view_mode': 'form',
        'target': 'new',
    }

class HariMinggu(models.Model):
    _name = 'hari.minggu'
    _description = 'Daftar Hari Senin - Minggu'

    name = fields.Selection([
        ('senin', 'Senin'),
        ('selasa', 'Selasa'),
        ('rabu', 'Rabu'),
        ('kamis', 'Kamis'),
        ('jumat', 'Jumat'),
        ('sabtu', 'Sabtu'),
        ('minggu', 'Minggu'),
    ], string="Hari", required=True)

