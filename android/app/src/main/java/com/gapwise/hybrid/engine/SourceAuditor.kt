package com.gapwise.hybrid.engine

import kotlin.math.min

/**
 * Deterministic source auditor mirroring web/source-audit.mjs.
 * Strictly an untrusted candidate extractor — never auto-approves requirements.
 */
object SourceAuditor {
    private val DIACRITICS_RE = Regex("[\\u064b-\\u065f\\u0670\\u06d6-\\u06ed]")
    private val NON_ALNUM_SPACE_RE = Regex("[^\\p{L}\\p{N}\\s]")
    private val MULTI_SPACE_RE = Regex("\\s+")
    private val SENTENCE_SPLIT_RE = Regex("(?<=[.!?؟;])\\s+")
    private val BULLET_PREFIX_RE = Regex("^\\s*(?:[-*•]|[\\d\\u06f0-\\u06f9\\u0660-\\u0669]+[.)])\\s*")
    private val NUMBER_RE = Regex("\\b\\d+(?:\\.\\d+)?\\b")
    private val YEAR_RE = Regex("^(?:19|20)\\d{2}$")

    private val SAMPLE_MATCH_HINTS: Map<String, Map<String, List<String>>> = mapOf(
        "refund" to mapOf(
            "period" to listOf("within 14 days", "14 days of delivery"),
            "receipt" to listOf("order receipt", "proof of purchase"),
            "unused" to listOf("items must be unused", "original condition"),
            "clearance" to listOf("final sale")
        ),
        "event" to mapOf(
            "hours" to listOf("at least 48 hours", "48 hours before"),
            "flexible" to listOf("flexible-cancellation ticket"),
            "checkin" to listOf("checked in")
        ),
        "software" to mapOf(
            "license" to listOf("copy of the applicable software licence", "copy of the applicable licence"),
            "notice" to listOf("required notice information"),
            "modifications" to listOf("changed source files", "modified files are marked")
        )
    )

    private val STOP: Set<String> = (
        "a an the from with for and or of to must need required requires be is are was were as at by that this " +
            "any include included original when within policy item items customers customer request " +
            "order day days standard shall should may can will have has been remain remains thereof hereby such " +
            "این آن از با برای و یا در به را که تا بر باید است هست بود شد شود ها های موارد مورد خود " +
            "تان شان مان ات اش ام هستم هستید هستیم هستند کنم کنید کنیم باشد باشید باشند می شود نمیشود کنید کرد داده دهند " +
            "bir bu ve veya ile için da de mi mı dir dır tur tür gibi olan olarak ya her herhangi şekilde dair " +
            "ilişkin üzerine takdirde halde üzere karşı zorunda zorundadır olmalı olmalıdır gerekir gereklidir sahiptir yeterlidir sunuz sunuzudur dur durur"
        ).split(" ").toSet()

    private val FA_NON_STRIP_Y = setOf("برای", "روی", "سوی", "وی", "ولی", "خیلی", "هیچی", "بسیاری", "مدتی")
    private val FA_NEG_PREFIX_RE = Regex("^(ن|نا|غیر)")
    private val FA_SCRIPT_RE = Regex("^[\\u0600-\\u06ff]+$")
    private val TR_ALPHA_RE = Regex("^[a-zçğıöşü]+$", RegexOption.IGNORE_CASE)
    private val TR_NEG_SUFFIX_RE = Regex("(?:meksizin|maksızın|sız|siz|suz|süz|maz|mez|mama|meme)$", RegexOption.IGNORE_CASE)
    private val EN_ALPHA_RE = Regex("^[a-z]+$")
    private val EN_SS_RE = Regex("(?:ss|us|is)$")
    private val TR_VERB_SUFFIXES = listOf(
        "ılmamaktadır", "ilmemektedir", "mamalısınız", "memelisiniz", "mamaktadır", "memektedir",
        "ilmektedir", "ılmaktadır", "mektedirler", "maktadırlar", "mektedir", "maktadır",
        "ilmiştir", "ılmıştır", "ulmuştur", "ülmüştür", "miştir", "mıştır",
        "ilmesi", "ılması", "ilmesine", "ılmasına", "mesine", "masına", "mesi", "ması",
        "ıldığına", "ildiğine", "ulduğuna", "üldüğüne", "dığına", "diğine",
        "ıldığı", "ildiği", "dığı", "diği", "tuğu", "tüğü", "mek", "mak", "yordu", "yor"
    )
    private val TR_NOUN_SUFFIXES = listOf(
        "larından", "lerinden", "larına", "lerine", "larını", "lerini", "nızın", "nizin", "nuzun", "nüzün", "sından", "sinden",
        "sınız", "siniz", "sunuz", "sünüz", "nızı", "nizi", "nuzu", "nüzü", "nız", "niz", "nuz", "nüz",
        "ndan", "nden", "ında", "inde", "ına", "ini", "ını", "unu", "ünü",
        "nın", "nin", "nun", "nün", "dan", "den", "tan", "ten",
        "ları", "leri", "lar", "ler", "si", "sı", "su", "sü", "ya", "ye", "da", "de", "ta", "te", "in", "ın", "un", "ün",
        "lusunuz", "lüsünüz", "ludur", "lüdür"
    )
    private val EN_SUFFIXES = listOf("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ed", "ly", "es", "s")
    private val SAFE_HARBOR_CONDITIONAL_RE = Regex(
        "^(?<antecedent>.+?)\\s+(?:takdirde|durumunda|halinde)\\s+(?:meydana\\s+gelen\\s+)?değişiklik\\s+ve\\s+bozulmalardan\\s+sorumlu\\s+değildir[.!?]*$" +
            "|^(?<antEn>.+?)\\s+in\\s+which\\s+case\\s+(?:the\\s+)?(?:consumer|buyer|customer)\\s+is\\s+not\\s+liable[^.!?\\n]*[.!?]*$" +
            "|^(?<antFa>.+?)\\s+در\\s+این\\s+صورت\\s+(?:کاربر|خریدار|مصرف[‌ ]کننده)\\s+مسئول[^.!؟\\n]*نیست[.!؟]*$",
        setOf(RegexOption.IGNORE_CASE)
    )
    private val COST_WAIVER_PHRASE_RE = Regex(
        "(?:ve\\s+)?(?:herhangi\\s+bir\\s+)?(?:cezai\\s+şart|masraf)\\s+ödemeksizin\\b|\\bwithout\\s+(?:any\\s+)?(?:penalty|additional\\s+fee)\\b|بدون\\s+(?:پرداخت\\s+)?جریمه",
        setOf(RegexOption.IGNORE_CASE)
    )
    private val DATIVE_COUNTERPARTY_RE = Regex(
        "\\b(?:satıcı\\s+veya\\s+sağlayıcıya(?:\\s+ya\\s+da\\s+yetkilendirmiş\\s+olduğu\\s+kişiye)?|satıcıya|sağlayıcıya)\\b",
        setOf(RegexOption.IGNORE_CASE)
    )
    private val EXCLUSIVE_RESTRICTION_RE = Regex(
        "\\b(?:sadece|yalnızca|yalnız|orijinal\\s+mağaza|mağazaya|şubeye|exclusively|only\\s+to\\s+(?:the\\s+)?original)\\b|فقط\\s+به|انحصاراً",
        setOf(RegexOption.IGNORE_CASE)
    )
    private val BURDEN_DUTY_RE = Regex(
        "\\b(?:ispat|yüküm(?:lü|lülüğü)?|burden\\s+of\\s+proof)\\b|بر\\s+عهده|بار\\s+اثبات",
        setOf(RegexOption.IGNORE_CASE)
    )
    private val COORD_SPLIT_RE = Regex(
        "\\s+و\\s+(?=(?:نباید|باید|می|نمی|شما|کاربر|اگر|در\\s|مگر|یا|هیچ))" +
            "|\\s+ve\\s+(?=(?:tüketici|mal|bildirim|cayma|bu|ek|ayrıca|satıcı|parola|kullanıcı|siz|kendi))" +
            "|;\\s+" +
            "|,\\s+(?=(?:and|or|unless|except|but|however|if)\\b)" +
            "|\\s+and\\s+(?=(?:must|shall|should|cannot|can not|buyers?|customers?|users?|all|no|never|requires?|you|the)\\b)",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val DEMO_BOILERPLATE_RE = Regex(
        "solely for a software demonstration|illustrative only and does not replace|authored for this prototype",
        RegexOption.IGNORE_CASE
    )

    private data class CueRule(val type: String, val regex: Regex)

    private val CUE_RULES: List<CueRule> = listOf(
        CueRule(
            "cross-reference",
            Regex(
                "\\b(standard requirements? apply|standard rules? apply|other rules? apply|terms apply|additional terms|additional requirements|applicable law|policy addendum|terms and conditions|subject to (?:additional|company|store) (?:rules|terms|policy))\\b|(?:مقررات استاندارد|شرایط عمومی|سایر ضوابط|قوانین جاری|طبق مقررات|genel şartlar|ek koşullar|standart kurallar|diğer hükümler)",
                setOf(RegexOption.IGNORE_CASE)
            )
        ),
        CueRule(
            "negation-exception",
            Regex(
                "\\b(unless|except|excluding|excluded|not eligible|cannot|can not|not permitted|not allowed|not refundable|not returnable|not accepted|not valid|ineligible|disallowed|banned|denied|prohibited|forbidden|no refunds?|no returns?|no exchanges?|final sale|as-is|void|invalid|void if|void unless|invalid if|without|never|non-?refundable)\\b|(?:مگر|به‌جز|به جز|جز در|نباید|نشده باشد|باز نشده|نمی‌?شود|امکان‌پذیر نیست|امکان پذیر نیست|عودت ندارد|بازگشت ندارد|مرجوع نمی‌?شود|بدون بازگشت|مجاز نیست|ممنوع|باطل|غیرمجاز|نامعتبر|فاقد اعتبار|رد می‌شود|بدون|هرگز|عدم|hariç|haricinde|olmadan|yasak|yasaktır|yapılamaz|edilemez|geçersiz|geçersizdir|değildir|mümkün değil|iade edilmez|iade alınmaz|kabul edilmez|uygun değildir)",
                setOf(RegexOption.IGNORE_CASE)
            )
        ),
        CueRule(
            "implicit-dependency",
            Regex(
                "\\b(depends? on|contingent on|conditional on|subject to|provided that|only if|if and only if|valid only|permitted only|approved only|eligible only|as long as|precondition|prerequisite|mandatory|requires?|condition(?:s)? (?:for|of)|in order to|before approving|prior to approval)\\b|(?:مشروط|منوط|فقط در صورت|تنها در صورت|تنها زمانی|تضمین|پلمب|به‌شرط|به شرط|در صورتی که|şartıyla|şartına|koşuluyla|koşuluna|bağlıdır)",
                setOf(RegexOption.IGNORE_CASE)
            )
        ),
        CueRule(
            "temporal-deadline",
            Regex(
                "\\b(within \\d+|at least \\d+|no later than|prior to|before|valid until|expir(?:e|ed|y)|effective date|superseded|archived|outdated)\\b|(?:حداقل|حداکثر|ظرف|مهلت|تا تاریخ|منقضی|قدیمی|تاریخ اعتبار|en geç|en az|en fazla|süresi içinde|son geçerlilik|süresi dolmuş)",
                setOf(RegexOption.IGNORE_CASE)
            )
        ),
        CueRule(
            "explicit-obligation",
            Regex(
                "\\b(must|shall|required|need to|needs to|has to|have to|may only|is excluded|are excluded|is permitted only if)\\b|(?:باید|الزامی|ضروری|لازم است|لازم می‌باشد|gerekir|gereklidir|gerekli|zorunlu|zorunludur|şarttır)",
                setOf(RegexOption.IGNORE_CASE)
            )
        )
    )

    private val BAN_POLARITY_RE = Regex(
        "\\b(no refunds?|no returns?|no exchanges?|prohibited|forbidden|void|banned|denied|never|cannot|can not|not eligible|not refundable|non-?refundable|not returnable|not permitted|not allowed|not accepted|not valid|ineligible|disallowed|excluded|without)\\b|ممنوعیت|ممنوع|نباید|باطل|غیرمجاز|نامعتبر|مجاز نیست|عودت ندارد|بازگشت ندارد|نمی‌?شود|yasak|asla|geçersiz|yapılamaz|edilemez|iade edilmez|uygun değildir|mamalısınız|memelisiniz",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val TERM_EXCLUSION_RE = Regex(
        "\\b(not|no|never|without|except|exclude[sd]?|final\\s*sale|prohibited|forbidden|non-?)\\b|ممنوعیت|ممنوع|نباید|باطل|نباشد|نشده|نمی‌?شود|değil|yasak|asla|mamaktadır|memektedir",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val STALE_YEAR_RE = Regex(
        "\\b(201\\d|202[0-3])\\b|\\b(superseded|expired|obsolete|archived|deprecated)\\b|منقضی|قدیمی|منسوخ|süresi dolmuş|eski sürüm",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val HEADING_LINE1_RE = Regex("/|\\(fictional\\)|policy|checklist|terms", RegexOption.IGNORE_CASE)
    private val TERMINAL_PUNCT_RE = Regex("[.؟!]$")

    private val CONFLICT_CONDITIONAL_RE = Regex(
        "\\b(unless|except|only if|provided that)\\b|مگر|به‌جز|به جز|فقط در صورت|şartıyla|haricinde",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val NEG_CONFLICT_RE = Regex(
        "\\b(never refundable|not refundable|non-?refundable|no refunds?|no returns?|not eligible|ineligible|prohibited|forbidden|void|not permitted|not allowed)\\b|غیرقابل بازگشت|عودت ندارد|بازگشت ندارد|ممنوع|باطل|غیرمجاز|iade edilmez|yasak|geçersiz|uygun değildir",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val POS_CONFLICT_RE = Regex(
        "\\b(refundable|eligible for|permitted|is approved|are approved|accepted|free cancellation)\\b|بازپرداخت|قابل استرداد|مجاز است|تایید می‌شود|تأیید می‌شود|iade|kabul edilir|uygundur|geçerlidir",
        setOf(RegexOption.IGNORE_CASE)
    )

    private val TIME_THRESHOLD_RE = Regex(
        "\\b(\\d+)\\s*(days?|hours?|months?|روز|ساعت|ماه|gün|saat|ay)\\b",
        setOf(RegexOption.IGNORE_CASE)
    )

    private fun toAsciiDigits(input: String): String {
        val sb = StringBuilder(input.length)
        for (ch in input) {
            when (ch) {
                in '\u06f0'..'\u06f9' -> sb.append(('0'.code + (ch.code - 0x06f0)).toChar())
                in '\u0660'..'\u0669' -> sb.append(('0'.code + (ch.code - 0x0660)).toChar())
                else -> sb.append(ch)
            }
        }
        return sb.toString()
    }

    fun normalize(input: String?): String {
        val raw = toAsciiDigits(input ?: "")
            .replace("\u064a", "\u06cc")
            .replace("\u0649", "\u06cc")
            .replace("\u0643", "\u06a9")
            .replace("\u200c", " ")
            .replace("İ", "i")
            .replace(Regex("I(?=[a-zçğıöşü])"), "ı")
        return DIACRITICS_RE.replace(raw, "")
            .lowercase()
            .replace('’', '\'')
            .replace('‘', '\'')
            .let { NON_ALNUM_SPACE_RE.replace(it, " ") }
            .let { MULTI_SPACE_RE.replace(it, " ") }
            .trim()
    }

    private fun canonicalStem(tok: String): String {
        if (tok.isEmpty()) return tok
        if (tok == "شما" || tok == "کاربر" || tok == "kullanıcı" || tok == "siz" || tok == "kendiniz") {
            return "__actor_user__"
        }
        if (FA_SCRIPT_RE.matches(tok)) {
            if (FA_NEG_PREFIX_RE.containsMatchIn(tok)) return tok
            var w = tok
            for (suf in listOf("هایشان", "تان", "شان", "مان", "های", "ها")) {
                if (w.endsWith(suf) && w.length - suf.length >= 4) {
                    w = w.dropLast(suf.length)
                    break
                }
            }
            if (w.endsWith("ی") && w.length >= 5 && w !in FA_NON_STRIP_Y) {
                w = w.dropLast(1)
            }
            return w
        }
        if (TR_ALPHA_RE.matches(tok) && !TR_NEG_SUFFIX_RE.containsMatchIn(tok)) {
            var w = tok
            var changed = false
            for (suf in TR_VERB_SUFFIXES) {
                if (w.endsWith(suf) && w.length - suf.length >= 4) {
                    w = w.dropLast(suf.length)
                    changed = true
                    break
                }
            }
            if (!changed) {
                for (pass in 0 until 2) {
                    var matched = false
                    for (suf in TR_NOUN_SUFFIXES) {
                        if (w.endsWith(suf) && w.length - suf.length >= 4) {
                            w = w.dropLast(suf.length)
                            matched = true
                            break
                        }
                    }
                    if (!matched) break
                }
                if (w.length >= 8 && w.last() in charArrayOf('i', 'ı', 'u', 'ü')) {
                    w = w.dropLast(1)
                }
            }
            if (w == "hakk") w = "hak"
            if (EN_ALPHA_RE.matches(w) && w.length >= 5 && !EN_SS_RE.containsMatchIn(w)) {
                for (suf in EN_SUFFIXES) {
                    if (w.endsWith(suf) && w.length - suf.length >= 4) {
                        w = if (suf == "ies") "${w.dropLast(3)}y" else w.dropLast(suf.length)
                        break
                    }
                }
            }
            return w
        }
        return tok
    }

    private fun tokens(t: String): Set<String> = normalize(t)
        .split(" ")
        .filter { it.length >= 2 && !STOP.contains(it) && !it.all(Char::isDigit) }
        .map { canonicalStem(it) }
        .filter { it.length >= 2 && !STOP.contains(it) }
        .toSet()

    private fun extractSafeHarborAntecedent(text: String): String? {
        val m = SAFE_HARBOR_CONDITIONAL_RE.find(text.trim()) ?: return null
        return listOf("antecedent", "antEn", "antFa")
            .firstNotNullOfOrNull { name -> runCatching { m.groups[name]?.value }.getOrNull() }
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
    }

    private fun stripBenignLegalModifiers(frag: String, termText: String, policyText: String): String {
        var cleaned = frag
        if (!Regex("ceza|penalty|ücret|masraf|fee|جریمه|کارمزد", RegexOption.IGNORE_CASE).containsMatchIn(policyText)) {
            cleaned = COST_WAIVER_PHRASE_RE.replace(cleaned, " ")
        }
        val hasDeliveryAction = Regex("yönelt|gönder|iade|submit|send|return|ارسال", RegexOption.IGNORE_CASE).containsMatchIn(termText)
        if (hasDeliveryAction && !EXCLUSIVE_RESTRICTION_RE.containsMatchIn(cleaned) && !BURDEN_DUTY_RE.containsMatchIn(cleaned)) {
            cleaned = DATIVE_COUNTERPARTY_RE.replace(cleaned, " ")
        }
        if (Regex("işleyiş", RegexOption.IGNORE_CASE).containsMatchIn(termText) &&
            Regex("kullanım", RegexOption.IGNORE_CASE).containsMatchIn(termText) &&
            Regex("uygun", RegexOption.IGNORE_CASE).containsMatchIn(termText)
        ) {
            cleaned = Regex("\\bteknik\\s+özellik(?:lerine|leri)?\\b", RegexOption.IGNORE_CASE).replace(cleaned, " ")
        }
        return cleaned
    }

    private data class SpanFragment(val line: Int, val fragment: String, val startOffset: Int, val endOffset: Int)
    private data class SubSpan(val fragment: String, val startOffset: Int, val endOffset: Int)

    private fun sentencePartsWithSpans(rawText: String): List<SpanFragment> {
        val parts = mutableListOf<SpanFragment>()
        val lineRe = Regex("[^\\r\\n]*(?:\\r?\\n|$)")
        var lineNum = 0
        for (lineMatch in lineRe.findAll(rawText)) {
            val rawLine = lineMatch.value
            if (rawLine.isEmpty()) break
            lineNum += 1
            val lineStart = lineMatch.range.first
            val lineContent = rawLine.removeSuffix("\n").removeSuffix("\r")
            if (lineContent.isBlank()) continue
            var cursor = 0
            fun pushSlice(segStart: Int, segEnd: Int) {
                if (segEnd <= segStart) return
                val rawSeg = lineContent.substring(segStart, segEnd)
                val lead = rawSeg.indexOfFirst { !it.isWhitespace() }.let { if (it < 0) rawSeg.length else it }
                val trail = rawSeg.reversed().indexOfFirst { !it.isWhitespace() }.let { if (it < 0) rawSeg.length else it }
                val s = segStart + lead
                val e = segEnd - trail
                if (e > s) {
                    parts.add(SpanFragment(lineNum, lineContent.substring(s, e), lineStart + s, lineStart + e))
                }
            }
            for (m in SENTENCE_SPLIT_RE.findAll(lineContent)) {
                pushSlice(cursor, m.range.first)
                cursor = m.range.last + 1
            }
            pushSlice(cursor, lineContent.length)
        }
        return parts
    }

    private fun splitSubClausesWithSpans(fragment: String, baseStartOffset: Int): List<SubSpan> {
        val subs = mutableListOf<SubSpan>()
        var cursor = 0
        fun pushSub(s: Int, e: Int) {
            if (e <= s) return
            val rawSub = fragment.substring(s, e)
            val lead = rawSub.indexOfFirst { !it.isWhitespace() }.let { if (it < 0) rawSub.length else it }
            val trail = rawSub.reversed().indexOfFirst { !it.isWhitespace() }.let { if (it < 0) rawSub.length else it }
            val cs = s + lead
            val ce = e - trail
            if (ce > cs) {
                subs.add(SubSpan(fragment.substring(cs, ce), baseStartOffset + cs, baseStartOffset + ce))
            }
        }
        for (m in COORD_SPLIT_RE.findAll(fragment)) {
            pushSub(cursor, m.range.first)
            cursor = m.range.last + 1
        }
        pushSub(cursor, fragment.length)
        return subs
    }

    private val TR_ONES = mapOf("bir" to 1, "iki" to 2, "uc" to 3, "üç" to 3, "dort" to 4, "dört" to 4, "bes" to 5, "beş" to 5, "alti" to 6, "altı" to 6, "yedi" to 7, "sekiz" to 8, "dokuz" to 9)
    private val TR_TENS = mapOf("on" to 10, "yirmi" to 20, "otuz" to 30, "kirk" to 40, "kırk" to 40, "elli" to 50, "altmis" to 60, "altmış" to 60)
    private val EN_NUMS = mapOf("one" to 1, "two" to 2, "three" to 3, "four" to 4, "five" to 5, "six" to 6, "seven" to 7, "eight" to 8, "nine" to 9, "ten" to 10, "fourteen" to 14, "fifteen" to 15, "thirty" to 30)
    private val FA_NUMS = mapOf("یک" to 1, "دو" to 2, "سه" to 3, "چهار" to 4, "پنج" to 5, "شش" to 6, "هفت" to 7, "هشت" to 8, "نه" to 9, "ده" to 10, "چهارده" to 14, "پانزده" to 15, "سی" to 30)
    private val TIME_EXPR_RE = Regex(
        "\\b(?:(\\d+)|(on|yirmi|otuz|kırk|elli|altmış)(?:\\s+(bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz))?|(bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz)|(one|two|three|four|five|six|seven|eight|nine|ten|fourteen|fifteen|thirty))\\s*(days?|hours?|months?|gün|saat|ay)\\b|(?:(\\d+)|(یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|چهارده|پانزده|سی))\\s*(روز|ساعت|ماه)",
        setOf(RegexOption.IGNORE_CASE)
    )

    private fun extractTimePairs(text: String): List<Pair<String, String>> {
        val src = toAsciiDigits(text)
        val out = mutableListOf<Pair<String, String>>()
        for (m in TIME_EXPR_RE.findAll(src)) {
            val g = m.groupValues
            val num = when {
                g[1].isNotEmpty() -> g[1]
                g[7].isNotEmpty() -> g[7]
                g[2].isNotEmpty() -> ((TR_TENS[g[2].lowercase()] ?: 0) + (if (g[3].isNotEmpty()) TR_ONES[g[3].lowercase()] ?: 0 else 0)).toString()
                g[4].isNotEmpty() -> (TR_ONES[g[4].lowercase()] ?: 0).toString()
                g[5].isNotEmpty() -> (EN_NUMS[g[5].lowercase()] ?: 0).toString()
                g[8].isNotEmpty() -> (FA_NUMS[g[8]] ?: 0).toString()
                else -> ""
            }
            val rawUnit = g[6].ifEmpty { g[9] }.lowercase()
            val unit = when (rawUnit) {
                "day", "days", "روز", "gün" -> "day"
                "hour", "hours", "ساعت", "saat" -> "hour"
                else -> "month"
            }
            if (num.isNotEmpty() && num != "0") out.add(num to unit)
        }
        return out
    }

    private val CITATION_REF_RE = Regex(
        "\\b(?:madde|md\\.?|clause|article|sec(?:tion)?\\.?|بند|ماده)\\s*\\d+(?:\\s*\\(\\d+\\))*",
        setOf(RegexOption.IGNORE_CASE)
    )

    private fun extractNumbers(text: String): List<String> {
        val withoutCitations = CITATION_REF_RE.replace(text, " ")
        val digits = NUMBER_RE
            .findAll(normalize(withoutCitations))
            .map { it.value }
            .filter { !YEAR_RE.matches(it) }
            .toList()
        return (digits + extractTimePairs(withoutCitations).map { it.first }).distinct()
    }

    private fun numbersCompatible(fragNums: List<String>, termNums: List<String>): Boolean {
        if (fragNums.isEmpty() || termNums.isEmpty()) return true
        val termSet = termNums.toSet()
        val fragSet = fragNums.toSet()
        return fragNums.all { it in termSet } && termNums.all { it in fragSet }
    }

    private fun detectCueType(trim: String): String? {
        if (extractSafeHarborAntecedent(trim) != null) return "implicit-dependency"
        CUE_RULES.firstOrNull { it.regex.containsMatchIn(trim) }?.type?.let { return it }
        if (extractTimePairs(trim).isNotEmpty()) return "temporal-deadline"
        return null
    }

    private fun isHeadingOrNoise(trim: String, lineIndex: Int): Boolean {
        if (DEMO_BOILERPLATE_RE.containsMatchIn(trim)) return true
        if (detectCueType(trim) != null) return false
        if (lineIndex == 1 && HEADING_LINE1_RE.containsMatchIn(trim) && !TERMINAL_PUNCT_RE.containsMatchIn(trim)) return true
        return tokens(trim).size < 2
    }

    private fun overlapStats(fragment: String, termText: String): Triple<Double, Double, Int> {
        val x = tokens(fragment)
        val y = tokens(termText)
        if (x.isEmpty() || y.isEmpty()) return Triple(0.0, 0.0, x.size)
        val shared = x.count { it in y }
        return Triple(shared.toDouble() / min(x.size, y.size), shared.toDouble() / x.size, x.size - shared)
    }

    private fun matchesExistingTerm(
        trim: String,
        terms: List<PolicyTerm>,
        hintMap: Map<String, List<String>>,
        policy: PolicyScenario
    ): Boolean {
        val effectiveTrim = extractSafeHarborAntecedent(trim) ?: trim
        val normTrim = normalize(effectiveTrim)
        val policyTitleAndTerms = listOf(policy.title, policy.question).plus(terms.map { "${it.label} ${it.why}" }).joinToString(" ")
        val allPolicyTokens = HashSet<String>()
        allPolicyTokens.addAll(tokens(policy.title))
        allPolicyTokens.addAll(tokens(policy.question))
        for (pt in terms) {
            allPolicyTokens.addAll(tokens("${pt.label} ${pt.why}"))
        }
        val fragNums = extractNumbers(effectiveTrim)
        val fragIsBan = BAN_POLARITY_RE.containsMatchIn(effectiveTrim)

        for (t in terms) {
            val hints = hintMap[t.id].orEmpty()
            val termFull = "${t.label} ${t.why}"
            val termNums = extractNumbers(termFull)
            if (!numbersCompatible(fragNums, termNums)) continue
            val termIsBan = TERM_EXCLUSION_RE.containsMatchIn(termFull)
            if (fragIsBan && !termIsBan) continue
            if (!fragIsBan && termIsBan) {
                if (Regex("\\bnot\\s+marked\\b", RegexOption.IGNORE_CASE).containsMatchIn(termFull) &&
                    Regex("\\bfinal\\s+sale\\b", RegexOption.IGNORE_CASE).containsMatchIn(effectiveTrim)
                ) {
                    continue
                }
                if (Regex("ممنوع|نباید|نمی‌?شود|هیچ").containsMatchIn(termFull) &&
                    !BAN_POLARITY_RE.containsMatchIn(effectiveTrim)
                ) {
                    continue
                }
            }
            val roleCleanedTrim = stripBenignLegalModifiers(effectiveTrim, termFull, policyTitleAndTerms)
            val cleanedTokens = tokens(roleCleanedTrim)
            val outOfPolicyNovel = cleanedTokens.count { tok ->
                !(tok in allPolicyTokens || (tok.endsWith("s") && tok.length > 3 && tok.dropLast(1) in allPolicyTokens))
            }
            val (minRecall, fragCoverage, novelCount) = overlapStats(roleCleanedTrim, termFull)
            val hintHit = hints.any { normTrim.contains(normalize(it)) }
            if (hintHit && min(novelCount, outOfPolicyNovel) <= 2) return true
            if (minRecall >= 0.6 && fragCoverage >= 0.55 && min(novelCount, outOfPolicyNovel) <= 1) return true
        }
        return false
    }

    private fun detectConflictSignals(candidates: List<DiscoveredClause>): List<ConflictSignal> {
        val signals = mutableListOf<ConflictSignal>()
        val positives = mutableListOf<DiscoveredClause>()
        val negatives = mutableListOf<DiscoveredClause>()
        for (c in candidates) {
            val low = c.label.lowercase()
            val isCond = CONFLICT_CONDITIONAL_RE.containsMatchIn(low)
            if (!isCond && NEG_CONFLICT_RE.containsMatchIn(low)) {
                negatives.add(c)
            } else if (POS_CONFLICT_RE.containsMatchIn(low)) {
                positives.add(c)
            }
        }
        if (positives.isNotEmpty() && negatives.isNotEmpty()) {
            signals.add(
                ConflictSignal(
                    lineA = positives.first().line,
                    lineB = negatives.first().line,
                    summary = "Lines ${positives.first().line} and ${negatives.first().line} contain opposing eligibility/refund statements."
                )
            )
        }

        data class TimeEntry(val cand: DiscoveredClause, val num: String, val unit: String, val toks: Set<String>)
        fun normUnit(raw: String): String = when (raw.lowercase()) {
            "day", "days", "روز", "gün" -> "day"
            "hour", "hours", "ساعت", "saat" -> "hour"
            else -> "month"
        }

        val entries = mutableListOf<TimeEntry>()
        for (c in candidates) {
            for ((num, unit) in extractTimePairs(c.label)) {
                entries.add(TimeEntry(c, num, unit, tokens(c.label)))
            }
        }
        for (i in entries.indices) {
            for (j in i + 1 until entries.size) {
                val a = entries[i]
                val b = entries[j]
                if (a.cand.line == b.cand.line || a.unit != b.unit || a.num == b.num) continue
                val shared = a.toks.any { it in b.toks }
                if (shared || (a.cand.matchedExisting && b.cand.cueType == "temporal-deadline")) {
                    signals.add(
                        ConflictSignal(
                            lineA = a.cand.line,
                            lineB = b.cand.line,
                            summary = "Lines ${a.cand.line} (${a.num} ${a.unit}s) and ${b.cand.line} (${b.num} ${b.unit}s) state competing time limits."
                        )
                    )
                    return signals
                }
            }
        }
        return signals
    }

    private data class ClauseUnit(
        val trim: String,
        val quote: String,
        val startOffset: Int,
        val endOffset: Int,
        val cueType: String?,
        val matchedExisting: Boolean
    )

    fun analyzeSourceDocument(
        text: String?,
        policy: PolicyScenario,
        maxCandidates: Int = 12,
        includeUnclassified: Boolean = true
    ): SourceAuditResult {
        val raw = text ?: ""
        val truncatedByCharLimit = raw.length > 30_000
        val scanned = raw.take(30_000)
        val parts = sentencePartsWithSpans(scanned)
        val hintMap = SAMPLE_MATCH_HINTS[policy.id].orEmpty()

        val out = mutableListOf<DiscoveredClause>()
        val seen = HashSet<String>()
        val uncertaintyReasons = mutableListOf<String>()
        var truncatedCount = 0
        var staleSignals = 0
        var externalReferenceCount = 0
        var unclassifiedCount = 0

        if (truncatedByCharLimit) {
            uncertaintyReasons.add("Source document exceeded 30,000-character scan cap; remaining text was not analyzed.")
        }

        fun pushCandidate(item: DiscoveredClause) {
            if (out.size < maxCandidates) out.add(item)
            else if (!item.matchedExisting) truncatedCount += 1
        }

        for ((line, fragment, startOffset, _) in parts) {
            val bulletMatch = BULLET_PREFIX_RE.find(fragment)
            val bulletLen = bulletMatch?.value?.length ?: 0
            val trim = fragment.substring(bulletLen).trim()
            val trimStartOffset = startOffset + bulletLen
            if (trim.length > 550) {
                truncatedCount += 1
                uncertaintyReasons.add("Line $line exceeds the 550-character clause scan limit; split or review the original paragraph before attesting coverage.")
                continue
            }
            if (trim.isEmpty()) continue
            if (isHeadingOrNoise(trim, line)) {
                if (STALE_YEAR_RE.containsMatchIn(trim)) {
                    staleSignals += 1
                    uncertaintyReasons.add("Line $line references an older/archived/expired policy marker (\"${trim.take(80)}\").")
                }
                continue
            }
            val key = normalize(trim)
            if (key.isEmpty() || !seen.add(key)) continue
            if (STALE_YEAR_RE.containsMatchIn(trim)) staleSignals += 1

            val wholeCueType = detectCueType(trim)
            val wholeMatched = if (wholeCueType == "cross-reference") false else matchesExistingTerm(trim, policy.terms, hintMap, policy)

            var units: List<ClauseUnit>? = null
            if (!wholeMatched && wholeCueType != "cross-reference") {
                val subClauses = splitSubClausesWithSpans(trim, trimStartOffset)
                if (subClauses.size > 1) {
                    val evalSubs = subClauses.map { sub ->
                        val subCue = detectCueType(sub.fragment) ?: wholeCueType
                        val subMatch = if (subCue == "cross-reference") false else matchesExistingTerm(sub.fragment, policy.terms, hintMap, policy)
                        ClauseUnit(sub.fragment, sub.fragment, sub.startOffset, sub.endOffset, subCue, subMatch)
                    }
                    val substantive = evalSubs.filter { tokens(it.trim).size >= 2 || it.cueType != null }
                    if (substantive.size > 1 && substantive.all { it.matchedExisting }) {
                        units = listOf(ClauseUnit(trim, fragment, startOffset, startOffset + fragment.length, wholeCueType, true))
                    } else if (substantive.any { it.matchedExisting } && substantive.any { !it.matchedExisting }) {
                        units = substantive
                    }
                }
            }

            if (units == null) {
                units = listOf(ClauseUnit(trim, fragment, startOffset, startOffset + fragment.length, wholeCueType, wholeMatched))
            }

            for (u in units) {
                if (normalize(u.trim).isEmpty()) continue
                if (u.cueType != null) {
                    if (u.cueType == "cross-reference") externalReferenceCount += 1
                    pushCandidate(
                        DiscoveredClause(
                            label = u.trim,
                            reason = if (u.cueType == "cross-reference") {
                                "Line $line references external/standard rules that are not enumerated here; verify before approving."
                            } else {
                                "The supplied source document states this (${u.cueType}) on line $line; review applicability and whether this is already covered."
                            },
                            origin = "document-scan",
                            cueType = u.cueType,
                            line = line,
                            quote = u.quote,
                            matchedExisting = if (u.cueType == "cross-reference") false else u.matchedExisting,
                            startOffset = u.startOffset,
                            endOffset = u.endOffset
                        )
                    )
                    continue
                }

                val threshold = if (u.trim.length < 24) 2 else 4
                if (!u.matchedExisting && includeUnclassified && tokens(u.trim).size >= threshold) {
                    unclassifiedCount += 1
                    pushCandidate(
                        DiscoveredClause(
                            label = u.trim,
                            reason = "Unclassified substantive clause on line $line; scanner cannot exclude a hidden requirement — human review required.",
                            origin = "uncertain-clause",
                            cueType = "unclassified-substantive",
                            line = line,
                            quote = u.quote,
                            matchedExisting = false,
                            startOffset = u.startOffset,
                            endOffset = u.endOffset
                        )
                    )
                }
            }
        }

        val conflictSignals = detectConflictSignals(out)
        if (truncatedCount > 0) {
            uncertaintyReasons.add("$truncatedCount additional clause(s) exceeded the $maxCandidates-candidate scan limit.")
        }
        if (externalReferenceCount > 0) {
            uncertaintyReasons.add("$externalReferenceCount external rule cross-reference(s) detected.")
        }
        if (conflictSignals.isNotEmpty()) {
            uncertaintyReasons.add(conflictSignals.first().summary)
        }
        if (staleSignals > 0 && uncertaintyReasons.none { "older/archived/expired" in it }) {
            uncertaintyReasons.add("Source mentions historical/expired validity markers; confirm revision is current.")
        }

        return SourceAuditResult(
            candidates = out,
            novelCount = out.count { !it.matchedExisting },
            truncatedByCharLimit = truncatedByCharLimit,
            truncatedCount = truncatedCount,
            externalReferenceCount = externalReferenceCount,
            unclassifiedCount = unclassifiedCount,
            staleSignals = staleSignals,
            conflictSignals = conflictSignals,
            coverageUncertain = truncatedByCharLimit ||
                truncatedCount > 0 ||
                conflictSignals.isNotEmpty() ||
                externalReferenceCount > 0 ||
                unclassifiedCount > 0 ||
                staleSignals > 0 ||
                out.any { !it.matchedExisting && it.cueType == "negation-exception" },
            uncertaintyReasons = uncertaintyReasons
        )
    }

    fun validateSourceQuote(quote: String?, source: String?): Boolean {
        val q = (quote ?: "").trim()
        if (q.isEmpty()) return false
        return (source ?: "").contains(q)
    }
}
