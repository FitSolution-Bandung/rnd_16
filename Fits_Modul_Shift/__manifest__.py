{
    'name': 'Fits Manajemen Shift',
    'version': '18.1',
    'summary': 'Manajemen Shift Kerja Karyawan',
    'category': 'Human Resources',
    'author': 'PT Fujicon Priangan Perdana',
    'website': 'https://websitepan.com',
    'license': 'LGPL-3',
    'application': True,
    'auto_install': False,
    'depends': [
        'base',
        'hr',
        'hr_attendance',
        'mail',
        
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Default Data
        # 'data/default_shift_data.xml',
        'data/email_template_lembur.xml',
        'data/email_template_jadwal_shift.xml',
        'data/tukar_shift_sequence.xml',
        'data/hari_minggu_data.xml',
        'data/gender_reference_data.xml',
             
        # Actions
        'views/actions.xml',
        
        # Views - Main Menu
        'views/menu.xml',
        
        # Views - Master
        'views/shift_views.xml',
        'views/jadwal_shift_views.xml',
        'views/jadwal_shift_wizard_views.xml',
        'views/tukar_shift_views.xml',
        'views/riwayat_shift_views.xml',
        'views/shift_statistik_views.xml',
        'views/hr_attendance_views.xml',
        'views/shift_laporan_views.xml',
        'views/shift_request_views.xml',
        'views/shift_configuration_pattern_views.xml',
        'views/hr_employee_shift_views.xml',
        
        'wizard/report_jadwal.xml',    
        # Report
        'report/report_jadwal_shift.xml',
     
        
        
        
        
        
        
    ],
    'assets': {
        'web.assets_backend': [
            'Fits_Modul_Shift/static/src/css/custom_shift.css',
            'Fits_Modul_Shift/static/src/css/shift_kanban.css',
            'Fits_Modul_Shift/static/src/css/shift_style.css',
            'Fits_Modul_Shift/static/src/js/shift_custom.js',
        ],
    },
    'images': ['static/description/icon.png'],
}
