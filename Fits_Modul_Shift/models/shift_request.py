from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ShiftRequest(models.Model):
    _name = 'shift.request'
    _description = 'Shift Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'tanggal_permohonan desc'

    name = fields.Char(
        string='Nama Request',
        compute='_compute_name',
        store=True,
        readonly=True
    )

    tanggal_permohonan = fields.Date(
        string='Date of application',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    # employee_pengaju = fields.Many2one(
    #     comodel_name='hr.employee',
    #     string='Applicant',
    #     required=True,
    #     default=lambda self: self._get_default_employee()
    # )
    
    employee_pengaju = fields.Many2one(
        comodel_name='hr.employee',
        string='Applicant',
        required=True,
        default=lambda self: self._get_default_employee(),
    )

    
    shift_id = fields.Many2one(
        comodel_name='shift.karyawan',
        string='Shifts',
        required=True
    )

    alasan = fields.Text(
        string='Reason for request',
        required=True
    )

    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        tracking=True
    )

      # readonly dinamis pakai property
    def _check_readonly_employee_pengaju(self):
        self.ensure_one()
        if self.status in ('approved', 'rejected'):
            return True  # readonly untuk semua
        if self.env.user.has_group('Fits_Modul_Shift.group_shifting_manager'):
            return False  # manager editable
        return True  # user biasa readonly

    @api.onchange('status')
    def _onchange_status_readonly(self):
        for rec in self:
            rec.employee_pengaju_readonly = rec._check_readonly_employee_pengaju()

    employee_pengaju_readonly = fields.Boolean(compute='_compute_readonly_field')

    @api.depends('status')
    def _compute_readonly_field(self):
        for rec in self:
            rec.employee_pengaju_readonly = rec._check_readonly_employee_pengaju()
    
    # ======================= COMPUTE NAME =======================
    @api.depends('employee_pengaju')
    def _compute_name(self):
        for rec in self:
            if rec.employee_pengaju:
                rec.name = f"Shift {rec.employee_pengaju.name}"
            else:
                rec.name = "Shift Request"

    # ======================= ACTION BUTTONS =======================
    def action_submit(self):
        for rec in self:
            if rec.status != 'draft':
                raise UserError("Request hanya bisa diajukan dari status Draft.")
            rec.status = 'submitted'
            rec._notify_admin_manager()

    def action_approve(self):
        for rec in self:
            if rec.status != 'submitted':
                raise UserError("Hanya request dengan status 'Submitted' yang bisa disetujui.")
            
            # === Tambah ke Jadwal Shift Karyawan ===
            Jadwal = self.env['jadwal.shift.karyawan']
            existing = Jadwal.search([
                ('employee_id', '=', rec.employee_pengaju.id),
                ('shift_id', '=', rec.shift_id.id),
                ('tanggal', '=', rec.tanggal_permohonan)
            ], limit=1)

            if existing:
                # Kalau sudah ada, mungkin update aja (opsional)
                existing.write({
                    'shift_id': rec.shift_id.id,
                })
            else:
                # Kalau belum ada, buat baru
                Jadwal.create({
                    'employee_id': rec.employee_pengaju.id,
                    'shift_id': rec.shift_id.id,
                    'tanggal': rec.tanggal_permohonan,
                })

            rec.status = 'approved'
            rec._notify_applicant(approved=True)  # kirim notifikasi ke pengaju

    def action_reject(self):
        for rec in self:
            if rec.status != 'submitted':
                raise UserError("Hanya request dengan status 'Submitted' yang bisa ditolak.")
            rec.status = 'rejected'
            rec._notify_applicant(approved=False)  # kirim notifikasi ke pengaju
            
    def action_set_draft(self):
        for rec in self:
            if rec.status not in ['approved', 'rejected']:
                raise UserError("Hanya request dengan status Approved atau Rejected yang bisa dikembalikan ke Draft.")
            rec.status = 'draft'

      # ======================= EMAIL NOTIFICATION =======================
    def _notify_admin_manager(self):
        """Kirim notifikasi ke admin/manager ketika request diajukan"""
        group_manager = self.env.ref('Fits_Modul_Shift.group_shifting_manager', raise_if_not_found=False)
        if not group_manager:
            return

        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            shift_name = rec.shift_id.name if rec.shift_id else "Tidak ada shift"
            subject = f"[Shift Request] {rec.name} menunggu persetujuan"
            body_html = f"""
                <p>Shift Request telah diajukan oleh: <b>{rec.employee_pengaju.name}</b>.</p>
                <p><b>Shift yang diminta:</b> {shift_name}</p>
                <p>Silakan cek modul Shift Request untuk persetujuan lebih lanjut.</p>
            """

            for user in group_manager.users:
                if user.partner_id.email:  # ambil email partner
                    mail_values = {
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': user.partner_id.email,
                        'email_from': self.env.user.email or 'noreply@yourdomain.com',
                    }
                    Mail.create(mail_values).send()

    def _notify_applicant(self, approved=True):
        """Kirim notifikasi ke pengaju ketika request disetujui atau ditolak"""
        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            employee = rec.employee_pengaju
            if not employee.work_email:  # pastikan ada email karyawan
                continue

            status_text = "disetujui" if approved else "ditolak"
            subject = f"Shift Request {status_text.capitalize()}"
            body_html = f"""
                <p>Halo {employee.name},</p>
                <p>Shift Request <b>{rec.name}</b> Anda telah <b>{status_text}</b>.</p>
                <p>Silakan cek modul Shift Request untuk informasi lebih lanjut.</p>
            """

            mail_values = {
                'subject': subject,
                'body_html': body_html,
                'email_to': employee.work_email,
                'email_from': self.env.user.email or 'noreply@yourdomain.com',
            }
            Mail.create(mail_values).send()
            
    @api.model
    def _get_default_employee(self):
         # Cek apakah user saat ini memiliki group shifting
        if self.env.user.has_group('Fits_Modul_Shift.group_shifting_user'):
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            return employee.id if employee else False
            # Jika user tidak ada di group, kembalikan False atau None
        return False