from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

class TukarShiftKaryawan(models.Model):
    _name = 'tukar.shift.karyawan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tukar Shift Karyawan'
    _rec_name = 'name'
    _order = 'tanggal_permohonan desc'

    name = fields.Char(
        string='Application name',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    
    employee_pengganti = fields.Many2one(
        comodel_name='hr.employee',
        string='Replacement',
        required=True,
        domain="[('id','!=',employee_pengaju)]"
    )

    jadwal_shift_pengganti = fields.Many2one(
        comodel_name='jadwal.shift.karyawan',
        string='Alternate Schedule',
        domain="[('employee_id','=',employee_pengganti), ('tanggal','=',tanggal_permohonan)]",
        required=False
    )

    employee_pengaju = fields.Many2one(
        comodel_name='hr.employee',
        string='Applicant',
        required=True,
        default=lambda self: self._get_default_employee(),
        domain="[('id','!=',employee_pengganti)]"
    )
    
    jadwal_shift_pengaju = fields.Many2one(
        comodel_name='jadwal.shift.karyawan',
        string='Applicant schedule',
        domain="[('employee_id','=',employee_pengaju), ('tanggal','=',tanggal_permohonan)]",
        required=False
    )

    tanggal_permohonan = fields.Date(
        string='Application date',
        default=fields.Date.today,
        required=True
    )
    
    shift_type = fields.Selection(
        selection=[
            ('normal', 'Normal'),
            ('carter', 'Backup'),
            ('oncall', 'On-Call'),
        ],
        string='Shift swap type',
        default='normal',
        required=True
    )

    alasan = fields.Text(
        string='Reason for changing shifts',
        required=True,
    )

    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submited', 'Submited'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        readonly=True,
        copy=False
    )

    approved_by = fields.Many2one(
        comodel_name='res.users',
        string='Disetujui Oleh',
        readonly=True
    )

    approved_date = fields.Datetime(
        string='Tanggal Disetujui',
        readonly=True
    )
    
        # Compute readonly dinamis
    def _check_readonly_employee_fields(self):
        self.ensure_one()
        if self.status in ('approved', 'rejected'):
            return True  # readonly untuk semua
        if self.env.user.has_group('Fits_Modul_Shift.group_shifting_manager'):
            return False  # manager editable
        return True  # user biasa readonly

    @api.depends('status')
    def _compute_readonly_employee_fields(self):
        for rec in self:
            rec.employee_readonly = rec._check_readonly_employee_fields()

    # Field helper untuk readonly di XML
    employee_readonly = fields.Boolean(compute='_compute_readonly_employee_fields')

    # Helper field tombol
    show_btn_submit = fields.Boolean(compute='_compute_button_visibility')
    show_btn_approve_reject = fields.Boolean(compute='_compute_button_visibility')
    show_btn_set_draft = fields.Boolean(compute='_compute_button_visibility')

    @api.model
    def _get_default_employee(self):
        if self.env.user.has_group('Fits_Modul_Shift.group_shifting_user'):
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            return employee.id if employee else False
        return False
    @api.depends('status')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_btn_submit = rec.status == 'draft'
            rec.show_btn_approve_reject = rec.status == 'submited'
            rec.show_btn_set_draft = rec.status in ['approved', 'rejected']

    @api.depends('employee_pengaju', 'employee_pengganti', 'shift_type')
    def _compute_name(self):
        for rec in self:
            if rec.employee_pengaju and rec.employee_pengganti:
                rec.name = f'Tukar {rec.employee_pengaju.name} ↔ {rec.employee_pengganti.name} ({rec.shift_type})'
            else:
                rec.name = 'Permohonan Tukar Shift'
    
    # @api.onchange('employee_pengaju', 'tanggal_permohonan')
    # def _onchange_employee_pengaju(self):
    #     if self.employee_pengaju and self.tanggal_permohonan:
    #         return {
    #             'domain': {
    #                 'jadwal_shift_pengaju': [
    #                     ('employee_id', '=', self.employee_pengaju.id),
    #                     ('tanggal', '=', self.tanggal_permohonan),
    #                 ]
    #             }
    #         }
    
    @api.onchange('employee_pengaju', 'tanggal_permohonan')
    def _onchange_employee_pengaju(self):
        """Otomatis isi jadwal_shift_pengaju sesuai shift employee yang login"""
          # Cek apakah user saat ini termasuk group shifting
        if not self.env.user.has_group('Fits_Modul_Shift.group_shifting_user'):
            # Jika bukan, kosongkan field dan hentikan
            self.jadwal_shift_pengaju = False
            return
    
        if self.employee_pengaju and self.tanggal_permohonan:
            # Cari shift sesuai employee & tanggal
            shift = self.env['jadwal.shift.karyawan'].search([
                ('employee_id', '=', self.employee_pengaju.id),
                ('tanggal', '=', self.tanggal_permohonan),
            ], limit=1)

            if shift:
                self.jadwal_shift_pengaju = shift
                
            else:
            # Kosongkan kalau tidak ada jadwal
             self.jadwal_shift_pengaju = False

            return {
                'domain': {
                    'jadwal_shift_pengaju': [
                        ('employee_id', '=', self.employee_pengaju.id),
                        ('tanggal', '=', self.tanggal_permohonan),
                    ]
                }
            }

    @api.onchange('employee_pengganti', 'tanggal_permohonan')
    def _onchange_employee_pengganti(self):
        if self.employee_pengganti and self.tanggal_permohonan:
            return {
                'domain': {
                    'jadwal_shift_pengganti': [
                        ('employee_id', '=', self.employee_pengganti.id),
                        ('tanggal', '=', self.tanggal_permohonan),
                    ]
                }
            }

                
    def _backup_tukar_shift(self):
        history_obj = self.env['tukar.shift.karyawan.history']
        for rec in self:
            history_obj.create({
                'tukar_shift_id': rec.id,
                'jadwal_pengaju_before': rec.jadwal_shift_pengaju.id,
                'jadwal_pengganti_before': rec.jadwal_shift_pengganti.id,
                'employee_pengaju': rec.employee_pengaju.id,
                'employee_pengganti': rec.employee_pengganti.id,
                'tanggal_backup': fields.Date.today(),
                'status_backup': rec.status,
                'shift_type_backup': rec.shift_type,
            })


    # def action_submit(self):
    #     for rec in self:
    #         if rec.status != 'draft':
    #             raise ValidationError("Hanya permohonan Draft yang bisa di-submit.")
    #         rec.status = 'submited'
    #         rec._send_email_to_managers()
    
    def action_submit(self):
        for rec in self:
            if rec.status != 'draft':
                raise ValidationError("Hanya permohonan Draft yang bisa di-submit.")

            # Isi jadwal_shift_pengaju otomatis jika belum ada
            if not rec.jadwal_shift_pengaju and rec.employee_pengaju and rec.tanggal_permohonan:
                shift = self.env['jadwal.shift.karyawan'].search([
                    ('employee_id', '=', rec.employee_pengaju.id),
                    ('tanggal', '=', rec.tanggal_permohonan),
                ], limit=1)
                if shift:
                    rec.jadwal_shift_pengaju = shift

            # Ubah status
            rec.status = 'submited'  # perbaiki typo 'submited' -> 'submitted'

            # Kirim email ke manager
            rec._send_email_to_managers()


    def action_approve(self):
        if not (self.env.user.has_group('Fits_Modul_Shift.group_shifting_manager') or
                self.env.user.has_group('Fits_Modul_Shift.group_shifting_user')):
            raise AccessError("Anda tidak memiliki hak akses untuk menyetujui permohonan ini.")


        for rec in self:
            if rec.status != 'submited':
                raise ValidationError("Hanya permohonan Submited yang bisa disetujui.")

            if not rec.jadwal_shift_pengaju:
                raise ValidationError("Jadwal shift pengaju harus diisi.")

            rec._backup_tukar_shift()

            pengaju = rec.jadwal_shift_pengaju
            pengganti = rec.jadwal_shift_pengganti

            if rec.shift_type == 'normal':
                if not pengganti:
                    raise ValidationError("Jadwal shift pengganti harus diisi untuk tipe Normal.")
                temp_emp = pengaju.employee_id
                pengaju.employee_id = pengganti.employee_id
                pengganti.employee_id = temp_emp

            elif rec.shift_type == 'carter':
                if not pengganti:
                    raise ValidationError("Pengganti harus diisi untuk tipe Carter.")

                jadwal_baru = pengaju.copy({
                    'employee_id': rec.employee_pengganti.id,
                    'shift_type': 'normal',
                    'pengaju_id': rec.employee_pengaju.id,
                    'jenis_shift': pengaju.jenis_shift,
                    'active': True,
                })

                pengaju.active = False

            elif rec.shift_type == 'oncall':
                if not rec.employee_pengganti:
                    raise ValidationError("Pengganti harus diisi untuk tipe On-call.")

                pengganti = self.env['jadwal.shift.karyawan'].search([
                    ('employee_id', '=', rec.employee_pengganti.id),
                    ('tanggal', '=', pengaju.tanggal),
                    ('active', '=', True)
                ], limit=1)

                if pengganti:
                    temp_emp = pengaju.employee_id
                    pengaju.employee_id = pengganti.employee_id
                    pengganti.employee_id = temp_emp
                else:
                    pengaju.employee_id = rec.employee_pengganti
            else:
                raise ValidationError("Tipe tukar shift tidak dikenal.")

            rec.status = 'approved'
            rec.approved_by = self.env.user
            rec.approved_date = fields.Datetime.now()
            rec._notify_karyawan_shift()

    def action_reject(self):
        """Tolak permohonan shift + kirim email ke pengaju"""
        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            if rec.status != 'submited':
                raise ValidationError("Hanya permohonan Submited yang bisa ditolak.")
            rec.status = 'rejected'

            employee = rec.employee_pengaju
            if not employee or not employee.work_email:
                continue

            body_html = f"""
                <p>Halo {employee.name},</p>
                <p>Permohonan tukar shift Anda <b>ditolak</b>.</p>
                <p>Silakan cek modul Tukar Shift untuk informasi lebih lanjut.</p>
            """
            mail_values = {
                'subject': 'Permohonan Tukar Shift Ditolak',
                'body_html': body_html,
                'email_to': employee.work_email,
                'email_from': self.env.user.email or 'noreply@yourdomain.com',
            }
            Mail.create(mail_values).send()


    def action_set_draft(self):
        for rec in self:
            if rec.status not in ['approved', 'rejected']:
                raise ValidationError("Hanya permohonan Disetujui atau Ditolak yang bisa dikembalikan ke Draft.")
            rec.status = 'draft'

    @api.onchange('shift_type')
    def _onchange_shift_type(self):
        if self.shift_type == 'oncall':
            self.jadwal_shift_pengganti = False

    def write(self, vals):
        for rec in self:
            if rec.status in ['approved', 'rejected']:
                protected_fields = {
                    'employee_pengaju', 'jadwal_shift_pengaju',
                    'employee_pengganti', 'jadwal_shift_pengganti',
                    'tanggal_permohonan', 'shift_type', 'alasan'
                }
                if any(field in vals for field in protected_fields):
                    raise ValidationError("Data tidak bisa diubah setelah Disetujui atau Ditolak.")
        return super().write(vals)

    @api.constrains('shift_type', 'jadwal_shift_pengganti')
    def _check_jadwal_pengganti_required(self):
        for rec in self:
            if rec.shift_type != 'oncall' and not rec.jadwal_shift_pengganti:
                raise ValidationError("Jadwal Pengganti wajib diisi untuk tipe Normal atau Backup.")

    @api.constrains('employee_pengaju', 'employee_pengganti')
    def _check_employees_different(self):
        for rec in self:
            if rec.employee_pengaju and rec.employee_pengganti and rec.employee_pengaju == rec.employee_pengganti:
                raise ValidationError("Pengaju dan Pengganti tidak boleh sama.")

    @api.model
    def create(self, vals):
        record = super(TukarShiftKaryawan, self).create(vals)
        record._send_email_to_managers()
        return record

    def _send_email_to_managers(self):
        """Kirim email ke semua manager ketika ada permohonan tukar shift baru"""
        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            group = self.env.ref('Fits_Modul_Shift.group_shifting_manager', raise_if_not_found=False)
            if not group:
                continue

            users = group.users.filtered(lambda u: u.email)
            if not users:
                continue

            for user in users:
                subject = f'Permohonan Tukar Shift Baru dari {rec.employee_pengaju.name}'
                body_html = f"""
                    <p>Halo {user.name},</p>
                    <p>Ada permohonan tukar shift baru dari <b>{rec.employee_pengaju.name}</b>.</p>
                    <p><b>Alasan:</b> {rec.alasan or '-'}</p>
                    <p>Silakan cek modul Tukar Shift untuk informasi lebih lanjut.</p>
                """

                mail_values = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': user.email,
                    'email_from': rec.env.user.email or 'noreply@yourdomain.com',
                }
                Mail.create(mail_values).send()


    def _notify_karyawan_shift(self):
        """Notifikasi ke pengaju & pengganti ketika shift disetujui"""
        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            if not rec.employee_pengaju.work_email or not rec.employee_pengganti.work_email:
                continue  # Skip jika tidak lengkap work_email

            pengaju_name = rec.employee_pengaju.name
            pengganti_name = rec.employee_pengganti.name

            if rec.shift_type == 'normal':
                body_html = f"""
                    <p>Halo,</p>
                    <p>Permohonan tukar shift telah <b>disetujui</b> dengan tipe <b>Normal</b>.</p>
                    <ul>
                        <li><b>{pengaju_name}</b> bertukar shift dengan <b>{pengganti_name}</b>.</li>
                    </ul>
                    <p>Silakan cek jadwal shift terbaru Anda.</p>
                """
            elif rec.shift_type == 'carter':
                body_html = f"""
                    <p>Halo,</p>
                    <p>Permohonan tukar shift telah <b>disetujui</b> dengan tipe <b>Backup</b>.</p>
                    <ul>
                        <li><b>{pengganti_name}</b> telah menggantikan shift milik <b>{pengaju_name}</b>.</li>
                    </ul>
                    <p>Silakan cek jadwal shift terbaru Anda.</p>
                """
            elif rec.shift_type == 'oncall':
                body_html = f"""
                    <p>Halo,</p>
                    <p>Permohonan tukar shift telah <b>disetujui</b> dengan tipe <b>On-Call</b>.</p>
                    <ul>
                        <li><b>{pengganti_name}</b> akan menggantikan <b>{pengaju_name}</b> sebagai on-call.</li>
                    </ul>
                    <p>Silakan cek jadwal shift terbaru Anda.</p>
                """
            else:
                body_html = f"""
                    <p>Halo,</p>
                    <p>Permohonan tukar shift Anda telah disetujui.</p>
                    <p>Silakan cek jadwal shift terbaru Anda.</p>
                """

            recipients = f"{rec.employee_pengaju.work_email},{rec.employee_pengganti.work_email}"
            mail_values = {
                'subject': 'Notifikasi Tukar Shift Disetujui',
                'body_html': body_html,
                'email_to': recipients,
                'email_from': self.env.user.email or 'noreply@yourdomain.com',
            }
            Mail.create(mail_values).send()


class TukarShiftKaryawanHistory(models.Model):
    _name = 'tukar.shift.karyawan.history'
    _description = 'History Tukar Shift Karyawan'
    _order = 'tanggal_backup desc'

    tukar_shift_id = fields.Many2one('tukar.shift.karyawan', string='Permohonan Tukar Shift')
    jadwal_pengaju_before = fields.Many2one('jadwal.shift.karyawan', string='Jadwal Pengaju (Before)')
    jadwal_pengganti_before = fields.Many2one('jadwal.shift.karyawan', string='Jadwal Pengganti (Before)')
    employee_pengaju = fields.Many2one('hr.employee', string='Pengaju')
    employee_pengganti = fields.Many2one('hr.employee', string='Pengganti')
    tanggal_backup = fields.Date(string='Tanggal Backup')
    status_backup = fields.Selection(
        selection=[('draft', 'Draft'), ('submited', 'Submited'), ('approved', 'Disetujui'), ('rejected', 'Ditolak')],
        string='Status Backup'
    )
    shift_type_backup = fields.Selection(
        selection=[('normal', 'Normal'), ('carter', 'Carter'), ('oncall', 'On-Call')],
        string='Tipe Tukar Shift Backup'
    )
