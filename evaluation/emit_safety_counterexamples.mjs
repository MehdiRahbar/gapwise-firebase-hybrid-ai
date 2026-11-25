/**
 * Executes paired 5-way adversarial safety counterexamples across EN, TR (rw_015, rw_033), and FA (rw_036)
 * and emits evidence/SAFETY_COUNTEREXAMPLES.json for independent verification.
 */
import fs from 'node:fs';
import { analyzeSourceDocument } from '../web/source-audit.mjs';
import { evaluateStrict, STATUS, SAMPLE_POLICIES } from '../web/engine.mjs';

const families = [
  {
    family: 'en_refund_policy',
    policy: SAMPLE_POLICIES[0],
    cleanSource:
      '1. Return requests must be submitted within 14 days of delivery.\n' +
      '2. Customers must provide an order receipt or proof of purchase.\n' +
      '3. Returned items must be unused and in original condition.\n' +
      '4. Final-sale merchandise is excluded.',
    yesObs: { period: 'yes', receipt: 'yes', unused: 'yes', clearance: 'yes' },
    noObs: { period: 'yes', receipt: 'yes', unused: 'no', clearance: 'yes' },
    extraSource:
      '1. Return requests must be submitted within 14 days of delivery.\n' +
      '2. Customers must provide an order receipt or proof of purchase.\n' +
      '3. Returned items must remain inside an unopened tamper seal.\n' +
      '4. Final-sale merchandise is excluded.',
    conflictSource:
      '1. Standard purchases are refundable within 14 days of delivery.\n' +
      '2. Online flash orders must be submitted within 7 days of delivery.',
  },
  {
    family: 'tr_madde9_withdrawal_rw015',
    policy: {
      id: 'p_tr_9',
      title: 'TR 14 Gun Cayma',
      scope: 'Mesafeli Sozlesmeler Md 9-11',
      question: '14 gun icinde bildirim gecerli mi?',
      terms: [
        { id: 'sure14', label: 'Tüketici on dört gün içinde gerekçe göstermeksizin cayma hakkını kullanmaktadır', why: 'Madde 9(1)', cost: 1, weight: 5 },
        { id: 'kalici', label: 'Cayma bildirimi süre dolmadan yazılı olarak veya kalıcı veri saklayıcısı ile yöneltilmektedir', why: 'Madde 11(1)', cost: 1, weight: 5 },
      ],
    },
    cleanSource:
      'Tüketici, on dört gün içinde herhangi bir gerekçe göstermeksizin ve cezai şart ödemeksizin sözleşmeden cayma hakkına sahiptir.\n' +
      'Cayma hakkının kullanıldığına dair bildirimin cayma hakkı süresi dolmadan, yazılı olarak veya kalıcı veri saklayıcısı ile satıcı veya sağlayıcıya yöneltilmesi yeterlidir.',
    yesObs: { sure14: 'yes', kalici: 'yes' },
    noObs: { sure14: 'no', kalici: 'yes' },
    extraSource:
      'Tüketici, on dört gün içinde herhangi bir gerekçe göstermeksizin sözleşmeden cayma hakkına sahiptir.\n' +
      'Ayrıca hijyen mührü açılmamış olmalıdır.',
    conflictSource:
      'Tüketici, on dört gün içinde gerekçe göstermeksizin sözleşmeden cayma hakkına sahiptir.\n' +
      'Kampanyalı ürünlerde cayma bildirimi en geç 7 gün içinde gönderilmelidir.',
  },
  {
    family: 'tr_madde13_return_rw033',
    policy: {
      id: 'p_tr_13',
      title: 'TR Iade Gonderim',
      scope: 'Mesafeli Sozlesmeler Md 13',
      question: '10 gun iade ve uygun kullanim tamam mi?',
      terms: [
        { id: 'on_gun', label: 'Tüketici cayma bildirimini yönelttiği tarihten itibaren on gün içinde malı geri göndermektedir', why: 'Madde 13(1)', cost: 1, weight: 5 },
        { id: 'uygun_kullanim', label: 'Mal cayma süresi içinde işleyişine ve kullanım talimatlarına uygun kullanılmıştır', why: 'Madde 13(2)', cost: 2, weight: 5 },
      ],
    },
    cleanSource:
      'Tüketici cayma hakkını kullandığına ilişkin bildirimi yönelttiği tarihten itibaren on gün içinde malı satıcı veya sağlayıcıya ya da yetkilendirmiş olduğu kişiye geri göndermek zorundadır.\n' +
      'Tüketici, cayma süresi içinde malı, işleyişine, teknik özelliklerine ve kullanım talimatlarına uygun bir şekilde kullandığı takdirde meydana gelen değişiklik ve bozulmalardan sorumlu değildir.',
    yesObs: { on_gun: 'yes', uygun_kullanim: 'yes' },
    noObs: { on_gun: 'yes', uygun_kullanim: 'no' },
    extraSource:
      'Tüketici 10 gün içinde malı geri göndermek zorundadır.\nEk olarak yetkili teknik servis raporu sunulmalıdır.',
    conflictSource:
      'Tüketici bildirimi yönelttiği tarihten itibaren 10 gün içinde malı geri göndermek zorundadır.\n' +
      'Elektronik cihazlarda iade gönderim süresi 5 gün olarak uygulanır.',
  },
  {
    family: 'fa_password_rw036',
    policy: {
      id: 'p_fa_pw',
      title: 'بررسی امنیت گذرواژه',
      scope: 'شرایط استفاده ویکی‌مدیا',
      question: 'آیا شرایط امنیت گذرواژه رعایت شده است؟',
      terms: [
        { id: 'security', label: 'کاربر مسئول حفظ امنیت گذرواژه‌ خود است', why: 'تعهد نگهداری', cost: 1, weight: 5 },
        { id: 'third_party', label: 'گذرواژه برای هیچ شخص ثالثی افشا نمی‌شود', why: 'ممنوعیت افشا', cost: 1, weight: 5 },
      ],
    },
    cleanSource: 'شما مسئول حفظ امنیت گذرواژه‌تان هستید و نباید آن را برای هیچ شخص ثالثی افشا کنید.',
    yesObs: { security: 'yes', third_party: 'yes' },
    noObs: { security: 'yes', third_party: 'no' },
    extraSource: 'شما مسئول حفظ امنیت گذرواژه‌تان هستید و گذرواژه برای هیچ شخص ثالثی افشا نمی‌شود و احراز دوعاملی سخت‌افزاری الزامی است.',
    conflictSource:
      'استفاده ایمن از حساب کاربری مجاز است.\nدر صورت افشا حساب غیرقابل بازگشت و مسدود می‌گردد.',
  },
];

const rows = [];
let unsafeYesCount = 0;

for (const f of families) {
  const variants = [
    ['verified_positive', f.cleanSource, f.yesObs, true, STATUS.YES],
    ['negation_failed_term', f.cleanSource, f.noObs, true, STATUS.NO],
    ['unknown_extra_requirement', f.extraSource, f.yesObs, true, STATUS.ASK],
    ['competing_conflict_rule', f.conflictSource, f.yesObs, true, STATUS.CONFLICT],
    ['pasted_source_mutation_unattested', f.cleanSource, f.yesObs, false, STATUS.ASK],
  ];
  for (const [kind, src, obs, attested, expected] of variants) {
    const audit = analyzeSourceDocument(src, f.policy, { maxCandidates: 24, includeUnclassified: true });
    const res = evaluateStrict(f.policy, obs, {
      scopeAccepted: true,
      sourceVerified: attested,
      coverageReviewed: attested,
      sourceText: src,
      pendingReviews: audit.novelCount,
      truncatedCandidates: audit.truncatedCount,
      truncatedByCharLimit: audit.truncatedByCharLimit,
      sourceConflictCount: audit.conflictSignals.length,
    });
    if (expected !== STATUS.YES && res.status === STATUS.YES) unsafeYesCount += 1;
    if (res.status !== expected) {
      throw new Error(`Counterexample mismatch ${f.family}/${kind}: expected ${expected}, got ${res.status}`);
    }
    rows.push({
      family: f.family,
      variant: kind,
      expected_status: expected,
      actual_status: res.status,
      certification_tier: res.certificationTier,
      bounded_positive: res.boundedPositive,
      novel_count: audit.novelCount,
      conflict_signals: audit.conflictSignals.length,
      passed: res.status === expected,
    });
  }
}

const report = {
  generated_utc: new Date().toISOString(),
  total_counterexamples: rows.length,
  families_tested: families.length,
  unsafe_yes_count: unsafeYesCount,
  all_passed: rows.every((r) => r.passed),
  cases: rows,
};

fs.writeFileSync(new URL('../evidence/SAFETY_COUNTEREXAMPLES.json', import.meta.url), JSON.stringify(report, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ total_counterexamples: report.total_counterexamples, unsafe_yes_count: unsafeYesCount, all_passed: report.all_passed }));
