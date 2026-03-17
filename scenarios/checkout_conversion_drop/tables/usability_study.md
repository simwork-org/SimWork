# ZaikaNow Checkout & UPI Reliability Study

## Study Overview

**Type:** Moderated usability study  
**Participants:** n=24  
**Date:** January 22-28, 2025  
**Objective:** Evaluate ordering and payment completion across Android, iOS, and web in major Indian metros

Participants were active ZaikaNow customers from Bengaluru, Mumbai, Delhi NCR, Hyderabad, and Pune. Most participants were frequent UPI users, reflecting the app's normal payment mix.

---

## Baseline Snapshot (November 2024)

| Metric | Baseline |
|--------|----------|
| Task completion rate | 93% |
| Avg payment confirmation time | 4.1s |
| Users reporting payment confusion | 2/18 |
| Users abandoning checkout | 2/18 |

---

## January Study Findings

| Metric | Baseline | January Study | Change |
|--------|----------|---------------|--------|
| Task completion rate | 93% | 61% | -32pp |
| Avg payment confirmation time | 4.1s | 13.9s | +239% |
| Users abandoning checkout | 2/18 | 10/24 | Significant increase |
| Users reporting trust loss after failed payment | 1/18 | 11/24 | Significant increase |

### Platform View

| Platform | Task Completion | Avg Confirmation Time | Common Failure Mode |
|----------|-----------------|-----------------------|---------------------|
| Android | 49% | 17.8s | UPI callback timeout |
| iOS | 72% | 9.3s | Delayed confirmation |
| Web | 81% | 6.1s | Retry confusion |

### Key Themes

1. **UPI approval happened, but the order stayed stuck**
   - Several Android participants approved the payment in their bank app but never received a clear confirmation in ZaikaNow.
2. **Money debited, order unclear**
   - Users were not sure whether they had been charged, reversed, or needed to retry.
3. **Retry guidance was weak**
   - The app did not clearly tell users whether to wait, retry, or choose another method.
4. **Trust damage persisted**
   - Even when later attempts worked, participants reported they were less willing to place future orders.

### Participant Quotes

> "I approved the UPI collect request, came back to the app, and it just kept spinning." — Participant 4, Bengaluru

> "If money has left my account, I should not have to guess whether lunch is actually coming." — Participant 11, Mumbai

> "After two failed payments I opened Zomato instead. I didn't want to risk it again." — Participant 17, Delhi NCR

### Recommendations

1. Improve UPI status messaging after approval.
2. Add explicit retry and fallback-method guidance.
3. Prioritize Android + UPI reliability in top metros.
4. Add post-failure reassurance for reversed or pending payments.
5. Track repeat-order drop among affected customers for recovery monitoring.
