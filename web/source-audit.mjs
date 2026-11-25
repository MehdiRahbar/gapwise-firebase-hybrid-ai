/**
 * Source document candidate extraction and coverage-uncertainty audit.
 * Strictly untrusted proposal generator — never sets attested yes/no facts.
 */
const DIACRITICS_RE = /[\u064b-\u065f\u0670\u06d6-\u06ed]/g;
const PERSIAN_DIGITS_RE = /[\u06f0-\u06f9\u0660-\u0669]/g;
const toAsciiDigits = (s) =>
  String(s ?? '').replace(PERSIAN_DIGITS_RE, (ch) => {
    const code = ch.charCodeAt(0);
    return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
  });

const normalize = (s) =>
  toAsciiDigits(s)
    .replace(/\u064a|\u0649/g, '\u06cc')
    .replace(/\u0643/g, '\u06a9')
    .replace(/\u200c/g, ' ')
    .replace(/İ/g, 'i')
    .replace(/I(?=[a-zçğıöşü])/g, 'ı')
    .replace(DIACRITICS_RE, '')
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const SAMPLE_MATCH_HINTS = {
  refund: {
    period: ['within 14 days', '14 days of delivery'],
    receipt: ['order receipt', 'proof of purchase'],
    unused: ['items must be unused', 'original condition'],
    clearance: ['final sale'],
  },
  event: {
    hours: ['at least 48 hours', '48 hours before'],
    flexible: ['flexible-cancellation ticket'],
    checkin: ['checked in'],
  },
  software: {
    license: ['copy of the applicable software licence', 'copy of the applicable licence'],
    notice: ['required notice information'],
    modifications: ['changed source files', 'modified files are marked'],
  },
};

const STOP = new Set(
  (
    'a an the from with for and or of to must need required requires be is are was were as at by that this ' +
    'any include included original when within policy item items customers customer request ' +
    'order day days standard shall should may can will have has been remain remains thereof hereby such ' +
    'این آن از با برای و یا در به را که تا بر باید است هست بود شد شود ها های موارد مورد خود ' +
    'تان شان مان ات اش ام هستم هستید هستیم هستند کنم کنید کنیم باشد باشید باشند می شود نمیشود کنید کرد داده دهند ' +
    'bir bu ve veya ile için da de mi mı dir dır tur tür gibi olan olarak ya her herhangi şekilde dair ' +
    'ilişkin üzerine takdirde halde üzere karşı zorunda zorundadır olmalı olmalıdır gerekir gereklidir sahiptir yeterlidir sunuz sunuzudur dur durur'
  ).split(' ')
);

const DEMO_BOILERPLATE_RE =
  /solely for a software demonstration|illustrative only and does not replace|authored for this prototype/i;

const CUE_RULES = [
  {
    type: 'cross-reference',
    re: /\b(standard requirements? apply|standard rules? apply|other rules? apply|terms apply|additional terms|additional requirements|applicable law|policy addendum|terms and conditions|subject to (?:additional|company|store) (?:rules|terms|policy))\b|(?:مقررات استاندارد|شرایط عمومی|سایر ضوابط|قوانین جاری|طبق مقررات|genel şartlar|ek koşullar|standart kurallar|diğer hükümler)/iu,
  },
  {
    type: 'negation-exception',
    re: /\b(unless|except|excluding|excluded|not eligible|cannot|can not|not permitted|not allowed|not refundable|not returnable|not accepted|not valid|ineligible|disallowed|banned|denied|prohibited|forbidden|no refunds?|no returns?|no exchanges?|final sale|as-is|void|invalid|void if|void unless|invalid if|without|never|non-?refundable)\b|(?:مگر|به‌جز|به جز|جز در|نباید|نشده باشد|باز نشده|نمی‌?شود|امکان‌پذیر نیست|امکان پذیر نیست|عودت ندارد|بازگشت ندارد|مرجوع نمی‌?شود|بدون بازگشت|مجاز نیست|ممنوع|باطل|غیرمجاز|نامعتبر|فاقد اعتبار|رد می‌شود|بدون|هرگز|عدم|hariç|haricinde|olmadan|yasak|yasaktır|yapılamaz|edilemez|geçersiz|geçersizdir|değildir|mümkün değil|iade edilmez|iade alınmaz|kabul edilmez|uygun değildir)/iu,
  },
  {
    type: 'implicit-dependency',
    re: /\b(depends? on|contingent on|conditional on|subject to|provided that|only if|if and only if|valid only|permitted only|approved only|eligible only|as long as|precondition|prerequisite|mandatory|requires?|condition(?:s)? (?:for|of)|in order to|before approving|prior to approval)\b|(?:مشروط|منوط|فقط در صورت|تنها در صورت|تنها زمانی|تضمین|پلمب|به‌شرط|به شرط|در صورتی که|şartıyla|şartına|koşuluyla|koşuluna|bağlıdır)/iu,
  },
  {
    type: 'temporal-deadline',
    re: /\b(within \d+|at least \d+|no later than|prior to|before|valid until|expir(?:e|ed|y)|effective date|superseded|archived|outdated)\b|(?:حداقل|حداکثر|ظرف|مهلت|تا تاریخ|منقضی|قدیمی|تاریخ اعتبار|en geç|en az|en fazla|süresi içinde|son geçerlilik|süresi dolmuş)/iu,
  },
  {
    type: 'explicit-obligation',
    re: /\b(must|shall|required|need to|needs to|has to|have to|may only|is excluded|are excluded|is permitted only if)\b|(?:باید|الزامی|ضروری|لازم است|لازم می‌باشد|gerekir|gereklidir|gerekli|zorunlu|zorunludur|şarttır)/iu,
  },
];

const BAN_POLARITY_RE =
  /\b(no refunds?|no returns?|no exchanges?|prohibited|forbidden|void|banned|denied|never|cannot|can not|not eligible|not refundable|non-?refundable|not returnable|not permitted|not allowed|not accepted|not valid|ineligible|disallowed|excluded|without)\b|ممنوعیت|ممنوع|نباید|باطل|غیرمجاز|نامعتبر|مجاز نیست|عودت ندارد|بازگشت ندارد|نمی‌?شود|yasak|asla|geçersiz|yapılamaz|edilemez|iade edilmez|uygun değildir|mamalısınız|memelisiniz/iu;

const TERM_EXCLUSION_RE =
  /\b(not|no|never|without|except|exclude[sd]?|final\s*sale|prohibited|forbidden|non-?)\b|ممنوعیت|ممنوع|نباید|باطل|نباشد|نشده|نمی‌?شود|değil|yasak|asla|mamaktadır|memektedir/iu;

const STALE_YEAR_RE = /\b(201\d|202[0-3])\b|\b(superseded|expired|obsolete|archived|deprecated)\b|منقضی|قدیمی|منسوخ|süresi dolmuş|eski sürüm/iu;

const FA_NON_STRIP_Y = new Set(['برای', 'روی', 'سوی', 'وی', 'ولی', 'خیلی', 'هیچی', 'بسیاری', 'مدتی']);
const TR_NEG_SUFFIX_RE = /(?:meksizin|maksızın|sız|siz|suz|süz|maz|mez|mama|meme)$/i;
const TR_VERB_SUFFIXES = [
  'ılmamaktadır', 'ilmemektedir', 'mamalısınız', 'memelisiniz', 'mamaktadır', 'memektedir',
  'ilmektedir', 'ılmaktadır', 'mektedirler', 'maktadırlar', 'mektedir', 'maktadır',
  'ilmiştir', 'ılmıştır', 'ulmuştur', 'ülmüştür', 'miştir', 'mıştır',
  'ilmesi', 'ılması', 'ilmesine', 'ılmasına', 'mesine', 'masına', 'mesi', 'ması',
  'ıldığına', 'ildiğine', 'ulduğuna', 'üldüğüne', 'dığına', 'diğine',
  'ıldığı', 'ildiği', 'dığı', 'diği', 'tuğu', 'tüğü', 'mek', 'mak', 'yordu', 'yor',
];
const TR_NOUN_SUFFIXES = [
  'larından', 'lerinden', 'larına', 'lerine', 'larını', 'lerini', 'nızın', 'nizin', 'nuzun', 'nüzün', 'sından', 'sinden',
  'sınız', 'siniz', 'sunuz', 'sünüz', 'nızı', 'nizi', 'nuzu', 'nüzü', 'nız', 'niz', 'nuz', 'nüz',
  'ndan', 'nden', 'ında', 'inde', 'ına', 'ini', 'ını', 'unu', 'ünü',
  'nın', 'nin', 'nun', 'nün', 'dan', 'den', 'tan', 'ten',
  'ları', 'leri', 'lar', 'ler', 'si', 'sı', 'su', 'sü', 'ya', 'ye', 'da', 'de', 'ta', 'te', 'in', 'ın', 'un', 'ün',
  'lusunuz', 'lüsünüz', 'ludur', 'lüdür', 'ludur',
];
const EN_SUFFIXES = ['ations', 'ation', 'ments', 'ment', 'ings', 'ing', 'ies', 'ed', 'ly', 'es', 's'];

/**
 * Conservatively normalizes grammatical inflections across EN/TR/FA while preserving
 * negative polarity suffixes so prohibitions and permissions never collide.
 */
function canonicalStem(tok) {
  if (!tok) return tok;
  if (tok === 'شما' || tok === 'کاربر' || tok === 'kullanıcı' || tok === 'siz' || tok === 'kendiniz') {
    return '__actor_user__';
  }
  if (/^[\u0600-\u06ff]+$/.test(tok)) {
    if (/^(ن|نا|غیر)/.test(tok)) return tok;
    let w = tok;
    for (const suf of ['هایشان', 'تان', 'شان', 'مان', 'های', 'ها']) {
      if (w.endsWith(suf) && w.length - suf.length >= 4) {
        w = w.slice(0, -suf.length);
        break;
      }
    }
    if (w.endsWith('ی') && w.length >= 5 && !FA_NON_STRIP_Y.has(w)) {
      w = w.slice(0, -1);
    }
    return w;
  }
  if (/^[a-zçğıöşü]+$/i.test(tok) && !TR_NEG_SUFFIX_RE.test(tok)) {
    let w = tok;
    let changed = false;
    for (const suf of TR_VERB_SUFFIXES) {
      if (w.endsWith(suf) && w.length - suf.length >= 4) {
        w = w.slice(0, -suf.length);
        changed = true;
        break;
      }
    }
    if (!changed) {
      for (let pass = 0; pass < 2; pass += 1) {
        let matched = false;
        for (const suf of TR_NOUN_SUFFIXES) {
          if (w.endsWith(suf) && w.length - suf.length >= 4) {
            w = w.slice(0, -suf.length);
            matched = true;
            break;
          }
        }
        if (!matched) break;
      }
      if (w.length >= 8 && /[iıuü]$/.test(w)) {
        w = w.slice(0, -1);
      }
    }
    if (w === 'hakk') w = 'hak';
    if (/^[a-z]+$/.test(w) && w.length >= 5 && !/(?:ss|us|is)$/.test(w)) {
      for (const suf of EN_SUFFIXES) {
        if (w.endsWith(suf) && w.length - suf.length >= 4) {
          w = suf === 'ies' ? `${w.slice(0, -3)}y` : w.slice(0, -suf.length);
          break;
        }
      }
    }
    return w;
  }
  return tok;
}

const SAFE_HARBOR_CONDITIONAL_RE =
  /^(?<antecedent>.+?)\s+(?:takdirde|durumunda|halinde)\s+(?:meydana\s+gelen\s+)?değişiklik\s+ve\s+bozulmalardan\s+sorumlu\s+değildir[.!?]*$|^(?<antEn>.+?)\s+in\s+which\s+case\s+(?:the\s+)?(?:consumer|buyer|customer)\s+is\s+not\s+liable[^.!?\n]*[.!?]*$|^(?<antFa>.+?)\s+در\s+این\s+صورت\s+(?:کاربر|خریدار|مصرف[‌ ]کننده)\s+مسئول[^.!؟\n]*نیست[.!؟]*$/iu;

const COST_WAIVER_PHRASE_RE =
  /(?:ve\s+)?(?:herhangi\s+bir\s+)?(?:cezai\s+şart|masraf)\s+ödemeksizin\b|\bwithout\s+(?:any\s+)?(?:penalty|additional\s+fee)\b|بدون\s+(?:پرداخت\s+)?جریمه/giu;

const DATIVE_COUNTERPARTY_RE =
  /\b(?:satıcı\s+veya\s+sağlayıcıya(?:\s+ya\s+da\s+yetkilendirmiş\s+olduğu\s+kişiye)?|satıcıya|sağlayıcıya)\b/giu;

const EXCLUSIVE_RESTRICTION_RE =
  /\b(?:sadece|yalnızca|yalnız|orijinal\s+mağaza|mağazaya|şubeye|exclusively|only\s+to\s+(?:the\s+)?original)\b|فقط\s+به|انحصاراً/iu;

const BURDEN_DUTY_RE = /\b(?:ispat|yüküm(?:lü|lülüğü)?|burden\s+of\s+proof)\b|بر\s+عهده|بار\s+اثبات/iu;

function extractSafeHarborAntecedent(text) {
  const m = SAFE_HARBOR_CONDITIONAL_RE.exec(String(text || '').trim());
  if (!m) return null;
  return (m.groups?.antecedent || m.groups?.antEn || m.groups?.antFa || '').trim();
}

function stripBenignLegalModifiers(frag, termText, policyText) {
  let cleaned = String(frag || '');
  if (!/ceza|penalty|ücret|masraf|fee|جریمه|کارمزد/i.test(policyText || '')) {
    cleaned = cleaned.replace(COST_WAIVER_PHRASE_RE, ' ');
  }
  const hasDeliveryAction = /yönelt|gönder|iade|submit|send|return|ارسال/i.test(termText || '');
  if (hasDeliveryAction && !EXCLUSIVE_RESTRICTION_RE.test(cleaned) && !BURDEN_DUTY_RE.test(cleaned)) {
    cleaned = cleaned.replace(DATIVE_COUNTERPARTY_RE, ' ');
  }
  if (/işleyiş/i.test(termText || '') && /kullanım/i.test(termText || '') && /uygun/i.test(termText || '')) {
    cleaned = cleaned.replace(/\bteknik\s+özellik(?:lerine|leri)?\b/giu, ' ');
  }
  return cleaned;
}

const TR_ONES = { bir: 1, iki: 2, uc: 3, üç: 3, dort: 4, dört: 4, bes: 5, beş: 5, alti: 6, altı: 6, yedi: 7, sekiz: 8, dokuz: 9 };
const TR_TENS = { on: 10, yirmi: 20, otuz: 30, kirk: 40, kırk: 40, elli: 50, altmis: 60, altmış: 60 };
const EN_NUMS = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, fourteen: 14, fifteen: 15, thirty: 30 };
const FA_NUMS = { یک: 1, دو: 2, سه: 3, چهار: 4, پنج: 5, شش: 6, هفت: 7, هشت: 8, نه: 9, ده: 10, چهارده: 14, پانزده: 15, سی: 30 };

const TIME_EXPR_RE =
  /\b(?:(?<num>\d+)|(?<trTen>on|yirmi|otuz|kırk|elli|altmış)(?:\s+(?<trOne>bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz))?|(?<trSingle>bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz)|(?<enNum>one|two|three|four|five|six|seven|eight|nine|ten|fourteen|fifteen|thirty))\s*(?<unit>days?|hours?|months?|gün|saat|ay)\b|(?:(?<faD>\d+)|(?<faW>یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|چهارده|پانزده|سی))\s*(?<faUnit>روز|ساعت|ماه)/giu;

function extractTimeEntries(text) {
  const src = toAsciiDigits(text);
  const res = [];
  for (const m of src.matchAll(TIME_EXPR_RE)) {
    const g = m.groups || {};
    let n = null;
    if (g.num) n = g.num;
    else if (g.faD) n = g.faD;
    else if (g.trTen) n = String((TR_TENS[g.trTen.toLowerCase()] || 0) + (g.trOne ? TR_ONES[g.trOne.toLowerCase()] || 0 : 0));
    else if (g.trSingle) n = String(TR_ONES[g.trSingle.toLowerCase()]);
    else if (g.enNum) n = String(EN_NUMS[g.enNum.toLowerCase()]);
    else if (g.faW) n = String(FA_NUMS[g.faW]);
    const rawUnit = (g.unit || g.faUnit || '').toLowerCase();
    const unit = /^(day|days|روز|gün)$/.test(rawUnit) ? 'day' : /^(hour|hours|ساعت|saat)$/.test(rawUnit) ? 'hour' : 'month';
    if (n) res.push({ num: n, unit });
  }
  return res;
}

const CITATION_REF_RE = /\b(?:madde|md\.?|clause|article|sec(?:tion)?\.?|بند|ماده)\s*\d+(?:\s*\(\d+\))*/giu;

function extractNumbers(text) {
  const withoutCitations = String(text || '').replace(CITATION_REF_RE, ' ');
  const digits = (normalize(withoutCitations).match(/\b\d+(?:\.\d+)?\b/g) || []).filter((n) => !/^(?:19|20)\d{2}$/.test(n));
  const timeNums = extractTimeEntries(withoutCitations).map((x) => x.num);
  return [...new Set([...digits, ...timeNums])];
}

function numbersCompatible(fragNums, termNums) {
  if (!fragNums.length || !termNums.length) return true;
  const termSet = new Set(termNums);
  const fragSet = new Set(fragNums);
  return fragNums.every((n) => termSet.has(n)) && termNums.every((n) => fragSet.has(n));
}

function tokens(t) {
  return new Set(
    normalize(t)
      .split(' ')
      .filter((x) => x.length >= 2 && !STOP.has(x) && !/^\d+$/.test(x))
      .map(canonicalStem)
      .filter((x) => x.length >= 2 && !STOP.has(x))
  );
}

function overlapStats(fragment, termText) {
  const x = tokens(fragment);
  const y = tokens(termText);
  if (!x.size || !y.size) return { minRecall: 0, fragmentCoverage: 0, novelCount: x.size };
  let shared = 0;
  for (const tok of x) {
    if (y.has(tok)) shared += 1;
  }
  return {
    minRecall: shared / Math.min(x.size, y.size),
    fragmentCoverage: shared / x.size,
    novelCount: x.size - shared,
  };
}

function isHeadingOrNoise(trim, lineIndex) {
  if (DEMO_BOILERPLATE_RE.test(trim)) return true;
  // Never drop an actionable ban/obligation/deadline on line 1 as a document title.
  if (detectCueType(trim)) return false;
  if (lineIndex === 1 && /\/|\(fictional\)|policy|checklist|terms/i.test(trim) && !/[.؟!]$/.test(trim)) return true;
  const toks = tokens(trim);
  if (toks.size < 2) return true;
  return false;
}

function sentencePartsWithSpans(rawText) {
  const parts = [];
  const lineRe = /[^\r\n]*(?:\r?\n|$)/g;
  let lineNum = 0;
  for (const lineMatch of rawText.matchAll(lineRe)) {
    const rawLine = lineMatch[0];
    if (!rawLine) break;
    lineNum += 1;
    const lineStart = lineMatch.index;
    const lineContent = rawLine.replace(/\r?\n$/, '');
    if (!lineContent.trim()) continue;
    const sepRe = /(?<=[.!?؟;])\s+/gu;
    let cursor = 0;
    const pushSlice = (segStart, segEnd) => {
      const rawSeg = lineContent.slice(segStart, segEnd);
      const lead = rawSeg.match(/^\s*/)[0].length;
      const trail = rawSeg.match(/\s*$/)[0].length;
      const s = segStart + lead;
      const e = segEnd - trail;
      if (e > s) {
        const frag = lineContent.slice(s, e);
        parts.push({
          line: lineNum,
          fragment: frag,
          startOffset: lineStart + s,
          endOffset: lineStart + e,
        });
      }
    };
    for (const m of lineContent.matchAll(sepRe)) {
      pushSlice(cursor, m.index);
      cursor = m.index + m[0].length;
    }
    pushSlice(cursor, lineContent.length);
  }
  return parts;
}

function detectCueType(trim) {
  if (extractSafeHarborAntecedent(trim)) return 'implicit-dependency';
  for (const rule of CUE_RULES) {
    if (rule.re.test(trim)) return rule.type;
  }
  if (extractTimeEntries(trim).length > 0) return 'temporal-deadline';
  return null;
}

const COORD_SPLIT_RE =
  /\s+و\s+(?=(?:نباید|باید|می|نمی|شما|کاربر|اگر|در\s|مگر|یا|هیچ))|\s+ve\s+(?=(?:tüketici|mal|bildirim|cayma|bu|ek|ayrıca|satıcı|parola|kullanıcı|siz|kendi))|;\s+|,\s+(?=(?:and|or|unless|except|but|however|if)\b)|\s+and\s+(?=(?:must|shall|should|cannot|can not|buyers?|customers?|users?|all|no|never|requires?|you|the)\b)/giu;

function splitSubClausesWithSpans(fragment, baseStartOffset) {
  const subs = [];
  let cursor = 0;
  const pushSub = (s, e) => {
    const rawSub = fragment.slice(s, e);
    const lead = rawSub.match(/^\s*/)[0].length;
    const trail = rawSub.match(/\s*$/)[0].length;
    const cs = s + lead;
    const ce = e - trail;
    if (ce > cs) {
      subs.push({
        fragment: fragment.slice(cs, ce),
        startOffset: baseStartOffset + cs,
        endOffset: baseStartOffset + ce,
      });
    }
  };
  for (const m of fragment.matchAll(COORD_SPLIT_RE)) {
    pushSub(cursor, m.index);
    cursor = m.index + m[0].length;
  }
  pushSub(cursor, fragment.length);
  return subs;
}

function matchesSingleTermOrUnion(trim, terms, hintMap, policy) {
  const safeHarborAnt = extractSafeHarborAntecedent(trim);
  const effectiveTrim = safeHarborAnt || trim;
  const normTrim = normalize(effectiveTrim);
  const policyTitleAndTerms = [policy?.title, policy?.question, ...terms.map((t) => `${t.label} ${t.why || ''}`)].join(' ');
  const allPolicyTokens = new Set();
  for (const field of [policy?.title, policy?.question]) {
    for (const tok of tokens(field || '')) allPolicyTokens.add(tok);
  }
  for (const pt of terms) {
    for (const tok of tokens(`${pt.label} ${pt.why || ''}`)) allPolicyTokens.add(tok);
  }
  const hasPolicyToken = (tok) =>
    allPolicyTokens.has(tok) || (tok.endsWith('s') && tok.length > 3 && allPolicyTokens.has(tok.slice(0, -1)));
  const fragNums = extractNumbers(effectiveTrim);
  const fragIsBan = BAN_POLARITY_RE.test(effectiveTrim);

  for (const t of terms) {
    const hints = hintMap[t.id] || [];
    const termFull = `${t.label} ${t.why || ''}`;
    const termNums = extractNumbers(termFull);
    if (!numbersCompatible(fragNums, termNums)) continue;
    const termIsBan = TERM_EXCLUSION_RE.test(termFull);
    // Do not swallow a prohibition into a purely affirmative term, or an affirmative assertion ("is marked final sale") into a negated term.
    if (fragIsBan && !termIsBan) continue;
    if (!fragIsBan && termIsBan) {
      if (/\bnot\s+marked\b/i.test(termFull) && /\bfinal\s+sale\b/i.test(effectiveTrim)) continue;
      if (/ممنوع|نباید|نمی‌?شود|هیچ/.test(termFull) && !BAN_POLARITY_RE.test(effectiveTrim)) continue;
    }

    const roleCleanedTrim = stripBenignLegalModifiers(effectiveTrim, termFull, policyTitleAndTerms);
    const cleanedTokens = [...tokens(roleCleanedTrim)];
    const outOfPolicyNovel = cleanedTokens.filter((tok) => !hasPolicyToken(tok)).length;

    const stats = overlapStats(roleCleanedTrim, termFull);
    // Exact sample hint counts only when at most 2 novel tokens appear beyond the policy scope.
    const hintHit = hints.some((v) => normTrim.includes(normalize(v)));
    if (hintHit && Math.min(stats.novelCount, outOfPolicyNovel) <= 2) return true;
    // Direct semantic overlap only counts when fragment itself adds < 2 unrepresented content tokens.
    if (stats.minRecall >= 0.6 && stats.fragmentCoverage >= 0.55 && Math.min(stats.novelCount, outOfPolicyNovel) <= 1) {
      return true;
    }
  }
  return false;
}

function matchesExistingTerm(trim, terms, hintMap, policy) {
  return matchesSingleTermOrUnion(trim, terms, hintMap, policy);
}

function detectConflictSignals(candidates) {
  const signals = [];
  const positives = [];
  const negatives = [];
  for (const c of candidates) {
    const low = c.label.toLowerCase();
    const isConditionalException = /\b(unless|except|only if|provided that)\b|مگر|به‌جز|به جز|فقط در صورت|şartıyla|haricinde/iu.test(low);
    if (
      !isConditionalException &&
      /\b(never refundable|not refundable|non-?refundable|no refunds?|no returns?|not eligible|ineligible|prohibited|forbidden|void|not permitted|not allowed)\b|غیرقابل بازگشت|عودت ندارد|بازگشت ندارد|ممنوع|باطل|غیرمجاز|iade edilmez|yasak|geçersiz|uygun değildir/iu.test(
        low
      )
    ) {
      negatives.push(c);
    } else if (
      /\b(refundable|eligible for|permitted|is approved|are approved|accepted|free cancellation)\b|بازپرداخت|قابل استرداد|مجاز است|تایید می‌شود|تأیید می‌شود|iade|kabul edilir|uygundur|geçerlidir/iu.test(
        low
      )
    ) {
      positives.push(c);
    }
  }
  if (positives.length && negatives.length) {
    signals.push({
      lineA: positives[0].line,
      lineB: negatives[0].line,
      summary: `Lines ${positives[0].line} and ${negatives[0].line} contain opposing eligibility/refund statements.`,
    });
  }

  // Detect conflicting numeric thresholds on overlapping topics (e.g., within 14 days vs within 7 days, digit or spelled).
  const timeEntries = [];
  for (const c of candidates) {
    for (const te of extractTimeEntries(c.label)) {
      timeEntries.push({ cand: c, num: te.num, unit: te.unit, toks: tokens(c.label) });
    }
  }
  for (let i = 0; i < timeEntries.length; i++) {
    for (let j = i + 1; j < timeEntries.length; j++) {
      const a = timeEntries[i];
      const b = timeEntries[j];
      if (a.cand.line === b.cand.line || a.unit !== b.unit || a.num === b.num) continue;
      const shared = [...a.toks].some((t) => b.toks.has(t));
      if (shared || (a.cand.matchedExisting && b.cand.cueType === 'temporal-deadline')) {
        signals.push({
          lineA: a.cand.line,
          lineB: b.cand.line,
          summary: `Lines ${a.cand.line} (${a.num} ${a.unit}s) and ${b.cand.line} (${b.num} ${b.unit}s) state competing time limits.`,
        });
        return signals;
      }
    }
  }
  return signals;
}

export function scanDocumentForConditions(text, policy, { maxCandidates = 12, includeUnclassified = false } = {}) {
  const res = analyzeSourceDocument(text, policy, { maxCandidates, includeUnclassified });
  return res.candidates;
}

export function analyzeSourceDocument(text, policy, { maxCandidates = 12, includeUnclassified = true } = {}) {
  const terms = Array.isArray(policy?.terms) ? policy.terms : [];
  const rawText = String(text || '');
  const truncatedByCharLimit = rawText.length > 30000;
  const scannedText = rawText.slice(0, 30000);
  const parts = sentencePartsWithSpans(scannedText);
  const hintMap = SAMPLE_MATCH_HINTS[policy?.id] || {};

  const out = [];
  const seen = new Set();
  const uncertaintyReasons = [];
  let truncatedCount = 0;
  let staleSignals = 0;
  let externalReferenceCount = 0;
  let unclassifiedCount = 0;

  if (truncatedByCharLimit) {
    uncertaintyReasons.push('Source document exceeded 30,000-character scan cap; remaining text was not analyzed.');
  }

  const pushCandidate = (item) => {
    if (out.length < maxCandidates) {
      out.push(item);
    } else if (!item.matchedExisting) {
      truncatedCount += 1;
    }
  };

  for (const { line, fragment, startOffset, endOffset } of parts) {
    const bulletMatch = fragment.match(/^\s*(?:[-*•]|[\d\u06f0-\u06f9\u0660-\u0669]+[.)])\s*/);
    const bulletOffset = bulletMatch ? bulletMatch[0].length : 0;
    const trim = fragment.slice(bulletOffset).trim();
    const trimStartOffset = startOffset + bulletOffset;
    const trimEndOffset = trimStartOffset + trim.length;

    // A long paragraph is NOT proof that it contains no additional conditions.
    // Record every skipped overlong fragment so a positive decision fails closed.
    if (trim.length > 550) {
      truncatedCount += 1;
      uncertaintyReasons.push(`Line ${line} exceeds the 550-character clause scan limit; split or review the original paragraph before attesting coverage.`);
      continue;
    }
    if (!trim) continue;
    if (isHeadingOrNoise(trim, line)) {
      if (STALE_YEAR_RE.test(trim)) {
        staleSignals += 1;
        uncertaintyReasons.push(`Line ${line} references an older/archived/expired policy marker ("${trim.slice(0, 80)}").`);
      }
      continue;
    }

    const key = normalize(trim);
    if (!key || seen.has(key)) continue;

    if (STALE_YEAR_RE.test(trim)) {
      staleSignals += 1;
    }

    const wholeCueType = detectCueType(trim);
    const wholeMatched = wholeCueType === 'cross-reference' ? false : matchesExistingTerm(trim, terms, hintMap, policy);

    let units = null;
    if (!wholeMatched && wholeCueType !== 'cross-reference') {
      const subClauses = splitSubClausesWithSpans(trim, trimStartOffset);
      if (subClauses.length > 1) {
        const evaluated = subClauses.map((sub) => {
          const subCue = detectCueType(sub.fragment) || wholeCueType;
          const subMatch = subCue === 'cross-reference' ? false : matchesExistingTerm(sub.fragment, terms, hintMap, policy);
          return { ...sub, cueType: subCue, matched: subMatch };
        });
        const substantiveSubs = evaluated.filter((s) => tokens(s.fragment).size >= 2 || s.cueType);
        if (substantiveSubs.length > 1 && substantiveSubs.every((s) => s.matched)) {
          units = [
            {
              trim,
              quote: fragment,
              startOffset,
              endOffset: startOffset + fragment.length,
              cueType: wholeCueType,
              matchedExisting: true,
            },
          ];
        } else if (substantiveSubs.some((s) => s.matched) && substantiveSubs.some((s) => !s.matched)) {
          units = substantiveSubs.map((s) => ({
            trim: s.fragment,
            quote: s.fragment,
            startOffset: s.startOffset,
            endOffset: s.endOffset,
            cueType: s.cueType,
            matchedExisting: s.matched,
          }));
        }
      }
    }

    if (!units) {
      units = [
        {
          trim,
          quote: fragment,
          startOffset,
          endOffset: startOffset + fragment.length,
          cueType: wholeCueType,
          matchedExisting: wholeMatched,
        },
      ];
    }

    seen.add(key);
    for (const u of units) {
      const subKey = normalize(u.trim);
      if (!subKey) continue;
      if (u.cueType) {
        if (u.cueType === 'cross-reference') externalReferenceCount += 1;
        pushCandidate({
          id: null,
          label: u.trim,
          reason:
            u.cueType === 'cross-reference'
              ? `Line ${line} references external/standard rules that are not enumerated here; verify before approving.`
              : `The supplied source document states this (${u.cueType}) on line ${line}; review applicability and whether this is already covered.`,
          origin: 'document-scan',
          cueType: u.cueType,
          line,
          startOffset: u.startOffset,
          endOffset: u.endOffset,
          quote: u.quote,
          matchedExisting: u.cueType === 'cross-reference' ? false : u.matchedExisting,
        });
        continue;
      }

      // Short clauses such as "No refunds." still require review.
      // Keep substantive 2+ token short fragments instead of silently discarding them.
      if (!u.matchedExisting && includeUnclassified && tokens(u.trim).size >= (u.trim.length < 24 ? 2 : 4)) {
        unclassifiedCount += 1;
        pushCandidate({
          id: null,
          label: u.trim,
          reason: `Unclassified substantive clause on line ${line}; scanner cannot exclude a hidden requirement — human review required.`,
          origin: 'uncertain-clause',
          cueType: 'unclassified-substantive',
          line,
          startOffset: u.startOffset,
          endOffset: u.endOffset,
          quote: u.quote,
          matchedExisting: false,
        });
      }
    }
  }

  const conflictSignals = detectConflictSignals(out);
  if (truncatedCount > 0) {
    uncertaintyReasons.push(`${truncatedCount} additional clause(s) exceeded the ${maxCandidates}-candidate scan limit.`);
  }
  if (externalReferenceCount > 0) {
    uncertaintyReasons.push(`${externalReferenceCount} external rule cross-reference(s) detected.`);
  }
  if (conflictSignals.length > 0) {
    uncertaintyReasons.push(conflictSignals[0].summary);
  }
  if (staleSignals > 0 && !uncertaintyReasons.some((r) => r.includes('older/archived/expired'))) {
    uncertaintyReasons.push('Source mentions historical/expired validity markers; confirm revision is current.');
  }

  return {
    candidates: out,
    novelCount: out.filter((x) => !x.matchedExisting).length,
    truncatedByCharLimit,
    truncatedCount,
    externalReferenceCount,
    unclassifiedCount,
    staleSignals,
    conflictSignals,
    coverageUncertain:
      truncatedByCharLimit ||
      truncatedCount > 0 ||
      conflictSignals.length > 0 ||
      externalReferenceCount > 0 ||
      unclassifiedCount > 0 ||
      staleSignals > 0 ||
      out.some((x) => !x.matchedExisting && x.cueType === 'negation-exception'),
    uncertaintyReasons,
  };
}

export function validateSourceQuote(suggestion, source) {
  const q = String(suggestion?.quote || '').trim();
  if (!q) return { found: false, reason: 'No exact source quote' };
  const whole = String(source || '');
  const index = whole.indexOf(q);
  return index >= 0 ? { found: true, offset: index } : { found: false, reason: 'Proposed quote not in supplied source' };
}
