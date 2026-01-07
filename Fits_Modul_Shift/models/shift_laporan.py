from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ShiftLaporan(models.Model):
    _name = 'shift.laporan'
    _description = 'Laporan Shift Karyawan'
    _rec_name = 'name'
    _order = 'periode_awal DESC'

    name = fields.Char(compute="_compute_name", store=True)
    periode_awal = fields.Date(string="Early Period", required=True)
    periode_akhir = fields.Date(string="Final Period", required=True)
    jenis_laporan = fields.Selection([
        ('mingguan', 'Mingguan'),
        ('bulanan', 'Bulanan')
    ], string="Report Type", default="mingguan")

    line_ids = fields.One2many('shift.laporan.line', 'laporan_id', string="Detail Shifts")
    rekap_ids = fields.One2many('shift.laporan.rekap', 'laporan_id', string="Recap per Employee")

    # ringkasan angka
    total_karyawan = fields.Integer(string="Total Employees", compute="_compute_totals", store=True)
    total_shift = fields.Integer(string="Total Shifts", compute="_compute_totals", store=True)
    total_wfh = fields.Integer(string="Total WFH", compute="_compute_totals", store=True)
    total_wfo = fields.Integer(string="Total WFO", compute="_compute_totals", store=True)

    # tambahan ringkasan
    total_hadir = fields.Integer(string="Totally Present", compute="_compute_totals", store=True)
    total_alfa = fields.Integer(string="Totally Alpha", compute="_compute_totals", store=True)
    total_izin = fields.Integer(string="Totally Permissions", compute="_compute_totals", store=True)
    total_lembur = fields.Integer(string="Totally Overtime", compute="_compute_totals", store=True)
    total_terlambat = fields.Integer(string="Totally Late", compute="_compute_totals", store=True)

    # ==================================================================
    # COMPUTES
    # ==================================================================
    @api.depends('periode_awal', 'periode_akhir', 'jenis_laporan')
    def _compute_name(self):
        for rec in self:
            if rec.periode_awal and rec.periode_akhir:
                rec.name = f"Laporan {rec.jenis_laporan.capitalize()} {rec.periode_awal} s/d {rec.periode_akhir}"
            else:
                rec.name = "Draft Laporan"

    @api.depends('line_ids')
    def _compute_totals(self):
        for rec in self:
            rec.total_shift = len(rec.line_ids)
            rec.total_karyawan = len(rec.line_ids.mapped('employee_id'))
            rec.total_wfh = len(rec.line_ids.filtered(lambda l: l.mode_kerja == 'wfh'))
            rec.total_wfo = len(rec.line_ids.filtered(lambda l: l.mode_kerja == 'wfo'))
            rec.total_hadir = len(rec.line_ids.filtered(lambda l: l.status_kehadiran == 'hadir'))
            rec.total_alfa = len(rec.line_ids.filtered(lambda l: l.status_kehadiran == 'alfa'))
            rec.total_izin = len(rec.line_ids.filtered(lambda l: l.status_kehadiran == 'izin'))
            rec.total_lembur = len(rec.line_ids.filtered(lambda l: l.status_kehadiran == 'izin_lembur'))
            rec.total_terlambat = len(rec.line_ids.filtered(lambda l: l.status_kehadiran == 'peringatan'))

    # ==================================================================
    # HELPERS
    # ==================================================================
    def _float_to_time(self, hours_float):
        """Konversi angka jam desimal (misal 7.84722) menjadi format HH:MM."""
        try:
            hours_float = float(hours_float or 0.0)
        except (TypeError, ValueError):
            hours_float = 0.0
        hours = int(hours_float)
        minutes = int(round((hours_float - hours) * 60))
        if minutes == 60:
            hours += 1
            minutes = 0
        return f"{hours:02d}:{minutes:02d}"

    def _get_shift_type(self, check_in):
        """Tentukan jenis shift berdasarkan jam check_in."""
        if not check_in:
            return False
        hour = fields.Datetime.to_datetime(check_in).hour
        if 6 <= hour < 14:
            return 'pagi'
        elif 14 <= hour < 22:
            return 'sore'
        return 'malam'

    # ==================================================================
    # ACTIONS
    # ==================================================================
    def action_generate(self):
        """Generate data laporan dari hr.attendance dalam periode yang dipilih."""
        for rec in self:
            rec.line_ids.unlink()
            rec.rekap_ids.unlink()

            if not rec.periode_awal or not rec.periode_akhir:
                raise UserError("Silakan isi Periode Awal dan Periode Akhir terlebih dahulu.")

            attendances = self.env['hr.attendance'].search([
                ('check_in', '>=', rec.periode_awal),
                ('check_in', '<=', rec.periode_akhir),
            ])

            # -----------------------------
            # DETAIL LAPORAN
            # -----------------------------
            for att in attendances:
                worked = att.worked_hours or 0.0

                if att.check_in and att.check_out:
                    if worked > 8.0:
                        status = 'izin_lembur'
                    else:
                        status = 'hadir'
                elif att.check_in and not att.check_out:
                    status = 'peringatan'
                else:
                    status = 'alfa'

                tanggal_val = fields.Datetime.to_datetime(att.check_in).date() if att.check_in else False

                self.env['shift.laporan.line'].create({
                    'laporan_id': rec.id,
                    'tanggal': tanggal_val,
                    'employee_id': att.employee_id.id if att.employee_id else False,
                    'shift_type': self._get_shift_type(att.check_in),
                    'durasi_jam': self._float_to_time(worked),
                    'status_kehadiran': status,
                    'mode_kerja': 'wfo',
                })

            # -----------------------------
            # REKAP PER EMPLOYEE
            # -----------------------------
            for emp in attendances.mapped('employee_id'):
                emp_records = attendances.filtered(lambda a: a.employee_id == emp)
                hadir = len(emp_records.filtered(lambda a: a.check_in and a.check_out))
                alfa = len(emp_records.filtered(lambda a: not a.check_in))
                lembur = len(emp_records.filtered(lambda a: (a.worked_hours or 0.0) > 8.0))

                self.env['shift.laporan.rekap'].create({
                    'laporan_id': rec.id,
                    'employee_id': emp.id,
                    'total_hadir': hadir,
                    'total_alfa': alfa,
                    'total_lembur': lembur,
                })


# ==================================================================
# DETAIL
# ==================================================================
class ShiftLaporanLine(models.Model):
    _name = 'shift.laporan.line'
    _description = 'Detail Laporan Shift'

    laporan_id = fields.Many2one('shift.laporan', required=True, ondelete='cascade')
    tanggal = fields.Date(string="Tanggal")
    employee_id = fields.Many2one('hr.employee', string="Karyawan", required=True)
    shift_type = fields.Selection([
        ('pagi', 'Sore'),
        ('sore', 'Malam'),
        ('malam', 'Pagi')
    ], string="Jenis Shift")
    durasi_jam = fields.Char(string="Durasi Jam")
    status_kehadiran = fields.Selection([
        ('hadir', 'Hadir'),
        ('alfa', 'Alfa'),
        ('peringatan', '⚠'),
        ('izin_lembur', 'Lembur'),
        ('izin', 'Izin'),
    ], string="Status Kehadiran")
    mode_kerja = fields.Selection([
        ('wfh', 'WFH'),
        ('wfo', 'WFO')
    ], string="Mode Kerja")


# ==================================================================
# REKAP
# ==================================================================
class ShiftLaporanRekap(models.Model):
    _name = 'shift.laporan.rekap'
    _description = 'Rekap Laporan Shift per Karyawan'

    laporan_id = fields.Many2one('shift.laporan', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Karyawan", required=True)
    total_hadir = fields.Integer("Total Hadir")
    total_alfa = fields.Integer("Total Alfa")
    total_lembur = fields.Integer("Total Lembur")
