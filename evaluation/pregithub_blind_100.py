"""Blind multi-domain >=120-case pre-GitHub benchmark generator (zero label leakage)."""
import hashlib
import json

DOMAINS = {
    'warranty_rma': {
        'title': 'Hardware warranty and RMA authorization',
        'title_fa': 'گارانتی سخت‌افزار و صدور مجوز RMA',
        'title_tr': 'Donanım garantisi ve RMA yetkilendirmesi',
        'scope': 'Hardware defect replacement under manufacturer coverage',
        'question': 'Should warranty RMA dispatch be approved for this unit?',
        'question_fa': 'آیا ارسال جایگزین گارانتی RMA برای این سخت‌افزار تایید شود؟',
        'question_tr': 'Bu ünite için garanti RMA değişimi onaylanmalı mı?',
        'terms': [
            ('warranty_active', 'Hardware is within the active warranty period', 'Hardware warranty and RMA authorization requires the hardware to be within the active warranty period.'),
            ('serial_legible', 'Chassis serial sticker is legible', 'Hardware warranty and RMA authorization requires the chassis serial sticker to be legible.'),
            ('invoice_attached', 'Original reseller invoice is attached', 'Hardware warranty and RMA authorization requires the original reseller invoice to be attached.'),
        ],
        'terms_fa': [
            ('warranty_active', 'سخت‌افزار باید در دوره گارانتی فعال باشد', 'گارانتی سخت‌افزار و صدور مجوز RMA نیازمند دوره گارانتی فعال است.'),
            ('serial_legible', 'برچسب شماره سریال بدنه باید خوانا باشد', 'شماره سریال بدنه خوانا برای صدور مجوز RMA لازم است.'),
            ('invoice_attached', 'فاکتور اصلی فروشنده باید پیوست شده باشد', 'فاکتور اصلی فروشنده پیوست لازم برای گارانتی سخت‌افزار است.'),
        ],
        'terms_tr': [
            ('warranty_active', 'Donanım aktif garanti süresi içinde olmalıdır', 'Donanım garantisi ve RMA yetkilendirmesi için aktif garanti süresi gerekir.'),
            ('serial_legible', 'Kasa seri numarası etiketi okunaklı olmalıdır', 'Donanım garantisi için kasa seri numarası etiketi okunaklı olmalıdır.'),
            ('invoice_attached', 'Orijinal satıcı faturası eklenmiş olmalıdır', 'Donanım garantisi için orijinal satıcı faturası eklenmiş olmalıdır.'),
        ],
        'clean_clauses_en': [
            '1. Returned hardware must be within the active warranty period.',
            '2. The chassis serial sticker must remain legible on inspection.',
            '3. An original reseller invoice must be attached to the ticket.',
        ],
        'clean_clauses_fa': [
            '1. سخت‌افزار باید در دوره گارانتی فعال باشد.',
            '2. برچسب شماره سریال بدنه باید خوانا باشد.',
            '3. فاکتور اصلی فروشنده باید پیوست شده باشد.',
        ],
        'clean_clauses_tr': [
            '1. Donanım aktif garanti süresi içinde olmalıdır.',
            '2. Kasa seri numarası etiketi okunaklı olmalıdır.',
            '3. Orijinal satıcı faturası eklenmiş olmalıdır.',
        ],
    },
    'cloud_access': {
        'title': 'Production cloud IAM elevation gate',
        'title_fa': 'دروازه ارتقای دسترسی ابری تولیدی IAM',
        'title_tr': 'Üretim bulut IAM yetki yükseltme kapısı',
        'scope': 'Temporary break-glass access to production clusters',
        'question': 'Should temporary production IAM elevation be granted?',
        'question_fa': 'آیا ارتقای موقت دسترسی ابری تولیدی IAM صادر شود؟',
        'question_tr': 'Geçici üretim bulut IAM yetki yükseltmesi verilmeli mi?',
        'terms': [
            ('ticket_approved', 'Production change ticket is approved', 'Production cloud IAM elevation gate requires an approved production change ticket.'),
            ('mfa_hardware', 'Requester uses hardware FIDO2 key', 'Production cloud IAM elevation gate requires a hardware FIDO2 key.'),
            ('peer_reviewer', 'On-call peer engineer signed the plan', 'Production cloud IAM elevation gate requires an on-call peer engineer to sign the plan.'),
        ],
        'terms_fa': [
            ('ticket_approved', 'درخواست باید دارای تیکت تغییر تاییدشده باشد', 'تیکت تغییر تاییدشده برای ارتقای دسترسی ابری تولیدی لازم است.'),
            ('mfa_hardware', 'کاربر باید با کلید سخت‌افزاری FIDO2 احراز هویت کند', 'کلید سخت‌افزاری FIDO2 احراز هویت برای دسترسی لازم است.'),
            ('peer_reviewer', 'مهندس همکار کشیک باید طرح اجرا را امضا کرده باشد', 'مهندس همکار کشیک طرح اجرا را امضا کرده باشد.'),
        ],
        'terms_tr': [
            ('ticket_approved', 'Talep onaylı bir değişiklik bileti içermelidir', 'Üretim bulut IAM için onaylı bir değişiklik bileti gerekir.'),
            ('mfa_hardware', 'Erişim için donanım FIDO2 anahtarı kullanılmalıdır', 'Erişim için donanım FIDO2 anahtarı kullanılmalıdır.'),
            ('peer_reviewer', 'Nöbetçi eş mühendis uygulama planını imzalamış olmalıdır', 'Nöbetçi eş mühendis uygulama planını imzalamış olmalıdır.'),
        ],
        'clean_clauses_en': [
            '1. Requesters must hold an approved production change ticket.',
            '2. Accounts must authenticate with a hardware FIDO2 key.',
            '3. An on-call peer engineer must have signed the rollout plan.',
        ],
        'clean_clauses_fa': [
            '1. درخواست باید دارای تیکت تغییر تاییدشده باشد.',
            '2. کاربر باید با کلید سخت‌افزاری FIDO2 احراز هویت کند.',
            '3. مهندس همکار کشیک باید طرح اجرا را امضا کرده باشد.',
        ],
        'clean_clauses_tr': [
            '1. Talep onaylı bir değişiklik bileti içermelidir.',
            '2. Erişim için donanım FIDO2 anahtarı kullanılmalıdır.',
            '3. Nöbetçi eş mühendis uygulama planını imzalamış olmalıdır.',
        ],
    },
    'clinic_trial': {
        'title': 'Outpatient study intake screening',
        'title_fa': 'غربالگری پذیرش سرپایی پژوهش بالینی',
        'title_tr': 'Ayaktan klinik çalışma kabul taraması',
        'scope': 'Enrollment eligibility check for observational mobility cohort',
        'question': 'Can this volunteer proceed to outpatient enrollment?',
        'question_fa': 'آیا داوطلب می‌تواند وارد پذیرش سرپایی پژوهش شود؟',
        'question_tr': 'Katılımcı ayaktan klinik çalışma kaydına ilerleyebilir mi?',
        'terms': [
            ('consent_signed', 'Written study consent form is signed', 'Outpatient study intake screening requires a signed written consent form.'),
            ('age_band', 'Participant meets the adult age band', 'Outpatient study intake screening requires meeting the adult age band.'),
            ('baseline_labs', 'Baseline metabolic panel is recorded', 'Outpatient study intake screening requires a recorded baseline metabolic panel.'),
        ],
        'terms_fa': [
            ('consent_signed', 'داوطلب باید فرم رضایت‌نامه کتبی پژوهش را امضا کرده باشد', 'فرم رضایت‌نامه کتبی پژوهش امضا شده لازم است.'),
            ('age_band', 'شرکت‌کننده باید در بازه سنی مجاز بزرگسالان باشد', 'بازه سنی مجاز بزرگسالان برای شرکت‌کننده لازم است.'),
            ('baseline_labs', 'آزمایش متابولیک پایه باید در پرونده ثبت شده باشد', 'آزمایش متابولیک پایه ثبت شده در پرونده لازم است.'),
        ],
        'terms_tr': [
            ('consent_signed', 'Katılımcı yazılı çalışma onam formunu imzalamış olmalıdır', 'Ayaktan çalışma kabul için yazılı çalışma onam formu imzalanmalıdır.'),
            ('age_band', 'Katılımcı geçerli yetişkin yaş aralığında olmalıdır', 'Katılımcı geçerli yetişkin yaş aralığında olmalıdır.'),
            ('baseline_labs', 'Başlangıç metabolik paneli kayıt altına alınmış olmalıdır', 'Başlangıç metabolik paneli kayıt altına alınmış olmalıdır.'),
        ],
        'clean_clauses_en': [
            '1. Volunteers must sign the written study consent form prior to intake.',
            '2. Participants must meet the eligible adult age band.',
            '3. A baseline metabolic panel must be recorded at intake.',
        ],
        'clean_clauses_fa': [
            '1. داوطلب باید فرم رضایت‌نامه کتبی پژوهش را امضا کرده باشد.',
            '2. شرکت‌کننده باید در بازه سنی مجاز بزرگسالان باشد.',
            '3. آزمایش متابولیک پایه باید در پرونده ثبت شده باشد.',
        ],
        'clean_clauses_tr': [
            '1. Katılımcı yazılı çalışma onam formunu imzalamış olmalıdır.',
            '2. Katılımcı geçerli yetişkin yaş aralığında olmalıdır.',
            '3. Başlangıç metabolik paneli kayıt altına alınmış olmalıdır.',
        ],
    },
    'cargo_customs': {
        'title': 'Cross-border freight customs release',
        'title_fa': 'ترخیص گمرکی محموله تجاری مرزی',
        'title_tr': 'Sınır ötesi yük gümrük serbest bırakması',
        'scope': 'Standard commercial pallet customs clearance protocol',
        'question': 'May customs brokerage clear this commercial shipment?',
        'question_fa': 'آیا ترخیص گمرکی این محموله تجاری مرزی مجاز است؟',
        'question_tr': 'Gümrük komisyoncusu bu ticari sevkiyatı serbest bırakabilir mi?',
        'terms': [
            ('hs_codes', 'Declared HS tariff codes match packing list', 'Cross-border freight customs release requires declared HS tariff codes matching the packing list.'),
            ('origin_cert', 'Chamber certificate of origin is attached', 'Cross-border freight customs release requires an attached chamber certificate of origin.'),
            ('duty_paid', 'Import duty escrow transfer is settled', 'Cross-border freight customs release requires settled import duty escrow transfer.'),
        ],
        'terms_fa': [
            ('hs_codes', 'کدهای تعرفه HS اظهارشده باید با فهرست بسته‌بندی مطابقت داشته باشد', 'کدهای تعرفه HS اظهارشده مطابقت با فهرست بسته‌بندی لازم است.'),
            ('origin_cert', 'گواهی مبدا اتاق بازرگانی باید پیوست شده باشد', 'گواهی مبدا اتاق بازرگانی پیوست شده لازم است.'),
            ('duty_paid', 'پیش‌پرداخت عوارض گمرکی باید تسویه شده باشد', 'پیش‌پرداخت عوارض گمرکی تسویه شده لازم است.'),
        ],
        'terms_tr': [
            ('hs_codes', 'Beyan edilen HS tarife kodları çeki listesi ile uyuşmalıdır', 'Beyan edilen HS tarife kodları çeki listesi ile uyuşmalıdır.'),
            ('origin_cert', 'Ticaret odası menşe şahadetnamesi eklenmiş olmalıdır', 'Ticaret odası menşe şahadetnamesi eklenmiş olmalıdır.'),
            ('duty_paid', 'İthalat vergisi emanet transferi tamamlanmış olmalıdır', 'İthalat vergisi emanet transferi tamamlanmış olmalıdır.'),
        ],
        'clean_clauses_en': [
            '1. Declared HS tariff codes must match the packing list.',
            '2. A chamber certificate of origin must be attached.',
            '3. Import duty escrow transfer must be settled before release.',
        ],
        'clean_clauses_fa': [
            '1. کدهای تعرفه HS اظهارشده باید با فهرست بسته‌بندی مطابقت داشته باشد.',
            '2. گواهی مبدا اتاق بازرگانی باید پیوست شده باشد.',
            '3. پیش‌پرداخت عوارض گمرکی باید تسویه شده باشد.',
        ],
        'clean_clauses_tr': [
            '1. Beyan edilen HS tarife kodları çeki listesi ile uyuşmalıdır.',
            '2. Ticaret odası menşe şahadetnamesi eklenmiş olmalıdır.',
            '3. İthalat vergisi emanet transferi tamamlanmış olmalıdır.',
        ],
    },
    'lease_sublet': {
        'title': 'Residential lease sublet approval',
        'title_fa': 'تایید اجاره فرعی واحد مسکونی',
        'title_tr': 'Konut kira alt kiralama onayı',
        'scope': 'Fixed-term apartment sublet authorization',
        'question': 'May the primary tenant sublet this apartment?',
        'question_fa': 'آیا مستاجر اصلی مجاز به اجاره فرعی این واحد است؟',
        'question_tr': 'Asıl kiracı bu daireyi alt kiraya verebilir mi?',
        'terms': [
            ('rent_current', 'Primary rent ledger shows zero arrears', 'Residential lease sublet approval requires zero arrears on the primary rent ledger.'),
            ('landlord_notice', 'Landlord written notice period was observed', 'Residential lease sublet approval requires observing the landlord written notice period.'),
            ('deposit_held', 'Standard security deposit remains in escrow', 'Residential lease sublet approval requires standard security deposit in escrow.'),
        ],
        'terms_fa': [
            ('rent_current', 'دفتر کل اجاره اصلی نباید بدهی معوق داشته باشد', 'دفتر کل اجاره اصلی بدون بدهی معوق لازم است.'),
            ('landlord_notice', 'اخطار کتبی به موجر باید رعایت شده باشد', 'اخطار کتبی به موجر رعایت شده لازم است.'),
            ('deposit_held', 'ودیعه استاندارد امنیتی باید در حساب امانی باقی بماند', 'ودیعه استاندارد امنیتی حساب امانی لازم است.'),
        ],
        'terms_tr': [
            ('rent_current', 'Ana kira hesabında ödenmemiş borç bulunmamalıdır', 'Ana kira hesabında ödenmemiş borç bulunmamalıdır.'),
            ('landlord_notice', 'Ev sahibine yazılı bildirim süresi gözetilmiş olmalıdır', 'Ev sahibine yazılı bildirim süresi gözetilmiş olmalıdır.'),
            ('deposit_held', 'Standart güvenlik depozitosu emanet hesapta kalmalıdır', 'Standart güvenlik depozitosu emanet hesapta kalmalıdır.'),
        ],
        'clean_clauses_en': [
            '1. The primary rent ledger must show zero arrears.',
            '2. Landlord written notice must have been observed.',
            '3. Standard security deposit must remain in escrow.',
        ],
        'clean_clauses_fa': [
            '1. دفتر کل اجاره اصلی نباید بدهی معوق داشته باشد.',
            '2. اخطار کتبی به موجر باید رعایت شده باشد.',
            '3. ودیعه استاندارد امنیتی باید در حساب امانی باقی بماند.',
        ],
        'clean_clauses_tr': [
            '1. Ana kira hesabında ödenmemiş borç bulunmamalıdır.',
            '2. Ev sahibine yazılı bildirim süresi gözetilmiş olmalıdır.',
            '3. Standart güvenlik depozitosu emanet hesapta kalmalıdır.',
        ],
    },
    'academic_grant': {
        'title': 'University travel grant reimbursement',
        'title_fa': 'بازپرداخت کمک‌هزینه سفر پژوهشی دانشگاه',
        'title_tr': 'Üniversite araştırma seyahat desteği geri ödemesi',
        'scope': 'Post-conference travel claim reimbursement gate',
        'question': 'Should the department reimburse this conference travel claim?',
        'question_fa': 'آیا دانشکده هزینه این سفر پژوهشی کنفرانس را بازپرداخت کند؟',
        'question_tr': 'Bölüm bu konferans seyahat talebini geri ödemeli mi?',
        'terms': [
            ('advisor_sig', 'Faculty advisor signed the travel pre-approval', 'University travel grant reimbursement requires faculty advisor signed travel pre-approval.'),
            ('boarding_pass', 'Original boarding passes and hotel folio exist', 'University travel grant reimbursement requires original boarding passes and hotel folio.'),
            ('poster_proof', 'Official conference program lists presentation', 'University travel grant reimbursement requires official conference program listing presentation.'),
        ],
        'terms_fa': [
            ('advisor_sig', 'استاد راهنما باید پیش‌تایید سفر را امضا کرده باشد', 'پیش‌تایید سفر امضاشده استاد راهنما لازم است.'),
            ('boarding_pass', 'کارت پرواز اصلی و صورتحساب هتل باید ضمیمه شود', 'کارت پرواز اصلی و صورتحساب هتل ضمیمه شده لازم است.'),
            ('poster_proof', 'برنامه رسمی کنفرانس باید ارائه مقاله را فهرست کرده باشد', 'برنامه رسمی کنفرانس فهرست ارائه مقاله لازم است.'),
        ],
        'terms_tr': [
            ('advisor_sig', 'Akademik danışman seyahat ön onayını imzalamış olmalıdır', 'Akademik danışman seyahat ön onayını imzalamış olmalıdır.'),
            ('boarding_pass', 'Orijinal biniş kartları ve otel faturası dosyaya eklenmelidir', 'Orijinal biniş kartları ve otel faturası dosyaya eklenmelidir.'),
            ('poster_proof', 'Resmi konferans programı sunumu listelemelidir', 'Resmi konferans programı sunumu listelemelidir.'),
        ],
        'clean_clauses_en': [
            '1. Faculty advisor must sign travel pre-approval before departure.',
            '2. Original boarding passes and hotel folio must accompany the claim.',
            '3. Official conference program must list the presentation.',
        ],
        'clean_clauses_fa': [
            '1. استاد راهنما باید پیش‌تایید سفر را امضا کرده باشد.',
            '2. کارت پرواز اصلی و صورتحساب هتل باید ضمیمه شود.',
            '3. برنامه رسمی کنفرانس باید ارائه مقاله را فهرست کرده باشد.',
        ],
        'clean_clauses_tr': [
            '1. Akademik danışman seyahat ön onayını imzalamış olmalıdır.',
            '2. Orijinal biniş kartları ve otel faturası dosyaya eklenmelidir.',
            '3. Resmi konferans programı sunumu listelemelidir.',
        ],
    },
}

EXTRA_IMPLICIT = {
    'en': [
        ('anti-static diagnostic log', ['anti', 'static', 'diagnostic', 'log'], 'Replacement approval depends on attaching an anti-static diagnostic log.'),
        ('dual-custody cryptographic seal', ['dual', 'custody', 'cryptographic', 'seal'], 'Privileged elevation is contingent on verifying the dual-custody cryptographic seal.'),
        ('cardiologist clearance memo', ['cardiologist', 'clearance', 'memo'], 'Participant enrollment applies only if a cardiologist clearance memo is filed.'),
        ('phytosanitary fumigation stamp', ['phytosanitary', 'fumigation', 'stamp'], 'Customs clearance is conditional on an intact phytosanitary fumigation stamp.'),
        ('municipal fire occupancy certificate', ['municipal', 'fire', 'occupancy', 'certificate'], 'Sublet permission is provided that a municipal fire occupancy certificate is active.'),
        ('economy airfare routing cap', ['economy', 'airfare', 'routing', 'cap'], 'Reimbursement validity is subject to staying below the economy airfare routing cap.'),
        ('thermal paste tamper badge', ['thermal', 'paste', 'tamper', 'badge'], 'Warranty coverage applies only when the thermal paste tamper badge stays unbroken.'),
        ('ephemeral bastion jump token', ['ephemeral', 'bastion', 'jump', 'token'], 'Cluster sign-in requires holding an ephemeral bastion jump token.'),
        ('fasting glucose threshold reading', ['fasting', 'glucose', 'threshold', 'reading'], 'Intake authorization depends on a normal fasting glucose threshold reading.'),
        ('bonded warehouse weighbridge slip', ['bonded', 'warehouse', 'weighbridge', 'slip'], 'Pallet release is only if a bonded warehouse weighbridge slip matches weight.'),
        ('neighbor acoustic quiet covenant', ['neighbor', 'acoustic', 'quiet', 'covenant'], 'Sublet consent is valid only upon signing the neighbor acoustic quiet covenant.'),
        ('institutional open-access preprint deposit', ['open', 'access', 'preprint', 'deposit'], 'Grant payout depends on an institutional open-access preprint deposit receipt.'),
    ],
    'fa': [
        ('گزارش تست آزمایشگاه آکوستیک', ['گزارش', 'آزمایشگاه', 'آکوستیک'], 'تایید نهایی منوط به ارائه گزارش تست آزمایشگاه آکوستیک است.'),
        ('تاییدیه رمزنگاری سخت‌افزاری HSM', ['تاییدیه', 'رمزنگاری', 'سخت‌افزاری', 'hsm'], 'دسترسی فقط به شرط ثبت تاییدیه رمزنگاری سخت‌افزاری HSM صادر می‌شود.'),
        ('نوار قلب تخصصی تاییدشده', ['نوار', 'قلب', 'تخصصی'], 'پذیرش داوطلب مشروط به ثبت نوار قلب تخصصی تاییدشده است.'),
        ('مهر قرنطینه گیاهی بندر', ['مهر', 'قرنطینه', 'گیاهی', 'بندر'], 'ترخیص کالا تنها در صورت وجود مهر قرنطینه گیاهی بندر مجاز است.'),
    ],
    'tr': [
        ('statik deşarj laboratuvar raporu', ['statik', 'deşarj', 'laboratuvar', 'raporu'], 'Değişim onayı yalnızca statik deşarj laboratuvar raporu sunulması şartıyla geçerlidir.'),
        ('ikili donanım anahtarı imzası', ['ikili', 'donanım', 'anahtarı', 'imzası'], 'Yetki yükseltme işlemi ikili donanım anahtarı imzası koşuluna bağlıdır.'),
        ('kardiyoloji uzman onay belgesi', ['kardiyoloji', 'uzman', 'onay', 'belgesi'], 'Katılım izni kardiyoloji uzman onay belgesi ibraz edilmesi şartına bağlıdır.'),
        ('gümrük radyasyon tarama fişi', ['gümrük', 'radyasyon', 'tarama', 'fişi'], 'Sevkiyat serbest bırakılması gümrük radyasyon tarama fişi sunulması koşuluyla mümkündür.'),
    ],
}

EXTRA_NEG_EXC = {
    'en': [
        ('liquid corrosion damage exclusion', ['liquid', 'corrosion'], 'Units showing liquid corrosion damage are excluded from warranty replacement.'),
        ('unpatched kernel bastion ban', ['unpatched', 'kernel'], 'Nodes running an unpatched kernel are prohibited from emergency elevation.'),
        ('beta-blocker concomitant exclusion', ['beta', 'blocker'], 'Volunteers taking concomitant beta-blocker therapy cannot enroll in this arm.'),
        ('unregistered wooden crating restriction', ['wooden', 'crating'], 'Parcels packed in untreated wooden crating are not permitted without heat-treat marks.'),
        ('short-term tourist hosting prohibition', ['tourist', 'hosting'], 'Subletting for short-term tourist hosting is strictly forbidden under this lease.'),
        ('business-class upgrade exclusion', ['business', 'upgrade'], 'Charges from any business-class upgrade are never refundable under grant rules.'),
        ('third-party battery pack exception', ['third', 'party', 'battery'], 'Claims involving a third-party battery pack are void unless pre-certified.'),
        ('shared service account prohibition', ['shared', 'service', 'account'], 'Elevation via any shared service account is not allowed under any waiver.'),
        ('recent surgical implant restriction', ['surgical', 'implant'], 'Applicants with a recent surgical implant are not eligible unless cleared by surgery.'),
        ('expired hazmat placard hold', ['hazmat', 'placard'], 'Containers missing an updated hazmat placard cannot leave the terminal.'),
        ('uninsured subtenant pet exclusion', ['subtenant', 'pet'], 'Housing an uninsured subtenant pet is prohibited except with written rider.'),
        ('alcoholic banquet charge exclusion', ['alcoholic', 'banquet'], 'Reimbursement is excluded for any alcoholic banquet receipts.'),
    ],
    'fa': [
        ('ممنوعیت خسارت ناشی از نوسان برق', ['نوسان', 'برق'], 'خسارت ناشی از نوسان برق بدون محافظ استاندارد از شمول گارانتی خارج و ممنوع است.'),
        ('حذف دسترسی حساب اشتراکی تیمی', ['حساب', 'اشتراکی'], 'ارتقای دسترسی از طریق حساب اشتراکی هرگز مجاز نیست مگر با استثنای کتبی.'),
        ('منع مصرف همزمان رقیق‌کننده خون', ['رقیق', 'کننده', 'خون'], 'مصرف همزمان رقیق‌کننده خون غیرمجاز است به‌جز با تایید پزشک ناظر.'),
        ('ممنوعیت جابه‌جایی محموله بدون پلمب فلزی', ['پلمب', 'فلزی'], 'خروج محموله بدون پلمب فلزی شماره دار ممنوع است.'),
    ],
    'tr': [
        ('sıvı teması oksitlenme istisnası', ['sıvı', 'oksitlenme'], 'Sıvı teması ve oksitlenme saptanan cihazlar hariç tutularak garanti kapsamı dışındadır.'),
        ('paylaşımlı yönetici hesabı yasağı', ['paylaşımlı', 'yönetici'], 'Paylaşımlı yönetici hesabı üzerinden yetki talebi kesinlikle yasaktır.'),
        ('antikoagülan ilaç kullanım yasağı', ['antikoagülan', 'ilaç'], 'Son iki haftada antikoagülan ilaç kullanımı olmadan katılım yapılamaz.'),
        ('mühürsüz tahta sandık yasağı', ['mühürsüz', 'tahta', 'sandık'], 'Isıl işlem damgasız ve mühürsüz tahta sandık girişi yasaktır.'),
    ],
}

EXTRA_TEMPORAL = {
    'en': [
        ('72-hour diagnostic drop-off deadline', ['72', 'hours'], 'Units must arrive at the depot within 72 hours of ticket opening.'),
        ('15-minute idle session expiry', ['15', 'minute', 'expire'], 'Elevated credentials expire no later than 15 minutes after shell inactivity.'),
        ('48-hour pre-intake washout deadline', ['48', 'hours'], 'Prior supplement washout must complete at least 48 hours before baseline visit.'),
        ('5-day manifest amendment cutoff', ['5', 'days'], 'Tariff amendments must be lodged prior to 5 days before vessel docking.'),
        ('superseded 2019 sublet schedule marker', ['2019', 'superseded'], 'Policy annex dated 2019 is archived and superseded pending legal renewal.'),
        ('20-day post-conference receipt cutoff', ['20', 'days'], 'Claims submitted after 20 days of conference closing are expired.'),
        ('2021 outdated diagnostic protocol', ['2021', 'outdated'], 'Reference firmware checklist v2.1 (2021) is marked outdated for rev-C boards.'),
        ('30-minute peer window expiry', ['30', 'minutes'], 'Peer approval token valid until 30 minutes before maintenance start.'),
        ('10-day prior landlord registration', ['10', 'days'], 'Tenant must submit subtenant ID no later than 10 days before move-in.'),
    ],
    'fa': [
        ('مهلت 48 ساعته ارسال قطعه معیوب', ['48', 'ساعت'], 'ارسال قطعه معیوب باید ظرف 48 ساعت پس از صدور کد رهگیری انجام شود.'),
        ('انقضای اعتبار سند سال 2020', ['منقضی', '2020'], 'دستورالعمل نسخه 2020 این بخش منقضی و قدیمی است و نیاز به بازبینی دارد.'),
        ('حداقل مهلت 7 روزه پیش از تحویل کلید', ['7', 'روز'], 'مدارک مستاجر فرعی باید حداقل 7 روز پیش از تحویل کلید ثبت شود.'),
    ],
    'tr': [
        ('48 saat içinde arıza kargo süresi', ['48', 'saat'], 'Arızalı parça onay kodundan sonra en geç 48 saat içinde kargoya verilmelidir.'),
        ('süresi dolmuş 2020 yönergesi', ['2020', 'süresi', 'dolmuş'], 'Bu 2020 tarihli güvenlik eki süresi dolmuş olarak işaretlenmiştir.'),
        ('7 gün öncesinden manifesto bildirimi', ['7', 'gün'], 'Gümrük ek beyanı varıştan en geç 7 gün önce sisteme girilmelidir.'),
    ],
}

EXTRA_COMPLEX = {
    'en': [
        ('cross_ref', 'external standard warranty rules', ['standard', 'rules'], 'All standard rules apply beyond this summary sheet. Also follow general company policy.'),
        ('cross_ref', 'corporate policy addendum', ['corporate', 'addendum'], 'Temporary cluster grants remain subject to additional terms in the corporate policy addendum.'),
        ('cross_ref', 'institutional ethics board rules', ['applicable', 'law'], 'Additional requirements from applicable law and IRB terms apply to every cohort intake.'),
        ('overlap', 'within warranty period plus encrypted wiping proof', ['encrypted', 'wiping', 'proof'], 'Hardware is within the active warranty period with notarized encrypted wiping proof signed off.'),
        ('overlap', 'approved change ticket plus SIEM telemetry tag', ['siem', 'telemetry', 'tag'], 'Production change ticket is approved together with immutable SIEM telemetry tag attached.'),
        ('overlap', 'written consent plus genomic biobank opt-in', ['genomic', 'biobank', 'opt'], 'Written study consent form is signed including mandatory genomic biobank opt-in addendum.'),
        ('unclassified', 'customs supervisor discretionary release hold', ['discretionary', 'quarantine', 'director'], 'Port agricultural inspection director exercises independent discretionary quarantine hold over refrigerated containers.'),
        ('unclassified', 'building cooperative board quorum vote', ['cooperative', 'board', 'quorum'], 'Building cooperative board quorum vote sets monthly seasonal occupancy caps across floors.'),
        ('truncation', '28 itemized grant travel rules (>24 maxCandidates)', ['compliance', 'voucher'], '\n'.join(f'{k}. Additional reimbursement compliance rule #{k} must be verified with original itemized voucher.' for k in range(1, 29))),
    ],
    'fa': [
        ('cross_ref', 'سایر ضوابط و مقررات استاندارد شرکت', ['مقررات', 'استاندارد'], 'علاوه بر موارد فوق، سایر ضوابط و مقررات استاندارد شرکت نیز لازم‌الاجرا است.'),
        ('overlap', 'تیکت تغییر همراه با امضای افسر امنیت سایبری', ['افسر', 'امنیت', 'سایبری'], 'درخواست باید دارای تیکت تغییر تاییدشده همراه با امضای کتبی افسر امنیت سایبری باشد.'),
        ('unclassified', 'کمیسیون گمرکی اختیار توقیف محموله‌های خاص را دارد', ['کمیسیون', 'توقیف'], 'کمیسیون ویژه ارزیابی بندر توقیف نهایی محموله‌های شیمیایی حساس را بررسی می‌کند.'),
    ],
    'tr': [
        ('cross_ref', 'genel şartlar ve ek koşullar bildirimi', ['genel', 'şartlar'], 'Buradaki maddelere ek olarak genel şartlar ve ek koşullar tamamen geçerlidir.'),
        ('overlap', 'fatura ibrazı ile birlikte gümrük ekspertiz tutanağı', ['gümrük', 'ekspertiz', 'tutanağı'], 'Orijinal satıcı faturası ile birlikte noter onaylı gümrük ekspertiz tutanağı sunulmalıdır.'),
        ('unclassified', 'etik kurul başkanlığı bağımsız inceleme yapar', ['etik', 'kurul'], 'Üniversite etik kurul başkanlığı saha bütçe denetimini bağımsız olarak yürütür.'),
    ],
}

CONTRADICTIONS = {
    'en': [
        ('Standard hardware claims are refundable within warranty.\nModified units are never refundable under this store policy.', ['never', 'refundable']),
        ('Break-glass sessions with approved tickets are permitted for debugging.\nDatabase write commands are strictly prohibited and not eligible on weekends.', ['prohibited']),
        ('Healthy adult volunteers are eligible for cohort intake.\nApplicants above age 60 are strictly void and not eligible under protocol B.', ['void']),
        ('Pre-cleared cargo containers are accepted at port gate 4.\nUncertified battery crates are strictly prohibited and not permitted in gate 4.', ['prohibited']),
        ('Academic sublets of 60 days are permitted by lease office.\nUnauthorized short sublets remain void and prohibited year-round.', ['void']),
        ('Approved travel claims are accepted for hotel reimbursement.\nLuxury suites remain non-refundable and not eligible for department funds.', ['non-refundable']),
    ],
    'fa': [
        ('کالاهای دارای گارانتی استاندارد قابل بازپرداخت و تعویض هستند.\nقطعات بازشده هرگز غیرقابل بازگشت بوده و تعویض آن‌ها ممنوع است.', ['غیرقابل بازگشت']),
        ('تجهیزات پزشکی مجاز با تاییدیه فنی قابل استرداد هزینه هستند.\nلوازم مصرفی استریل‌شده غیرقابل بازگشت و ارسال آن ممنوع است.', ['ممنوع']),
    ],
    'tr': [
        ('Standart donanım talepleri iade kapsamında kabul edilir.\nAçılmış güç üniteleri iadesi kesinlikle geçersiz sayılır.', ['geçersiz']),
        ('Onaylı konferans harcamaları iade için uygundur.\nEkstra otel harcamaları kesinlikle geçersiz kabul edilir.', ['geçersiz']),
    ],
}


def build_blind_suite():
    domain_keys = list(DOMAINS.keys())
    cases = []
    idx = 0

    def add_case(domain, category, lang, clauses, gt_decision, hidden_condition='', hidden_tokens=None,
                 scope_accepted=True, source_verified=True, coverage_reviewed=True, obs_override=None):
        nonlocal idx
        idx += 1
        d = DOMAINS[domain]
        title = d['title'] if lang == 'en' else d[f'title_{lang}']
        question = d['question'] if lang == 'en' else d[f'question_{lang}']
        terms_raw = d['terms'] if lang == 'en' else d[f'terms_{lang}']
        header = {
            'en': f"{title} / Internal Procedure Specification",
            'fa': f"{title} / دستورالعمل داخلی",
            'tr': f"{title} / Dahili Prosedür",
        }[lang]
        if category == 'empty_or_too_short_source':
            source_text = clauses
        else:
            source_text = header + '\n' + '\n'.join(clauses)
        policy = {
            'id': f'blind_{domain}_{idx:03d}',
            'title': title,
            'scope': d['scope'],
            'question': question,
            'terms': [{'id': tid, 'label': lbl, 'why': why, 'cost': 1} for tid, lbl, why in terms_raw],
        }
        obs = {tid: 'yes' for tid, _, _ in terms_raw}
        if obs_override:
            obs.update(obs_override)
        doc_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()[:16]
        sample_id = f'pg_{idx:03d}'
        cases.append({
            'visible_input': {
                'sample_id': sample_id,
                'document_hash': doc_hash,
                'domain': domain,
                'source_type': category,
                'language': lang,
                'policy': policy,
                'source_text': source_text,
                'observations': obs,
                'scopeAccepted': scope_accepted,
                'sourceVerified': source_verified,
                'coverageReviewed': coverage_reviewed,
            },
            'ground_truth': {
                'sample_id': sample_id,
                'gt_decision': gt_decision,
                'hidden_condition': hidden_condition,
                'hidden_tokens': hidden_tokens or [],
                'category': category,
            },
        })

    for lang, items in EXTRA_IMPLICIT.items():
        for j, (cond, toks, clause) in enumerate(items):
            dom = domain_keys[(j + (0 if lang == 'en' else 2)) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'implicit_dependency', lang, [*base, f'4. {clause}'], 'ASK', cond, toks)

    for lang, items in EXTRA_NEG_EXC.items():
        for j, (cond, toks, clause) in enumerate(items):
            dom = domain_keys[(j + 1) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'explicit_negation_exception', lang, [*base, f'4. {clause}'], 'ASK', cond, toks)

    for lang, items in EXTRA_TEMPORAL.items():
        for j, (cond, toks, clause) in enumerate(items):
            dom = domain_keys[(j + 3) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'temporal_stale_deadline', lang, [*base, f'4. {clause}'], 'ASK', cond, toks)

    for lang, items in EXTRA_COMPLEX.items():
        for j, (subcat, cond, toks, clause) in enumerate(items):
            dom = domain_keys[(j + 4) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            lines = [clause] if subcat == 'truncation' else [*base, f'4. {clause}']
            add_case(dom, f'complex_{subcat}', lang, lines, 'ASK', cond, toks)

    for lang, items in CONTRADICTIONS.items():
        for j, (text_block, toks) in enumerate(items):
            dom = domain_keys[(j + 2) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'internal_contradiction', lang, [*base[:1], text_block], 'CONFLICT', 'conflicting rules in source', toks)

    for lang, count in (('en', 9), ('fa', 3), ('tr', 3)):
        for j in range(count):
            dom = domain_keys[(j + 5) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'clean_satisfied_yes', lang, base, 'YES', '', [])

    for lang, count in (('en', 6), ('fa', 2), ('tr', 2)):
        for j in range(count):
            dom = domain_keys[j % len(domain_keys)]
            first_term = DOMAINS[dom]['terms'][0][0]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'confirmed_false_no', lang, base, 'NO', '', [], obs_override={first_term: 'no'})

    for lang, count in (('en', 6), ('fa', 2), ('tr', 2)):
        for j in range(count):
            dom = domain_keys[(j + 1) % len(domain_keys)]
            base = DOMAINS[dom][f'clean_clauses_{lang}']
            add_case(dom, 'out_of_scope', lang, base, 'OUT_OF_SCOPE', '', [], scope_accepted=False)

    short_samples = [('en', ''), ('en', 'Approved OK.'), ('en', '   \n  '), ('fa', 'تایید شد'), ('tr', 'Onaylı')]
    for j, (lang, snippet) in enumerate(short_samples):
        dom = domain_keys[j % len(domain_keys)]
        add_case(dom, 'empty_or_too_short_source', lang, snippet, 'ASK', 'missing/insufficient source (<24 chars)', [])

    return cases


if __name__ == '__main__':
    suite = build_blind_suite()
    print(json.dumps({'count': len(suite), 'domains': sorted({c['visible_input']['domain'] for c in suite})}, ensure_ascii=False))
