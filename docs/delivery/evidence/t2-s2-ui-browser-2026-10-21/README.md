# T2-S2-UI synthetic browser evidence (2026-10-21)

**Env:** Vite `http://127.0.0.1:5173` → API `http://127.0.0.1:8000` → Postgres `theplan_s1_test` @ `127.0.0.1:5433`. Demo user `nebula@localhost` (disposable seed; not household/live).

**Code tip under review:** bounce fix `@ f40ded6` (+ this docs tip commit).

| Shot | Claim |
| --- | --- |
| `W1-held-list.png` | Held list + count (10) + Show all expand |
| `W2-held-empty.png` | Empty: “No held misses.” |
| `W2-held-error-retry.png` | Error `role=alert` + Retry (not zero) |
| `W3-banner-before-edit.png` / `W3-banner-distinct-dates.png` | TZ label `America/Los_Angeles`; Original miss ≠ Current after date save |
| `W4-leave-held.png` | Leave held; banner remains unresolved |
| `W5-skip-success.png` | Skip confirm → banner cleared |
| `W6-bounds-still-missed.png` / `W6-release-success.png` | Bad dates → bounds alert; fix + Save dates & release clears held |
| `W7-stale-revision-409.png` | Stale `expected_revision` → conflict alert; dates unchanged |

Loading copy “Loading held…” observed on first CalendarSupportIdle paint (transient; not a separate PNG).
