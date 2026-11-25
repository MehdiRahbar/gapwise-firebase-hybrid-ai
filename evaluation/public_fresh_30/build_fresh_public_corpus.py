"""
Build and freeze the N=30 fresh unseen public-source benchmark corpus strictly from
locally captured raw HTML/text snapshots in scratch/public_fresh_raw/.
All excerpts are verified as exact verbatim substrings of the captured source text.
Single-author rubric frozen prior to running ANY evaluator on this dataset.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / 'scratch' / 'public_fresh_raw'
OUT_DIR = Path(__file__).resolve().parent
MANIFEST = json.loads((RAW_DIR / 'manifest.json').read_text(encoding='utf-8'))


def raw_text(key: str) -> str:
    return (RAW_DIR / f'{key}.txt').read_text(encoding='utf-8')


def lines_join(key: str, start_1based: int, end_1based: int) -> str:
    ls = raw_text(key).splitlines()
    chunk = [l.strip() for l in ls[start_1based - 1:end_1based] if l.strip()]
    joined = '\n'.join(chunk)
    return joined


def assert_verbatim_lines(key: str, snippets: list[str]) -> str:
    full_norm = ' '.join(raw_text(key).split())
    for s in snippets:
        s_norm = ' '.join(s.split())
        assert s_norm in full_norm, f'Non-verbatim snippet for {key}: {s[:80]!r}'
    return '\n'.join(snippets)


def term(tid: str, label: str, why: str) -> dict:
    return {'id': tid, 'label': label, 'why': why, 'cost': 1, 'weight': 5}


def case(
    sample_id: str,
    lang: str,
    domain: str,
    source_key: str,
    source_title: str,
    policy_effective: str,
    jurisdiction: str,
    question: str,
    terms: list[dict],
    observations: dict,
    snippets: list[str],
    gt_decision: str,
    rationale: str,
    hidden_requirements: list[str] | None = None,
    scope_accepted: bool = True,
    source_verified: bool = True,
    coverage_reviewed: bool = True,
) -> dict:
    meta = MANIFEST[source_key]
    src_text = assert_verbatim_lines(source_key, snippets)
    return {
        'visible_input': {
            'sample_id': sample_id,
            'split': 'unseen_public_fresh',
            'domain': domain,
            'lang': lang,
            'source_key': source_key,
            'source_title': source_title,
            'source_url': meta['url'],
            'source_file_sha256': meta['sha256'],
            'retrieval_utc': meta['retrieval_utc'],
            'captured_utc': meta['retrieval_utc'],
            'policy_effective_date': policy_effective,
            'jurisdiction': jurisdiction,
            'question': question,
            'scopeAccepted': scope_accepted,
            'sourceVerified': source_verified,
            'coverageReviewed': coverage_reviewed,
            'policy': {
                'id': f'pf_{sample_id}',
                'title': source_title,
                'scope': policy_effective,
                'terms': terms,
            },
            'observations': observations,
            'source_text': src_text,
            'source_sha256': hashlib.sha256(src_text.encode('utf-8')).hexdigest(),
        },
        'ground_truth': {
            'gt_decision': gt_decision,
            'hidden_requirements': hidden_requirements or [],
            'rationale': rationale,
            'visible_facts': [f"{t['id']} ({t['label']}) = {observations.get(t['id'], 'unknown')}" for t in terms],
            'missing_facts': hidden_requirements or [],
            'gold_audit_status': 'SINGLE_AUTHOR_FROZEN_PRIOR_TO_EVAL_2026_11_22',
        },
    }


def main():
    cases = [
        # --- ENGLISH (10: 2 YES, 2 NO, 2 ASK, 2 CONFLICT, 2 OUT_OF_SCOPE) ---
        case(
            'fp_en_01', 'en', 'oss_licensing', 'bsd2_en',
            'SPDX BSD-2-Clause License', 'BSD-2-Clause (SPDX)', 'Global / Contract Law',
            'Can we redistribute both source and binary forms of this BSD-2-Clause library?',
            [
                term('source_notice', 'Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.', 'Clause 1'),
                term('binary_notice', 'Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.', 'Clause 2'),
            ],
            {'source_notice': 'yes', 'binary_notice': 'yes'},
            [
                '1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.',
                '2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.',
            ],
            'YES',
            'Both BSD-2-Clause redistribution obligations match confirmed checklist controls.',
        ),
        case(
            'fp_en_02', 'en', 'oss_licensing', 'apache2_en',
            'Apache License 2.0 Section 4(a)-(b)', 'Apache-2.0 (SPDX)', 'Global / Contract Law',
            'Can we distribute modified Apache-2.0 files if we ship a license copy and change notices?',
            [
                term('license_copy', 'You must give any other recipients of the Work or Derivative Works a copy of this License', 'Section 4(a)'),
                term('modified_notice', 'You must cause any modified files to carry prominent notices stating that You changed the files', 'Section 4(b)'),
            ],
            {'license_copy': 'yes', 'modified_notice': 'yes'},
            [
                '(a) You must give any other recipients of the Work or Derivative Works a copy of this License; and',
                '(b) You must cause any modified files to carry prominent notices stating that You changed the files; and',
            ],
            'YES',
            'Both excerpted Apache-2.0 Section 4(a)-(b) obligations match verified controls.',
        ),
        case(
            'fp_en_03', 'en', 'media_terms', 'apple_media_en',
            'Apple Media Services Section C Account Age', 'Apple Media Services Terms (US)', 'United States',
            'Can an 11-year-old create an Apple Account directly on their own under this clause?',
            [
                term('age_13', 'You must be age thirteen (13) (or equivalent minimum age in your Home Country) to create an account and use our Services.', 'Section C'),
            ],
            {'age_13': 'no'},
            [
                'You must be age thirteen (13) (or equivalent minimum age in your Home Country, as set forth in the Apple Account creation process) to create an account and use our Services.',
            ],
            'NO',
            'User confirmed minimum age 13 criterion is NOT met.',
        ),
        case(
            'fp_en_04', 'en', 'oss_licensing', 'apache2_en',
            'Apache License 2.0 Section 3 Patent Termination', 'Apache-2.0 (SPDX)', 'Global / Contract Law',
            'Do patent grants remain active if our company files a patent lawsuit over the Work?',
            [
                term('no_patent_suit', 'Company has not instituted patent litigation alleging the Work constitutes patent infringement.', 'Section 3 termination trigger'),
            ],
            {'no_patent_suit': 'no'},
            [
                'If You institute patent litigation against any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Work or a Contribution incorporated within the Work constitutes direct or contributory patent infringement, then any patent licenses granted to You under this License for that Work shall terminate as of the date such litigation is filed.',
            ],
            'NO',
            'Confirmed patent litigation negates ongoing Apache-2.0 patent license grant.',
        ),
        case(
            'fp_en_05', 'en', 'oss_licensing', 'isc_en',
            'SPDX ISC License', 'ISC License (SPDX)', 'Global / Contract Law',
            'Is retaining only the copyright line sufficient to redistribute this ISC module?',
            [
                term('copyright_line', 'Copyright notice appears in all copies', 'First notice requirement'),
            ],
            {'copyright_line': 'yes'},
            [
                'Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.',
            ],
            'ASK',
            'ISC requires both copyright notice and permission notice in all copies; checklist omits permission notice.',
            hidden_requirements=['permission notice'],
        ),
        case(
            'fp_en_06', 'en', 'media_terms', 'apple_media_en',
            'Apple Media Services Section F Rentals', 'Apple Media Services Terms (US)', 'United States',
            'Is keeping a rental on one device enough to comply with playback rules?',
            [
                term('single_device', 'Content rentals are viewable on a single device at a time', 'Device limit'),
            ],
            {'single_device': 'yes'},
            [
                'Content rentals are viewable on a single device at a time, and must be played within thirty (30) days, and completed within forty-eight (48) hours of the start of play (stopping, pausing or restarting does not extend this period).',
            ],
            'ASK',
            'Clause additionally requires playing within 30 days and finishing within 48 hours of start.',
            hidden_requirements=['30 days', '48 hours'],
        ),
        case(
            'fp_en_07', 'en', 'privacy_policy', 'wikimedia_priv_en',
            'Wikimedia Privacy Policy IP Retention vs Abuse Investigation', 'Effective Oct 6, 2025', 'Global / US',
            'Can our legal brief state IP addresses are guaranteed unlinked to usernames?',
            [
                term('no_name_needed', 'No real name or email is required for a standard account', 'Account registration'),
                term('ip_username_unlinked', 'IP addresses remain unassociated with usernames during abuse investigations', 'IP linkability'),
            ],
            {'no_name_needed': 'yes', 'ip_username_unlinked': 'conflict'},
            [
                'Your password is only used to verify that the account is yours. Your IP address is also automatically submitted to us, and we record it temporarily. This is to protect Wikimedia users and project content; in the event of abuse, IP addresses may be associated with usernames as part of an investigation.',
            ],
            'CONFLICT',
            'Conflicting evidence/interpretation on whether IP addresses remain unlinked under abuse investigation.',
        ),
        case(
            'fp_en_08', 'en', 'media_terms', 'apple_media_en',
            'Apple Media Services EULA Liability Cap Override', 'Apple Media Services Terms', 'Consumer / Cross-Border',
            'Does the flat $250 liability cap strictly apply regardless of statutory consumer rights?',
            [
                term('statutory_vs_cap', 'Contractual $250 liability cap governs without statutory consumer override', 'Liability conflict'),
            ],
            {'statutory_vs_cap': 'conflict'},
            [
                'SOME JURISDICTIONS DO NOT ALLOW THE EXCLUSION OR LIMITATION OF LIABILITY FOR PERSONAL INJURY, OR OF INCIDENTAL OR CONSEQUENTIAL DAMAGES, SO THIS LIMITATION MAY NOT APPLY TO YOU. In no event shall Licensor’s total liability to you for all damages (other than as may be required by applicable law in cases involving personal injury) exceed the amount of two hundred and fifty dollars ($250.00).',
            ],
            'CONFLICT',
            'Mandatory local consumer statute conflicts with the contractual $250 total liability ceiling.',
        ),
        case(
            'fp_en_09', 'en', 'oss_licensing', 'ccby4_en',
            'Creative Commons BY 4.0 Section 2(a)(2) Fair Use', 'CC BY 4.0 International', 'Global',
            'Must a teacher quoting a short excerpt under statutory fair dealing follow CC BY 4.0 license terms?',
            [
                term('fair_use_covered', 'Use falls under CC BY 4.0 rather than statutory Exceptions and Limitations', 'License scope'),
            ],
            {'fair_use_covered': 'yes'},
            [
                'Exceptions and Limitations . For the avoidance of doubt, where Exceptions and Limitations apply to Your use, this Public License does not apply, and You do not need to comply with its terms and conditions.',
            ],
            'OUT_OF_SCOPE',
            'Section 2(a)(2) explicitly puts statutory fair use/fair dealing outside the license scope.',
            scope_accepted=False,
        ),
        case(
            'fp_en_10', 'en', 'privacy_policy', 'wikimedia_priv_en',
            'Wikimedia Privacy Policy Alternative Policies', 'Effective Oct 6, 2025', 'Global',
            'Does the general Wikimedia Privacy Policy govern donor payment processing on donate.wikimedia.org?',
            [
                term('covered_by_main', 'Site falls under general Wikimedia Privacy Policy rather than Donor Privacy Policy', 'Scope boundary'),
            ],
            {'covered_by_main': 'yes'},
            [
                'This Privacy Policy, however, does not cover some situations where we may gather or process information.',
                'Some Wikimedia Foundation websites or tools have alternative privacy policies or provisions that differ from this Privacy Policy. These websites include:',
                'donate.wikimedia.org , including the donation process, such as clicking on a donation banner (covered by the Donor Privacy Policy );',
            ],
            'OUT_OF_SCOPE',
            'Donations on donate.wikimedia.org are governed by the separate Donor Privacy Policy.',
            scope_accepted=False,
        ),

        # --- TURKISH (10: 2 YES, 2 NO, 2 ASK, 2 CONFLICT, 2 OUT_OF_SCOPE) ---
        case(
            'fp_tr_01', 'tr', 'privacy_policy', 'wikimedia_priv_tr',
            'Wikimedia Gizlilik Politikası (Hesapsız Okuma)', 'Effective Oct 6, 2025 (TR)', 'Global / TR',
            'Wikimedia sitelerini okumak için standart kullanıcı hesabı açmak zorunlu mu?',
            [
                term('no_signup_needed', 'Okuma ya da paylaşım yapmak için nadir durumlar haricinde üye olma zorunluluğu yoktur', 'Üyelik muafiyeti'),
                term('temp_account_public', 'Üye olmadan yapılan katkılar geçici hesapla alenen gösterilir', 'Geçici hesap şeffaflığı'),
            ],
            {'no_signup_needed': 'yes', 'temp_account_public': 'yes'},
            [
                'Wikimedia sitelerinde okuma ya da paylaşım yapmak için nadir durumlar haricinde üye olmak zorunda değilsiniz. Ancak, eğer üye olmadan katkıda bulunursanız, yaptığınız paylaşımlar geçici hesabınız ile beraber alenen gösterilecek.',
            ],
            'YES',
            'Hem üyeliksiz okuma kuralı hem de geçici hesap kamusallığı onaylanmıştır.',
        ),
        case(
            'fp_tr_02', 'tr', 'privacy_policy', 'wikimedia_priv_tr',
            'Wikimedia Gizlilik Politikası Değişiklik Süreci', 'Effective Oct 6, 2025 (TR)', 'Global / TR',
            'Önemli politika değişikliği öncesinde 30 günlük kamu görüşü şartı sağlandı mı?',
            [
                term('public_comment_30', 'En az 30 günlük bir kamu görüşü dönemi tamamlanmadan bu Politika\'da önemli değişiklikler yapılmayacaktır.', '30 gün şartı'),
            ],
            {'public_comment_30': 'yes'},
            [
                'En az 30 günlük bir kamu görüşü dönemi tamamlanmadan bu Politika\'da önemli değişiklikler yapılmayacaktır.',
            ],
            'YES',
            'Politika değişikliği için gereken 30 günlük kamu görüşü süreci doğrulanmıştır.',
        ),
        case(
            'fp_tr_03', 'tr', 'oss_licensing', 'ccby4_tr',
            'CC BY 4.0 Türkçe Bölüm 2(a)(5)(B) Aşağı Yönlü Sınırlama Yasağı', 'CC BY 4.0 TR', 'Global / TR',
            'CC BY 4.0 materyalini alıcıların erişimini kısıtlayan DRM ile dağıtabilir miyiz?',
            [
                term('no_etp', 'Lisanslı Materyale Etkin Teknolojik Önlemler uygulanmamıştır ve ek şart dayatılmamıştır', 'Kısıtlama yasağı'),
            ],
            {'no_etp': 'no'},
            [
                'Aşağı yönlü sınırlamanın olmayışı . Bunun herhangi bir Lisanslı Materyal alıcısının Lisansa Konu Hakları kullanımını sınırlaması hâlinde, Lisanslı Materyal üzerinde hiçbir ek veya farklı şart veya koşullar teklif edemez veya dayatamaz veya Lisanslı Materyale Etkin Teknolojik Önlemler uygulayamazsınız.',
            ],
            'NO',
            'DRM / etkin teknolojik önlem uygulanmaması şartı hayır olarak doğrulanmıştır.',
        ),
        case(
            'fp_tr_04', 'tr', 'platform_terms', 'google_terms_tr',
            'Google Hizmet Şartları Otomatik Tarama Kısıtı', 'Effective 30 July 2026 (TR)', 'Global / TR',
            'robots.txt dosyasını yok sayarak eğitim verisi çekmek bu şartlara uygun mu?',
            [
                term('robots_compliance', 'robots.txt gibi makine tarafından okunabilir talimatlara uyulmaktadır', 'Otomatik erişim kuralı'),
            ],
            {'robots_compliance': 'no'},
            [
                'web sayfalarımızda makine tarafından okunabilir talimatları ihlal edecek şekilde, hizmetlerimizden herhangi birindeki içeriğe erişmek için otomatik yöntemler kullanma (ör. tarama, eğitim veya diğer etkinliklere izin vermeyen robots.txt dosyaları)',
            ],
            'NO',
            'robots.txt talimatlarına uyulmadığı doğrulanmıştır.',
        ),
        case(
            'fp_tr_05', 'tr', 'privacy_policy', 'google_priv_tr',
            'Google Gizlilik Politikası Yeni Amaç İçin İzin', 'Effective 16 Oct 2026 (TR)', 'Global / TR',
            'Drive verilerinden reklam göstermemek yeni amaç için veriyi kullanmaya yeter mi?',
            [
                term('no_drive_ads', 'Drive, Gmail veya Google Fotoğraflar içeriklerine dayanarak kişiselleştirilmiş reklam gösterilmez', 'Reklam kısıtı'),
            ],
            {'no_drive_ads': 'yes'},
            [
                'Kişiselleştirilmiş reklamları destekleyen diğer Google hizmetlerinde bu verilerin kullanılmasını tercih etmediğiniz sürece Drive, Gmail veya Google Fotoğraflar\'daki içeriklerinize dayanarak size kişiselleştirilmiş reklamlar göstermeyiz.',
                'Bilgilerinizi bu Gizlilik Politikası\'nda yer almayan bir amaç doğrultusunda kullanmadan önce sizden izin isteriz.',
            ],
            'ASK',
            'Metin politika dışı her yeni amaç için açık kullanıcı izni zorunluluğu ekler; kontrol listesinde eksik.',
            hidden_requirements=['izin'],
        ),
        case(
            'fp_tr_06', 'tr', 'platform_terms', 'wikimedia_tou_tr',
            'Wikimedia Kullanım Şartları Bölüm 4 Reşit Olmayanlar', 'Wikimedia ToU TR', 'Global / TR',
            'Ticari amaçlı veri talebi yasağını doğrulamak bu maddeye uyum için yeterli mi?',
            [
                term('no_promo_pii', 'Onaylanmamış promosyon veya ticari amaçlarla kişisel bilgi istenmez', 'Ticari gizlilik'),
            ],
            {'no_promo_pii': 'yes'},
            [
                'Taciz, kötüye kullanım, gizlilik ihlali ya da Wikimedia Vakfı tarafından özellikle onaylanmamış olan promosyon veya ticari amaçlarla kişisel olarak tanınmaya yol açacak bilgileri isteme ve',
                '18 yaşın altındaki birinden yasa dışı bir amaç için kişisel olarak tanınmaya yol açacak bilgiler isteme veya reşit olmayanların sağlık veya refahına ilişkin herhangi bir geçerli yasayı ihlal etme.',
            ],
            'ASK',
            '18 yaş altı bireylerin sağlığı ve refahına ilişkin ek yasak kontrol listesinde yoktur.',
            hidden_requirements=['18'],
        ),
        case(
            'fp_tr_07', 'tr', 'platform_terms', 'wikimedia_tou_tr',
            'Wikimedia Kullanım Koşulları Dil Önceliği Çelişkisi', 'Wikimedia ToU TR', 'Global / TR',
            'Türkçe metindeki yorum İngilizce aslından farklıysa Türkçe metin esas alınabilir mi?',
            [
                term('tr_translation_binding', 'Türkçe çeviri ile İngilizce asıl metin arasındaki anlam uyuşmazlığı çözüldü', 'Dil önceliği'),
            ],
            {'tr_translation_binding': 'conflict'},
            [
                'İşbu içeriğin İngilizce asıl metni ile herhangi bir tercümesi arasında anlam veya yorumlama açısından çelişki bulunması durumunda İngilizce metin öncelik teşkil edecektir.',
            ],
            'CONFLICT',
            'İngilizce asıl metin ile Türkçe çeviri arasında yorum farkı/çelişki bildirildi.',
        ),
        case(
            'fp_tr_08', 'tr', 'platform_terms', 'google_terms_tr',
            'Google Hizmet Şartları California vs Yerel Yasa Çakışması', 'Effective 30 July 2026 (TR)', 'Cross-Border / TR',
            'Tüketici uyuşmazlığı yalnızca California mahkemelerinde mi görülmek zorundadır?',
            [
                term('governing_law', 'Yetkili hukuk ve mahkeme uyuşmazlığı netleştirildi', 'Yargı yetkisi'),
            ],
            {'governing_law': 'conflict'},
            [
                'Bu şartlar ile bu şartlardan, hizmete özgü ek şartlardan veya ilgili hizmetlerden kaynaklanan ya da bunlarla alakalı tüm anlaşmazlıklarda kanunlar ihtilafı kurallarından bağımsız olarak California yasaları geçerli olacaktır.',
                'Geçerli yerel yasalar uyarınca belirli uyuşmazlıklar Kaliforniya mahkemelerinde çözümlenemiyorsa, bu uyuşmazlıklar için yerel mahkemelerinize başvurabilirsiniz.',
            ],
            'CONFLICT',
            'California hukuku hükmü ile emredici yerel tüketici kanunu arasında yargı yetkisi çakışması vardır.',
        ),
        case(
            'fp_tr_09', 'tr', 'oss_licensing', 'ccby4_tr',
            'CC BY 4.0 Türkçe Bölüm 2(a)(2) İstisnalar ve Sınırlamalar', 'CC BY 4.0 TR', 'Global / TR',
            'Adil kullanım istisnası kapsamındaki alıntılar CC BY 4.0 lisansı kapsamına girer mi?',
            [
                term('under_cc_scope', 'Kullanım yasal istisna yerine CC BY 4.0 kapsamındadır', 'Lisans kapsamı'),
            ],
            {'under_cc_scope': 'yes'},
            [
                'İstisnalar ve Sınırlamalar. Herhangi bir şüpheye mahal vermemek adına, Sizin kullanımız ile ilgili herhangi bir İstisna ve Sınırlamanın geçerli olduğu durumlarda işbu Kamu Lisansı geçerli olmayacak olup, bu lisansın şart ve koşullarına riayet etmeniz gerekmemektedir.',
            ],
            'OUT_OF_SCOPE',
            'Yasal istisna ve sınırlamaların geçerli olduğu kullanımlar CC BY 4.0 kapsamı dışındadır.',
            scope_accepted=False,
        ),
        case(
            'fp_tr_10', 'tr', 'privacy_policy', 'wikimedia_priv_tr',
            'Wikimedia Gizlilik Politikası Kapsam Dışı Siteler', 'Effective Oct 6, 2025 (TR)', 'Global / TR',
            'Wikimedia Mağazası verileri bu genel gizlilik politikası kapsamında mıdır?',
            [
                term('main_policy_applies', 'Hizmet genel Wikimedia Gizlilik Politikasına tabidir', 'Politika kapsamı'),
            ],
            {'main_policy_applies': 'yes'},
            [
                'Bazı Wikimedia Vakfı web sitelerinin bu Gizlilik Politikasından farklı alternatif gizlilik politikaları veya hükümleri vardır. Bu web siteleri şunlardır:',
                'Wikimedia Mağazası ( Mağazanın politikası kapsamındadır );',
                'donate.wikimedia.org , bir bağış linkine tıklamak gibi bağış sürecini içerir ( Bağış Gizlilik Politikası kapsamındadır.);',
            ],
            'OUT_OF_SCOPE',
            'Wikimedia Mağazası ve bağış sayfası alternatif politikaların kapsamındadır.',
            scope_accepted=False,
        ),

        # --- PERSIAN (10: 2 YES, 2 NO, 2 ASK, 2 CONFLICT, 2 OUT_OF_SCOPE) ---
        case(
            'fp_fa_01', 'fa', 'privacy_policy', 'google_priv_fa',
            'خط‌مشی رازداری Google (رمزگذاری و راستی‌آزمایی ۲ مرحله‌ای)', 'Google Privacy Policy FA', 'Global / FA',
            'آیا الزامات انتقال امن داده و حفاظت حساب در این بخش تأیید شده است؟',
            [
                term('transit_encryption', 'از رمزگذاری برای حفظ خصوصی داده‌ها هنگام انتقال استفاده می‌شود', 'رمزگذاری انتقال'),
                term('two_factor_features', 'ویژگی‌های امنیتی مانند مرور ایمن و راستی‌آزمایی ۲ مرحله‌ای ارائه می‌شود', 'حفاظت حساب'),
            ],
            {'transit_encryption': 'yes', 'two_factor_features': 'yes'},
            [
                'از رمزگذاری استفاده می‌کنیم تا داده‌های شما هنگام انتقال به‌صورت خصوصی حفظ شوند',
                'مجموعه‌ای از ویژگی‌های امنیتی (مانند مرور ایمن ، بررسی امنیتی و راستی‌آزمایی ۲ مرحله‌ای ) را برای کمک به شما برای محافظت از حسابتان ارائه می‌کنیم',
            ],
            'YES',
            'هر دو کنترل امنیت انتقال و حفاظت حساب به صراحت تأیید شده‌اند.',
        ),
        case(
            'fp_fa_02', 'fa', 'privacy_policy', 'wikimedia_priv_fa',
            'سیاست حفظ حریم خصوصی ویکی‌مدیا (ساخت حساب)', 'Wikimedia Privacy FA', 'Global / FA',
            'آیا استفاده از وبگاه ویکی‌مدیا بدون نام واقعی و نشانی ایمیل مجاز است؟',
            [
                term('no_account_required', 'برای استفاده از وبگاه ویکی‌مدیا نیاز به ساخت حساب کاربری نیست', 'عدم اجبار ثبت‌نام'),
                term('no_realname_needed', 'در صورت ایجاد حساب نیازی به ارائه نام یا آدرس ایمیل نیست', 'حفظ ناشناسی'),
            ],
            {'no_account_required': 'yes', 'no_realname_needed': 'yes'},
            [
                'شما برای استفاده از وبگاه ویکی‌مدیا نیاز به ساخت حساب کاربری ندارید.',
                'اگر شما یک حساب ایجاد می کنید، نیازی نیست که نام و یا آدرس ایمیلتان را به ما بدهید.',
            ],
            'YES',
            'هر دو بند عدم نیاز به حساب و عدم نیاز به نام و ایمیل تایید شده است.',
        ),
        case(
            'fp_fa_03', 'fa', 'platform_terms', 'wikimedia_tou_fa',
            'شرایط استفاده ویکی‌مدیا (ممنوعیت جعل هویت)', 'Wikimedia ToU FA', 'Global / FA',
            'آیا استفاده از نام کاربری دیگران به قصد فریبکاری طبق شرایط استفاده مجاز است؟',
            [
                term('no_impersonation', 'تلاش برای جعل هویت کاربر دیگر یا استفاده فریبکارانه از نام کاربری انجام نشده است', 'منع جعل هویت'),
            ],
            {'no_impersonation': 'no'},
            [
                'تلاش برای جعل هویت کاربر یا فردی دیگر، وانمود کردن به وابستگی داشتن به شخص یا نهادی خاص، یا استفاده از نام کاربری کاربر دیگری به قصد فریبکاری؛',
            ],
            'NO',
            'شرط منع جعل هویت و استفاده فریبکارانه نقض شده است (no).',
        ),
        case(
            'fp_fa_04', 'fa', 'platform_terms', 'google_terms_fa',
            'شرایط خدمات Google (ممنوعیت فروش یا اجاره نرم‌افزار)', 'Google Terms FA', 'Global / FA',
            'آیا کپی، توزیع و کرایه‌دادن نرم‌افزار بدون مجوز تحت این شرط مجاز است؟',
            [
                term('no_copy_or_rent', 'هیچ بخشی از سرویس‌ها یا نرم‌افزار کپی، توزیع، فروخته یا کرایه داده نمی‌شود', 'ممنوعیت بازفروش'),
            ],
            {'no_copy_or_rent': 'no'},
            [
                'اجازه ندارید هیچ بخشی از سرویس‌ها یا نرم‌افزار ما را کپی کنید، تغییر دهید، توزیع کنید، بفروشید یا کرایه دهید.',
            ],
            'NO',
            'شرط صریح منع کپی و اجاره نرم‌افزار نقض شده است.',
        ),
        case(
            'fp_fa_05', 'fa', 'oss_licensing', 'ccby4_fa_deed',
            'سند CC BY 4.0 فارسی (اعتبار مناسب و اعلام تغییرات)', 'CC BY 4.0 Deed FA', 'Global / FA',
            'آیا صرفاً ذکر نام پدیدآورنده برای انتشار نسخه تغییریافته تحت CC BY 4.0 کافی است؟',
            [
                term('creator_credit', 'نام پدیدآورنده و طرفین ارجاع درج شده است', 'اعتبار پدیدآورنده'),
            ],
            {'creator_credit': 'yes'},
            [
                'اعتبار مناسب — اگر عرضه شود، شما باید نام پدیدآورنده و طرفین ارجاع، یک اعلان حق تکثیر، یک اعلان پروانه، یک اعلان سلب مسئولیت، و یک پیوند به مواد ارائه کنید.',
                'اگر تغییری صورت گرفته‌است به آن اشاره کنید — در نگارش 4.0، شما باید به اینکه مواد را تغییر دادید اشاره کنید و یک اشاره از تغییرات قبلی را حفظ کنید.',
            ],
            'ASK',
            'مستند علاوه بر نام پدیدآورنده، اعلان پروانه، پیوند و اشاره به تغییرات را الزامی می‌داند.',
            hidden_requirements=['تغییری', 'اعلان پروانه'],
        ),
        case(
            'fp_fa_06', 'fa', 'platform_terms', 'google_terms_fa',
            'شرایط خدمات Google (فرصت رفع مشکل و شرح دلیل)', 'Google Terms FA', 'Global / FA',
            'آیا ارسال پیش‌اعلان به تنهایی پیش از تعلیق یا برداشتن محتوا کافی است؟',
            [
                term('prior_notice', 'پیش‌اعلان پیش از انجام اقدام ارائه می‌شود', 'اطلاع‌رسانی قبلی'),
            ],
            {'prior_notice': 'yes'},
            [
                'پیش‌از انجام اقداماتی که در زیر شرح داده شده است، هر زمان که به‌طور منطقی امکان‌پذیر باشد پیش‌اعلانی به شما ارائه می‌کنیم، دلیل اقدام خود را شرح می‌دهیم، و فرصت رسیدگی و رفع مشکل را به شما می‌دهیم',
            ],
            'ASK',
            'متن علاوه بر پیش‌اعلان، شرح دلیل اقدام و دادن فرصت رسیدگی و رفع مشکل را نیز شرط کرده است.',
            hidden_requirements=['فرصت رسیدگی', 'دلیل اقدام'],
        ),
        case(
            'fp_fa_07', 'fa', 'governance_policy', 'wikimedia_ucoc_fa',
            'آیین‌نامه فراگیر رفتاری ویکی‌مدیا (اولویت نسخه انگلیسی)', 'Wikimedia UCoC FA', 'Global / FA',
            'آیا در صورت تعارض معنایی بین ترجمه فارسی و متن انگلیسی می‌توان به ترجمه فارسی استناد کرد؟',
            [
                term('translation_precedence', 'تعارض تفسیری بین ترجمه فارسی و متن اصلی انگلیسی بررسی و حل شده است', 'تعارض ترجمه'),
            ],
            {'translation_precedence': 'conflict'},
            [
                'لطفاً توجه داشته باشید که در صورت وجود هرگونه تفاوت در معنا یا تفسیر بین نسخه انگلیسی اصلی این محتوا و ترجمه، نسخه انگلیسی اصلی اولویت دارد.',
            ],
            'CONFLICT',
            'وجود تعارض در معنا بین نسخه ترجمه و نسخه انگلیسی اصلی نیازمند رجوع به متن انگلیسی است.',
        ),
        case(
            'fp_fa_08', 'fa', 'platform_terms', 'google_terms_fa',
            'شرایط خدمات Google (تعارض قانون کالیفرنیا و قانون محلی)', 'Google Terms FA', 'Cross-Border / FA',
            'آیا تمامی دعاوی الزاماً تحت قانون کالیفرنیا و در سانتاکلارا رسیدگی می‌شوند؟',
            [
                term('law_and_venue', 'تعارض بین قانون کالیفرنیا و قوانین محلی آمره مشخص شده است', 'تعارض قانون حاکم'),
            ],
            {'law_and_venue': 'conflict'},
            [
                lines_join('google_terms_fa', 154, 155),
            ],
            'CONFLICT',
            'قانون قراردادی کالیفرنیا با قوانین محلی آمره در محل سکونت کاربر تعارض احتمالی دارد.',
        ),
        case(
            'fp_fa_09', 'fa', 'oss_licensing', 'ccby4_fa_deed',
            'سند CC BY 4.0 فارسی (خروج استفاده منصفانه از شمول پروانه)', 'CC BY 4.0 Deed FA', 'Global / FA',
            'آیا استناد به استفاده منصفانه در آموزش تابع شروط قراردادی CC BY 4.0 است؟',
            [
                term('within_license_scope', 'استفاده در شمول پروانه CC BY 4.0 قرار می‌گیرد و خارج از استثنائات قانونی است', 'شمول پروانه'),
            ],
            {'within_license_scope': 'yes'},
            [
                lines_join('ccby4_fa_deed', 52, 54),
            ],
            'OUT_OF_SCOPE',
            'موارد استفاده منصفانه و استثنائات قانونی خارج از شمول پروانه CC BY 4.0 هستند.',
            scope_accepted=False,
        ),
        case(
            'fp_fa_10', 'fa', 'privacy_policy', 'wikimedia_priv_fa',
            'سیاست حفظ حریم خصوصی ویکی‌مدیا (موقعیت‌های خارج از شمول)', 'Wikimedia Privacy FA', 'Global / FA',
            'آیا سیاست عمومی ویکی‌مدیا بر تراکنش‌های فروشگاه ویکی‌مدیا و صفحه اهدای مالی حاکم است؟',
            [
                term('general_policy_scope', 'این خدمت در شمول سیاست عمومی ویکی‌مدیا قرار دارد', 'مرز شمول سیاست'),
            ],
            {'general_policy_scope': 'yes'},
            [
                lines_join('wikimedia_priv_fa', 84, 84),
            ],
            'OUT_OF_SCOPE',
            'بند صریحاً فروشگاه ویکی‌مدیا و خدمات دارای سیاست جداگانه را خارج از پوشش اعلام می‌کند.',
            scope_accepted=False,
        ),
    ]

    payload = {
        'metadata': {
            'dataset_name': 'gapwise_fresh_unseen_public_30_v1',
            'created_utc': '2026-11-22T19:45:00Z',
            'methodology': '30 verbatim excerpts extracted directly from newly fetched official public documents (EN:10, TR:10, FA:10; balanced 6 per class across YES/NO/ASK/CONFLICT/OUT_OF_SCOPE). Zero overlap with real_world_36 or balanced_200. Adjudication rubric is single-author frozen BEFORE executing GAPWISE once.',
            'counts': {'total': len(cases), 'en': 10, 'tr': 10, 'fa': 10, 'per_class': 6},
        },
        'cases': cases,
    }
    out_path = OUT_DIR / 'fresh_public_corpus_30.json'
    out_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
    out_path.write_bytes(out_bytes)
    corpus_sha = hashlib.sha256(out_bytes).hexdigest()
    (OUT_DIR / 'CORPUS_SHA256_FROZEN.txt').write_text(f'{corpus_sha}  fresh_public_corpus_30.json\n', encoding='utf-8')
    print(f'FROZEN {len(cases)} cases -> {out_path} sha256={corpus_sha}')


if __name__ == '__main__':
    main()
