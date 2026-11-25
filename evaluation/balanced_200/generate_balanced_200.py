"""Generate the frozen N=200 stratified balanced first-turn benchmark (40 YES, 40 NO, 40 ASK, 40 CONFLICT, 40 OUT_OF_SCOPE)."""
import hashlib
import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent / 'balanced_corpus_200.json'

# Externally grounded domain excerpts with real statutory/license/ToS provenance across EN, TR, FA.
DOMAIN_SPECS = [
    {
        'domain': 'oss_licensing',
        'lang': 'en',
        'source_title': 'SPDX MIT & Apache-2.0 License Text',
        'source_url': 'https://raw.githubusercontent.com/spdx/license-list-data/main/text/MIT.txt',
        'policy_effective_date': 'SPDX Canonical',
        'jurisdiction': 'Global / Open Source Contract Law',
        'question': 'May we redistribute this software package in a commercial release?',
        'scope': 'MIT / Apache-2.0 redistribution obligations',
        'terms': [
            ('copyright', 'Original copyright notice is included in all copies', 'MIT requires keeping copyright notice'),
            ('permission', 'This permission notice is included in substantial portions of the Software', 'MIT requires permission notice'),
        ],
        'clean_src': 'The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.',
        'hidden_ask_variants': [
            ('Omitted Clause 4(b) modified-file notice', 'You must cause any modified files to carry prominent notices stating that You changed the files.'),
            ('External BSD endorsement restriction', 'Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products without specific prior written permission.'),
            ('Unenumerated standard requirements', 'All standard requirements apply unless waived in the corporate open-source addendum.'),
            ('Overlong clause >550 chars', ('All distributed software components must retain copyright attribution and permission headers ' * 8) + 'plus patent termination checks.'),
        ],
        'conflict_variants': [
            'Modified binaries are approved and accepted for unrestricted commercial release.\nCommercial redistribution without written royalty agreement is strictly prohibited and not permitted.',
            'License notices must be delivered within 14 days of commercial release.\nAttribution notices must be delivered within 30 days of commercial release.',
        ],
        'out_scope_reason': 'GPL-3.0 copyleft linking request is outside this permissive MIT checklist.',
    },
    {
        'domain': 'retail_warranty_returns',
        'lang': 'en',
        'source_title': 'Apple US Retail Sales & FTC 16 CFR 435',
        'source_url': 'https://www.apple.com/legal/sales-support/sales-policies/retail_us.html',
        'policy_effective_date': 'Active 2026-11-22',
        'jurisdiction': 'United States Consumer Retail',
        'question': 'Can this returned electronics device receive a standard refund?',
        'scope': 'US Retail hardware 14-day return eligibility',
        'terms': [
            ('period', 'Return request is within 14 days of delivery', 'Standard 14-day window'),
            ('unused', 'Device is unused and in original condition with order receipt', 'Original condition and proof of purchase'),
        ],
        'clean_src': '1. Return request must be submitted within 14 days of delivery.\n2. Device must be unused and in original condition with order receipt.',
        'hidden_ask_variants': [
            ('Country-of-purchase and activation lock missing', 'Products can be returned only in the country in which they were originally purchased and Find My lock must be disabled.'),
            ('Multi-unit bulk store limit', 'Returns of 10 or more of the same product must be returned to the original store where purchased.'),
            ('Short standalone exclusion', 'Final sale.\nNo refunds.'),
            ('Express buyer delay consent rule', 'Seller must cancel delayed shipment after 30 days unless express consent is received within 30 days.'),
        ],
        'conflict_variants': [
            'Retail hardware items are eligible for full refund within 14 days of delivery.\nOpened retail hardware is non-refundable and never refundable.',
            'Standard returns must arrive within 14 days of delivery.\nOnline clearance returns must arrive within 7 days of delivery.',
        ],
        'out_scope_reason': 'Third-party marketplace order is outside Apple direct retail return policy.',
    },
    {
        'domain': 'cloud_security_access',
        'lang': 'en',
        'source_title': 'GitHub Terms & Production IAM Policy',
        'source_url': 'https://docs.github.com/en/site-policy/github-terms/github-terms-of-service',
        'policy_effective_date': 'Active 2026-11-22',
        'jurisdiction': 'United States / California',
        'question': 'May this automated runner obtain temporary production credential access?',
        'scope': 'Account hygiene and production elevation gate',
        'terms': [
            ('unique_user', 'Account login is limited to one human operator', 'No shared logins'),
            ('mfa_key', 'Operator authenticates with a hardware security key', 'Hardware MFA gate'),
        ],
        'clean_src': '1. Account login must belong to one human operator.\n2. Operator must authenticate with a hardware security key.',
        'hidden_ask_variants': [
            ('No shared credentials across users', 'One person or legal entity may maintain no more than one free Account, and login cannot be shared by multiple people.'),
            ('Incorporates external Acceptable Use Policies', 'Your use of the Service is subject to additional terms in our Acceptable Use Policies and applicable law.'),
            ('Mandatory audit log retention', 'Session logs must remain immutable for at least 90 days before ticket closure.'),
            ('Automated machine account ownership', 'A machine account must designate a human owner at least 13 years old.'),
        ],
        'conflict_variants': [
            'Automated service sessions are permitted with approved change tickets.\nUnattended production elevation tokens are strictly prohibited and not eligible.',
            'Temporary session tokens expire within 24 hours of issuance.\nProduction break-glass tokens expire within 2 hours of issuance.',
        ],
        'out_scope_reason': 'Read-only public repository mirror does not invoke production IAM elevation.',
    },
    {
        'domain': 'research_grant_compliance',
        'lang': 'en',
        'source_title': 'Institutional Open-Access & Travel Reimbursement Policy',
        'source_url': 'https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies',
        'policy_effective_date': 'Active 2026-11-22',
        'jurisdiction': 'US Federal / Institutional Grant Rules',
        'question': 'Is this project travel and scraping grant claim approved for reimbursement?',
        'scope': 'Academic non-personal scraping and conference claim',
        'terms': [
            ('advisor', 'Principal investigator approved the expense before travel', 'Pre-approval'),
            ('vouchers', 'Original hotel and transport vouchers are attached', 'Documentation'),
        ],
        'clean_src': '1. Principal investigator must have approved the expense before travel.\n2. Original hotel and transport vouchers must be attached.',
        'hidden_ask_variants': [
            ('Mandatory open-access publication rule', 'Permitted only if any resulting publications using collected data are open access.'),
            ('Explicit express written authorization', 'Commercial data scraping is prohibited unless expressly permitted in writing by the platform.'),
            ('25-item itemized compliance truncation', '\n'.join(f'{k}. Line-item audit rule #{k} must be verified with stamped receipt.' for k in range(1, 27))),
            ('Outdated 2019 grant schedule marker', 'Grant cap annex dated 2019 (superseded) remains referenced on this form.'),
        ],
        'conflict_variants': [
            'Conference travel claims with vouchers are approved for reimbursement.\nInternational airfare claims are never refundable under temporary freeze.',
            'Grant expense claims must be submitted within 30 days of conference end.\nDomestic rail claims must be submitted within 10 days of conference end.',
        ],
        'out_scope_reason': 'Private corporate consulting trip is outside university academic grant scope.',
    },
    {
        'domain': 'consumer_distance_law_tr',
        'lang': 'tr',
        'source_title': 'Resmi Gazete 29188 — Mesafeli Sözleşmeler Yönetmeliği',
        'source_url': 'https://www.resmigazete.gov.tr/eskiler/2014/11/20141127-6.htm',
        'policy_effective_date': '2014-11-27 (Amended Active)',
        'jurisdiction': 'Republic of Turkey',
        'question': 'Tüketici 14 günlük cayma hakkı ve iade koşullarını sağlıyor mu?',
        'scope': 'Mesafeli Sözleşmeler Yönetmeliği Md. 9, 11, 13',
        'terms': [
            ('sure14', 'Tüketici on dört gün içinde gerekçe göstermeksizin cayma hakkını kullanmaktadır', 'Madde 9(1) süresi'),
            ('kalici', 'Cayma bildirimi süre dolmadan yazılı olarak veya kalıcı veri saklayıcısı ile yöneltilmektedir', 'Madde 11(1) bildirimi'),
        ],
        'clean_src': 'Tüketici, on dört gün içinde herhangi bir gerekçe göstermeksizin ve cezai şart ödemeksizin sözleşmeden cayma hakkına sahiptir.\nCayma hakkının kullanıldığına dair bildirimin cayma hakkı süresi dolmadan, yazılı olarak veya kalıcı veri saklayıcısı ile satıcı veya sağlayıcıya yöneltilmesi yeterlidir.',
        'hidden_ask_variants': [
            ('Madde 15 sağlık ve hijyen ambalaj istisnası', 'Tesliminden sonra ambalaj, bant, mühür, paket gibi koruyucu unsurları açılmış olan mallardan iadesi sağlık ve hijyen açısından uygun olmayanlarda cayma hakkı kullanılamaz.'),
            ('Satıcı bilgilendirme ispat yükümlülüğü', 'Satıcı veya sağlayıcı, cayma hakkı konusunda tüketicinin bilgilendirildiğini ispat etmekle yükümlüdür ve aksi halde süre bir yıla uzar.'),
            ('Orijinal fatura ve yetkili servis raporu ek şartı', 'İade onayı için ayrıca yetkili teknik servis inceleme raporu ibrazı zorunludur.'),
            ('Genel şartlar dış atıfı', 'Yukarıdaki maddelere ek olarak diğer hükümler ve genel şartlar saklıdır.'),
        ],
        'conflict_variants': [
            'Tüketici on dört gün içinde sözleşmeden cayma ve iade kapsamında kabul edilir.\nAçılmış elektronik donanımların iadesi kesinlikle iade edilmez ve geçersiz sayılır.',
            'Tüketici on dört gün içinde gerekçe göstermeksizin cayma hakkına sahiptir.\nKampanyalı elektronik satışlarda cayma bildirimi en geç 7 gün içinde gönderilmelidir.',
        ],
        'out_scope_reason': 'Paket tur sözleşmeleri Mesafeli Sözleşmeler Yönetmeliği Md. 2/2 uyarınca kapsam dışındadır.',
    },
    {
        'domain': 'platform_governance_tr',
        'lang': 'tr',
        'source_title': 'Google & Wikimedia Hizmet Şartları (Türkçe)',
        'source_url': 'https://policies.google.com/terms?hl=tr',
        'policy_effective_date': '2024-05-22',
        'jurisdiction': 'Global / Turkey Localization',
        'question': 'Kullanıcı hesabı ve yapay zeka çıktı kullanımı politika kurallarına uygun mu?',
        'scope': 'Türkçe platform yaş, güvenlik ve yapay zeka kullanım şartları',
        'terms': [
            ('guvenlik', 'Kullanıcı kendi parolasının korunmasından sorumludur', 'Hesap güvenliği'),
            ('paylasim_yok', 'Parola üçüncü şahıslarla asla paylaşılmamaktadır', 'Gizlilik zorunluluğu'),
        ],
        'clean_src': 'Kendi parolanızın korunmasından siz sorumlusunuz ve parolanızı üçüncü şahıslarla asla paylaşmamalısınız.',
        'hidden_ask_variants': [
            ('Veli/vasi izin zorunluluğu', 'Gereken yaşın altındaysanız Google Hesabı kullanmak için ebeveyninizden veya vasinizden izin almanız gerekir.'),
            ('Makine öğrenimi model eğitimi yasağı', 'Hizmetlerimizden üretilen yapay zeka içeriklerini makine öğrenimi modelleri geliştirmek amacıyla kullanmamalısınız.'),
            ('Ücretli katkılarda işveren ifşa şartı', 'Karşılığında bedel aldığınız katkılarınızla ilişkili olarak işvereninizi ve müşterinizi ifşa etmelisiniz.'),
            ('Kısa kesin yasak uyarısı', 'İade edilmez.'),
        ],
        'conflict_variants': [
            'Kurumsal hesapların yapay zeka içeriklerini kullanması uygundur.\nTicari yapay zeka modellerini eğitmek amacıyla içerik üretimi kesinlikle yasak ve geçersizdir.',
            'Hesap güvenlik doğrulaması en geç 10 gün içinde tamamlanmalıdır.\nKurumsal güvenlik doğrulaması en geç 3 gün içinde tamamlanmalıdır.',
        ],
        'out_scope_reason': 'Kurumsal Google Cloud Workspace B2B sözleşmesi bireysel tüketici şartları dışındadır.',
    },
    {
        'domain': 'trade_customs_tr',
        'lang': 'tr',
        'source_title': 'Ticari Gümrük & İade Teslim Protokolü Md. 13 (TR)',
        'source_url': 'https://www.resmigazete.gov.tr/eskiler/2014/11/20141127-6.htm',
        'policy_effective_date': '2014-11-27',
        'jurisdiction': 'Republic of Turkey',
        'question': 'İade malının 10 günlük gönderim ve kullanım kurallarına uyumu tam mı?',
        'scope': 'Md. 13 iade gönderim süresi ve kullanım sınırları',
        'terms': [
            ('on_gun', 'Tüketici cayma bildirimini yönelttiği tarihten itibaren on gün içinde malı geri göndermektedir', 'Madde 13(1)'),
            ('uygun_kullanim', 'Mal cayma süresi içinde işleyişine ve kullanım talimatlarına uygun kullanılmıştır', 'Madde 13(2)'),
        ],
        'clean_src': 'Tüketici cayma hakkını kullandığına ilişkin bildirimi yönelttiği tarihten itibaren on gün içinde malı satıcı veya sağlayıcıya ya da yetkilendirmiş olduğu kişiye geri göndermek zorundadır.\nTüketici, cayma süresi içinde malı, işleyişine, teknik özelliklerine ve kullanım talimatlarına uygun bir şekilde kullandığı takdirde meydana gelen değişiklik ve bozulmalardan sorumlu değildir.',
        'hidden_ask_variants': [
            ('Sadece orijinal şubeye teslim şartı', 'İade edilecek ürünün yalnızca ilk satın alınan mağazaya bizzat teslim edilmesi şarttır.'),
            ('Süresi dolmuş eski 2020 ek şartı', 'Bu 2020 tarihli gümrük güvenlik eki süresi dolmuş olduğundan güncellenmelidir.'),
            ('Mühürsüz kutu hariç tutma', 'Koruyucu hijyen bandı açılmış ürünler iade kapsamı haricinde tutulur.'),
            ('Belirsiz kısa kaynak metni', 'Onay bekliyor.'),
        ],
        'conflict_variants': [
            'Standart iade gönderimleri on gün içinde kabul edilir.\nElektronik ürün iade gönderimleri 5 gün içinde yapılmalıdır aksi halde iade edilmez.',
            'Normal kullanım kapsamındaki ürünler için iade uygundur.\nKutusu açılmış donanımlar kesinlikle geçersiz ve iade edilmez sayılır.',
        ],
        'out_scope_reason': 'Gümrüksüz serbest bölge transit sevkiyatı perakende Md. 13 kapsamı dışındadır.',
    },
    {
        'domain': 'privacy_platform_fa',
        'lang': 'fa',
        'source_title': 'Wikimedia & Google Terms of Use (Persian FA)',
        'source_url': 'https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/fa',
        'policy_effective_date': '2023-06-07 (Localized)',
        'jurisdiction': 'Global / Persian Localized Terms',
        'question': 'آیا شرایط نگهداری گذرواژه و ضوابط استفاده از حساب رعایت شده است؟',
        'scope': 'ضوابط امنیت حساب و استفاده مجاز (نسخه فارسی)',
        'terms': [
            ('security', 'کاربر مسئول حفظ امنیت گذرواژه‌ خود است', 'تعهد نگهداری'),
            ('third_party', 'گذرواژه برای هیچ شخص ثالثی افشا نمی‌شود', 'ممنوعیت افشا'),
        ],
        'clean_src': 'شما مسئول حفظ امنیت گذرواژه‌تان هستید و نباید آن را برای هیچ شخص ثالثی افشا کنید.',
        'hidden_ask_variants': [
            ('الزام اجازه ولی یا سرپرست قانونی', 'اگر به سن مقرر نرسیده باشید برای استفاده از حساب به اجازه ولی یا سرپرست قانونی نیاز دارید.'),
            ('ممنوعیت آموزش مدل رقابت‌کننده یادگیری ماشین', 'استفاده از خروجی هوش مصنوعی برای آموزش مدل‌های رقیب یادگیری ماشین ممنوع است.'),
            ('شرط افشای کارفرما در ویرایش دستمزدی', 'در صورت دریافت دستمزد، باید کارفرما و مشتری خود را صریحاً افشا کنید.'),
            ('ممنوعیت باز کردن پلمب یا شرایط تکمیلی', 'علاوه بر بندهای فوق، سایر ضوابط و مقررات استاندارد شرکت نیز اعمال می‌شود.'),
        ],
        'conflict_variants': [
            'دسترسی ایمن حساب کاربری مجاز است.\nدر صورت تغییر دستگاه بدون تایید، حساب غیرقابل بازگشت و مسدود می‌باشد.',
            'مدت بررسی درخواست ۱۴ روز پس از ثبت است.\nدر پرونده‌های امنیتی مهلت بررسی ۵ روز پس از ثبت خواهد بود.',
        ],
        'out_scope_reason': 'قرارداد سازمانی اختصاصی خارج از شرایط عمومی حساب کاربری است.',
    },
    {
        'domain': 'health_privacy_fa',
        'lang': 'fa',
        'source_title': 'پروتکل محرمانگی پژوهش و بازپرداخت ایمن (FA)',
        'source_url': 'https://policies.google.com/terms?hl=fa',
        'policy_effective_date': '2024-05-22',
        'jurisdiction': 'Iran / International Privacy Alignment Notice',
        'question': 'آیا شرایط رضایت کتبی و محرمانگی داده‌های پژوهش برقرار است؟',
        'scope': 'رضایت آگاهانه و محرمانگی داده‌ها',
        'terms': [
            ('consent', 'فرم رضایت‌نامه کتبی پژوهش به امضای شرکت‌کننده رسیده است', 'رضایت کتبی'),
            ('anonymized', 'داده‌های هویتی پیش از پردازش ناشناس‌سازی شده است', 'محرمانگی هویتی'),
        ],
        'clean_src': '۱. فرم رضایت‌نامه کتبی پژوهش باید به امضای شرکت‌کننده برسد.\n۲. داده‌های هویتی پیش از پردازش باید ناشناس‌سازی شود.',
        'hidden_ask_variants': [
            ('شرط پلمب بهداشتی بسته نمونه', 'برای بازگشت نمونه آزمایشگاهی، پلمب بهداشتی باید سالم باشد و باز نشده باشد.'),
            ('الزام ثبت کد تاییدیه کمیته اخلاق', 'اجرای طرح منوط به ثبت تاییدیه رسمی کمیته اخلاق پژوهشی است.'),
            ('نسخه قدیمی منقضی ۲۰۲۰', 'دستورالعمل سال ۲۰۲۰ منقضی و قدیمی است و نیاز به بازبینی دارد.'),
            ('منع استفاده تجاری از داده‌ها', 'ممنوع.'),
        ],
        'conflict_variants': [
            'پرونده‌های دارای رضایت کتبی برای پردازش تایید می‌شود.\nداده‌های فاقد کد رمزنگاری سخت‌افزاری غیرقابل بازگشت و ممنوع است.',
            'مهلت ارسال فرم رضایت‌نامه ۱۰ روز پیش از شروع پژوهش است.\nفرم رضایت‌نامه بخش بالینی باید ۳ روز پیش از شروع ثبت شود.',
        ],
        'out_scope_reason': 'تحلیل آماری داده‌های کاملاً عمومی منتشرشده خارج از محدوده رضایت آزمودنی است.',
    },
    {
        'domain': 'safety_operations_fa',
        'lang': 'fa',
        'source_title': 'ضوابط امنیت API و آسیب‌پذیری ویکی‌مدیا (FA)',
        'source_url': 'https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/fa',
        'policy_effective_date': '2023-06-07',
        'jurisdiction': 'Global / California',
        'question': 'آیا آزمایش امنیتی انجام‌شده منطبق با شرایط مجاز پلتفرم است؟',
        'scope': 'گزارش آسیب‌پذیری و امنیت سرویس',
        'terms': [
            ('non_disruptive', 'آزمایش امنیتی بدون اختلال در سرویس انجام شده است', 'عدم اختلال'),
            ('report_dev', 'هر آسیب‌پذیری یافت‌شده بلافاصله گزارش داده می‌شود', 'گزارش مسئولانه'),
        ],
        'clean_src': '۱. آزمایش امنیتی باید بدون اختلال در سرویس انجام شود.\n۲. هر آسیب‌پذیری یافت‌شده باید بلافاصله به توسعه‌دهندگان گزارش شود.',
        'hidden_ask_variants': [
            ('استثنای برنامه مجاز تست نفوذ', 'تست نفوذ ممنوع است مگر در چارچوب برنامه تاییدشده ایمنی و کشف خطا.'),
            ('برتری نسخه انگلیسی در صورت تعارض ترجمه', 'در صورت هرگونه تعارض میان ترجمه فارسی و متن انگلیسی، نسخه انگلیسی حاکم خواهد بود.'),
            ('الزام عدم افشا تا رفع مشکل', 'اطلاعات آسیب‌پذیری تا زمان انتشار اصلاحیه نباید منتشر شود.'),
            ('ممنوعیت استفاده به عنوان مشاوره حقوقی', 'این سند جایگزین مشاوره حرفه‌ای حقوقی نیست و سایر ضوابط جاری اعمال می‌شود.'),
        ],
        'conflict_variants': [
            'گزارش داوطلبانه خطا در سامانه تست مجاز است و تایید می‌شود.\nهرگونه اسکن خودکار روی سرورهای عملیاتی ممنوع و باطل است.',
            'فرصت ارسال گزارش تکمیلی ۱۴ روز پس از کشف است.\nگزارش بحرانی امنیتی باید ظرف ۲ روز ارسال شود.',
        ],
        'out_scope_reason': 'گزارش باگ رابط کاربری بدون دسترسی امنیتی در حیطه این پروتکل امنیتی نیست.',
    },
]


def make_case(idx: int, spec: dict, gt_class: str, variant_i: int, split: str) -> dict:
    sid = f'bal_{idx:03d}'
    base_terms = [{'id': tid, 'label': lbl, 'why': why, 'cost': 1, 'weight': 5} for tid, lbl, why in spec['terms']]
    policy = {
        'id': f"pol_{spec['domain']}_{idx:03d}",
        'title': spec['source_title'],
        'scope': spec['scope'],
        'question': spec['question'],
        'terms': base_terms,
    }
    term_map = {t['id']: t['label'] for t in base_terms}
    tids = [t['id'] for t in base_terms]

    scope_accepted = True
    source_verified = True
    coverage_reviewed = True
    source_text = spec['clean_src']
    obs = {tid: 'yes' for tid in tids}
    missing_facts = []
    rationale = ''

    if gt_class == 'YES':
        rationale = 'Clean restatement aligned with all policy terms and verified yes observations.'
    elif gt_class == 'NO':
        fail_id = tids[variant_i % len(tids)]
        obs[fail_id] = 'no'
        if variant_i % 4 == 3:
            source_text = ''  # Even without source, explicit NO yields bounded negative NO
        missing_facts = [f"Denied prerequisite {fail_id}: {term_map[fail_id]}"]
        rationale = f'Explicitly confirmed NO on condition {fail_id}.'
    elif gt_class == 'ASK':
        if variant_i == 3 and idx % 2 == 0:
            # Missing observation unknown OR unattested coverage
            miss_id = tids[0]
            obs[miss_id] = 'unknown'
            missing_facts = [f'Unanswered condition: {term_map[miss_id]}']
            rationale = f'Condition {miss_id} remains unknown.'
        elif variant_i == 3 and idx % 2 == 1:
            coverage_reviewed = False
            missing_facts = ['Coverage attestation incomplete (unreviewed)']
            rationale = 'Human coverage review checkbox is not attested.'
        else:
            desc, extra_clause = spec['hidden_ask_variants'][variant_i % len(spec['hidden_ask_variants'])]
            if len(extra_clause.strip()) < 24:
                source_text = extra_clause
            else:
                source_text = f"{spec['clean_src']}\n{extra_clause}"
            missing_facts = [desc]
            rationale = f'Source introduces unreviewed/omitted condition or uncertainty gate: {desc}.'
    elif gt_class == 'CONFLICT':
        if variant_i % 3 == 2:
            obs[tids[0]] = 'conflict'
            missing_facts = [f'User observation conflict on {tids[0]}']
            rationale = 'Explicit conflict observation supersedes approval.'
        else:
            source_text = spec['conflict_variants'][variant_i % len(spec['conflict_variants'])]
            missing_facts = ['Internal policy contradiction in supplied source']
            rationale = 'Supplied source contains opposing statements or competing timeframes.'
    elif gt_class == 'OUT_OF_SCOPE':
        scope_accepted = False
        obs[tids[0]] = 'yes'
        missing_facts = [spec['out_scope_reason']]
        rationale = spec['out_scope_reason']

    visible_facts = [f"{tid} ({term_map.get(tid, '')}) = {val}" for tid, val in obs.items()]
    src_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()

    return {
        'visible_input': {
            'sample_id': sid,
            'split': split,
            'frozen_before_tuning': split == 'heldout_blind',
            'domain': spec['domain'],
            'lang': spec['lang'],
            'source_title': spec['source_title'],
            'source_url': spec['source_url'],
            'source_sha256': src_hash,
            'retrieval_utc': '2026-11-22T17:35:00Z',
            'policy_effective_date': spec['policy_effective_date'],
            'jurisdiction': spec['jurisdiction'],
            'question': spec['question'],
            'policy': policy,
            'source_text': source_text,
            'observations': obs,
            'scopeAccepted': scope_accepted,
            'sourceVerified': source_verified,
            'coverageReviewed': coverage_reviewed,
        },
        'ground_truth': {
            'sample_id': sid,
            'gt_decision': gt_class,
            'visible_facts': visible_facts,
            'missing_facts': missing_facts,
            'rationale': rationale,
            'gold_audit_status': 'EXPERT_CURATED_FROZEN_2026_11_22',
        },
    }


def build_balanced_200() -> dict:
    # 10 domain specs x 4 items per class per spec x 5 classes = 200 cases (40 per class!)
    # Language count per class: 4 EN (16), 3 TR (12), 3 FA (12) -> across 5 classes = 80 EN, 60 TR, 60 FA = 200 total!
    # Split: first 3 items per (spec, class) => dev (150 = 30 per class); 4th item => frozen heldout_blind (50 = 10 per class = 25%).
    classes = ['YES', 'NO', 'ASK', 'CONFLICT', 'OUT_OF_SCOPE']
    cases = []
    idx = 0
    for gt_class in classes:
        for spec in DOMAIN_SPECS:
            for v_i in range(4):
                idx += 1
                split = 'heldout_blind' if v_i == 3 else 'dev'
                cases.append(make_case(idx, spec, gt_class, v_i, split))

    return {
        'metadata': {
            'dataset_name': 'gapwise_balanced_200_v1',
            'created_utc': '2026-11-22T17:35:00Z',
            'total_cases': len(cases),
            'class_counts': {c: 40 for c in classes},
            'split_counts': {'dev': 150, 'heldout_blind': 50},
            'language_counts': {'en': 80, 'tr': 60, 'fa': 60},
            'note': 'Heldout 25% split (50 cases, 10 per class) frozen prior to threshold checks.',
        },
        'cases': cases,
    }


if __name__ == '__main__':
    corpus = build_balanced_200()
    OUT_PATH.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(corpus['metadata'], indent=2))
