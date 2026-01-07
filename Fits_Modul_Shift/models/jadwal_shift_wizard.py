from odoo import models, fields
from datetime import timedelta
import random

class GenderReference(models.Model):
    _name = 'gender.reference'
    _description = 'Referensi Gender'

    name = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', required=True, unique=True)


class JadwalShiftWizard(models.TransientModel):
    _name = 'jadwal.shift.wizard'
    _description = 'Wizard Input Massal Jadwal Shift Otomatis'

    tanggal_mulai = fields.Date(string="Start Date", required=True)
    tanggal_selesai = fields.Date(string="End Date", required=True)
    shift_ids = fields.Many2many('shift.karyawan', string="Shift List", required=True)
    day_ids = fields.Many2many('hari.minggu', string="Days", help="pilih", required=True)
    department_ids = fields.Many2many('hr.department', string="Department", help="Filter by Department")
    gender_ids = fields.Many2many('gender.reference', string="Gender", help="Filter by Gender")
    tag_ids = fields.Many2many(
        'hr.employee.category',
        string="By Tags",
        help="Filter employees by tags"
    )

    def action_create_shifts(self):
        if not self.shift_ids or not self.day_ids:
            return

        domain = [('active', '=', True)]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))

        all_employees = self.env['hr.employee'].search(domain)
        if not all_employees:
            return

        if self.gender_ids:
            selected_genders = self.gender_ids.mapped('name')
            all_employees = all_employees.filtered(lambda e: e.gender in selected_genders)

        if self.tag_ids:
            selected_tag_ids = self.tag_ids.ids
            all_employees = all_employees.filtered(
                lambda e: any(tag.id in selected_tag_ids for tag in e.category_ids)
            )

        created_records = []

        mapping = {
            'monday': 'senin', 'tuesday': 'selasa', 'wednesday': 'rabu',
            'thursday': 'kamis', 'friday': 'jumat', 'saturday': 'sabtu', 'sunday': 'minggu',
        }
        selected_days = set(self.day_ids.mapped("name"))

        # 🔥 Siapkan pola shift per karyawan
        employee_patterns = {}
        for emp in all_employees:
            if emp.shift_config_id:
                work_days = emp.shift_config_id.work_days
                off_days = emp.shift_config_id.off_days
            else:
                work_days, off_days = 4, 2  # default

            cycle_len = work_days + off_days
            if emp.shift_start_date:
                days_diff = (self.tanggal_mulai - emp.shift_start_date).days
                offset = days_diff % cycle_len if days_diff >= 0 else 0
            else:
                offset = 0

            employee_patterns[emp.id] = {
                "work_days": work_days,
                "off_days": off_days,
                "cycle_len": cycle_len,
                "offset": offset,
            }

        current_date = self.tanggal_mulai

        while current_date <= self.tanggal_selesai:
            hari_eng = current_date.strftime("%A").lower()
            hari_indo = mapping.get(hari_eng)

            if hari_indo not in selected_days:
                current_date += timedelta(days=1)
                continue

            groups = self.department_ids if self.department_ids else [None]

            for dept in groups:
                if dept:
                    employees_in_group = all_employees.filtered(lambda e: e.department_id == dept)
                else:
                    employees_in_group = all_employees

                if not employees_in_group:
                    continue

                # 🔥 UPDATE - minimal 1 shift per type
                shift_types_needed = ['Shift Pagi', 'Shift Sore', 'Shift Malam']  # ganti sesuai nama shift
                shift_list_today = [
                    s for s in self.shift_ids
                    if not s.allowed_days or hari_indo in s.allowed_days.mapped("name")
                ]
                if not shift_list_today:
                    continue

                employee_list = list(employees_in_group)
                random.shuffle(employee_list)

                assigned_shifts_today = {st: False for st in shift_types_needed}

                # 🔥 Pastikan minimal 1 per shift
                for shift_type in shift_types_needed:
                    shift_obj = next((s for s in shift_list_today if s.name == shift_type), None)
                    if not shift_obj:
                        continue
                    for emp in employee_list:
                        # cek pola kerja-libur
                        pattern = employee_patterns.get(emp.id)
                        if pattern:
                            if emp.shift_start_date and current_date < emp.shift_start_date:
                                continue
                            days_since_start = (current_date - (emp.shift_start_date or self.tanggal_mulai)).days
                            pos_in_cycle = (days_since_start + pattern["offset"]) % pattern["cycle_len"]
                            if pos_in_cycle >= pattern["work_days"]:
                                continue  # libur sesuai pola

                        already = self.env['jadwal.shift.karyawan'].search_count([
                            ('tanggal', '=', current_date),
                            ('employee_id', '=', emp.id),
                        ])
                        if already:
                            continue

                        # cek no female
                        if getattr(emp, 'gender', False) == 'female' and getattr(shift_obj, 'no_female', False):
                            continue

                        # assign shift
                        rec = self.env['jadwal.shift.karyawan'].create({
                            'tanggal': current_date,
                            'employee_id': emp.id,
                            'shift_id': shift_obj.id,
                        })
                        created_records.append(rec.id)
                        assigned_shifts_today[shift_type] = True
                        break  # lanjut ke shift berikutnya

                # 🔥 Sisa employee acak normal
                for emp in employee_list:
                    already = self.env['jadwal.shift.karyawan'].search_count([
                        ('tanggal', '=', current_date),
                        ('employee_id', '=', emp.id),
                    ])
                    if already:
                        continue

                    # cek pola kerja-libur
                    pattern = employee_patterns.get(emp.id)
                    if pattern:
                        if emp.shift_start_date and current_date < emp.shift_start_date:
                            continue
                        days_since_start = (current_date - (emp.shift_start_date or self.tanggal_mulai)).days
                        pos_in_cycle = (days_since_start + pattern["offset"]) % pattern["cycle_len"]
                        if pos_in_cycle >= pattern["work_days"]:
                            continue  # libur sesuai pola

                    shift = random.choice(shift_list_today)
                    if getattr(emp, 'gender', False) == 'female' and getattr(shift, 'no_female', False):
                        alt_shift = next((s for s in shift_list_today if not getattr(s, 'no_female', False)), None)
                        if alt_shift:
                            shift = alt_shift
                        else:
                            continue

                    rec = self.env['jadwal.shift.karyawan'].create({
                        'tanggal': current_date,
                        'employee_id': emp.id,
                        'shift_id': shift.id,
                    })
                    created_records.append(rec.id)

            current_date += timedelta(days=1)

        self._send_email_notifications(created_records)

    def _send_email_notifications(self, record_ids):
        jadwal_model = self.env['jadwal.shift.karyawan']
        created_shifts = jadwal_model.browse(record_ids)

        karyawan_ids = created_shifts.mapped('employee_id')

        for karyawan in karyawan_ids:
            jadwal_karyawan = jadwal_model.search([
                ('employee_id', '=', karyawan.id),
                ('tanggal', '>=', self.tanggal_mulai),
                ('tanggal', '<=', self.tanggal_selesai),
            ])

            body_lines = []
            for rec in jadwal_karyawan.sorted(key=lambda r: r.tanggal):
                body_lines.append(f"{rec.tanggal}: {rec.shift_id.name}")

            body_html = "<br/>".join(body_lines)

            if karyawan.work_email:
                mail = self.env['mail.mail'].create({
                    'subject': f"Jadwal Shift Anda {self.tanggal_mulai} - {self.tanggal_selesai}",
                    'body_html': f"<p>Halo {karyawan.name},</p>"
                                 f"<p>Berikut jadwal shift Anda:</p>"
                                 f"<p>{body_html}</p>",
                    'email_to': karyawan.work_email,
                })
                mail.send()
