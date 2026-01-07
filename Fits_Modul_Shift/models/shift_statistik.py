from odoo import models, fields, api

class ShiftStatistik(models.Model):
    _name = 'shift.statistik'
    _description = 'Statistik Shift Karyawan'
    _auto = False  # view model

    name = fields.Char(string='Karyawan')
    shift_pagi = fields.Integer(string='Shift Pagi')
    shift_sore = fields.Integer(string='Shift Sore')
    shift_malam = fields.Integer(string='Shift Malam')
    total_shift = fields.Integer(string='Total Shift')

    hadir = fields.Integer(string='Hadir')
    terlambat = fields.Integer(string='Terlambat')
    absen = fields.Integer(string='Absen')
    overtime = fields.Float(string='Overtime (Jam)')
    shift_carter = fields.Integer(string='Shift Carter')
    shift_oncall = fields.Integer(string='Shift On-call')

    def init(self):
     self.env.cr.execute("""
        CREATE OR REPLACE VIEW shift_statistik AS (
            SELECT
                ROW_NUMBER() OVER() AS id,
                emp.name AS name,
                SUM(CASE WHEN rs.shift_type = 'pagi' THEN 1 ELSE 0 END) AS shift_pagi,
                SUM(CASE WHEN rs.shift_type = 'sore' THEN 1 ELSE 0 END) AS shift_sore,
                SUM(CASE WHEN rs.shift_type = 'malam' THEN 1 ELSE 0 END) AS shift_malam,
                COUNT(*) AS total_shift,

                -- Kehadiran
                SUM(CASE WHEN rs.status_kehadiran = 'hadir' THEN 1 ELSE 0 END) AS hadir,
                SUM(CASE WHEN rs.status_kehadiran = 'alfa' THEN 1 ELSE 0 END) AS absen,
                SUM(CASE WHEN rs.status_kehadiran = 'peringatan' THEN 1 ELSE 0 END) AS terlambat,
                SUM(CASE WHEN rs.status_kehadiran = 'izin_lembur' THEN 1 ELSE 0 END) AS lembur,

                -- Carter & On-call
                SUM(CASE WHEN rs.shift_type = 'carter' THEN 1 ELSE 0 END) AS shift_carter,
                SUM(CASE WHEN rs.shift_type = 'oncall' THEN 1 ELSE 0 END) AS shift_oncall,

                -- Placeholder overtime biar gak error
                0 AS overtime

            FROM riwayat_shift_karyawan rs
            JOIN hr_employee emp ON rs.karyawan_id = emp.id
            WHERE rs.tanggal >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY emp.name
        )
    """)


