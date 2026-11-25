package com.gapwise.hybrid.engine

object SamplePolicies {
    val ALL: List<PolicyScenario> = listOf(
        PolicyScenario(
            id = "refund",
            title = "Store return policy",
            tag = "Policy · demo",
            scope = "Fictional store policy: not actual merchant terms",
            source = "Sample demonstration data written for this prototype",
            question = "Can we approve a refund for this returned purchase?",
            terms = listOf(
                PolicyTerm("period", "Request is within 14 days of delivery", "14-day return window from delivery", 1, 5),
                PolicyTerm("receipt", "Customer can provide order proof or receipt", "Order verification required", 1, 5),
                PolicyTerm("unused", "Item is unused and in original condition", "Condition limits eligible refunds", 2, 4),
                PolicyTerm("clearance", "Item is not marked final sale", "Final sale items are excluded", 2, 4)
            ),
            sampleSourceText = """
                DEMO STORE / RETURNS AND REFUNDS POLICY — 2026-11-20 (fictional)
                1. Return requests must be submitted within 14 days of delivery.
                2. Customers must provide an order receipt or equivalent proof of purchase.
                3. Returned items must be unused and in their original condition.
                4. Final-sale merchandise is excluded from standard refunds.
                5. Safety-sealed items must have an intact tamper-evident seal for a refund.
                6. A cash refund is permitted only if the original payment method can be verified.
                This fictional document is solely for a software demonstration, not any real store's terms.
            """.trimIndent()
        ),
        PolicyScenario(
            id = "event",
            title = "Event cancellation policy",
            tag = "Contract · demo",
            scope = "Illustrative sample event terms only: verify your real ticket contract",
            source = "Sample demonstration data written for this prototype",
            question = "Can this registration be cancelled without a fee?",
            terms = listOf(
                PolicyTerm("hours", "Cancellation is at least 48 hours before start", "Late cancellations incur a fee", 1, 5),
                PolicyTerm("flexible", "Ticket tier is eligible for flexible changes", "Basic tickets are non-refundable", 1, 5),
                PolicyTerm("checkin", "Attendee has not already checked in", "Checked-in bookings cannot cancel", 2, 3)
            ),
            sampleSourceText = """
                DEMO EVENT / CANCELLATION TERMS — 2026-11-20 (fictional)
                1. Free cancellation requires at least 48 hours before the event.
                2. Ticket holders must have purchased a flexible-cancellation ticket.
                3. A booking that has already been checked in cannot be cancelled free.
                4. Group bookings of 10 or more must receive manager authorization.
                This fictional document is solely for a software demonstration, not real booking terms.
            """.trimIndent()
        ),
        PolicyScenario(
            id = "software",
            title = "Software redistribution checklist",
            tag = "Compliance · demo",
            scope = "Illustrative checklist only: consult the actual licence and legal counsel",
            source = "Training checklist written for this demo, not a legal determination",
            question = "Have we completed this demo distribution checklist?",
            terms = listOf(
                PolicyTerm("license", "A copy of the applicable licence is included", "Check packaging includes the licence.", 1, 5),
                PolicyTerm("notice", "Any required NOTICE information is preserved", "Check actual licence requirements for NOTICE.", 2, 4),
                PolicyTerm("modifications", "Modified files are marked as changed when required", "Check marking obligations for modifications.", 2, 3)
            ),
            sampleSourceText = """
                DEMO SOFTWARE / INTERNAL DISTRIBUTION CHECKLIST — 2026-11-20 (fictional)
                1. Distribution must include a copy of the applicable software licence.
                2. Any required NOTICE information must be preserved.
                3. Changed source files must be marked when the applicable licence requires it.
                4. Third-party assets must be reviewed for separate attribution requirements.
                This sample checklist is illustrative only and does not replace checking applicable licences.
            """.trimIndent()
        )
    )

    fun byId(id: String): PolicyScenario? = ALL.firstOrNull { it.id == id }
}
