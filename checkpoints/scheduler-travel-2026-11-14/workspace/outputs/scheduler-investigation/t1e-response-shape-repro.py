import sys, json
from pathlib import Path
root = Path(r'F:\Code Repo\ThePlan\apps\api')
sys.path[:0] = [str(root), str(root/'tests')]
import httpx, pytest
import test_t1e_microsoft as t
from app.db import SessionLocal
from app.models import CalendarSubscription, UserSettings
from app.scheduler.calendar_freshness import evaluate_calendar_freshness

t.assert_t1a_container_isolated()
t.assert_disposable_database_url(t.engine.url.render_as_string(hide_password=False))
for label, response in [('missing_value', lambda: httpx.Response(200, json={})), ('invalid_json', lambda: httpx.Response(200, content=b'not json'))]:
    db = SessionLocal()
    try:
        with t._committed_ms(db, calendars=[('dex-'+label, label)]) as fx:
            with pytest.MonkeyPatch.context() as mp:
                _, settings, account, subs = t._load(db, fx)
                t._patch_token(mp)
                t._patch_httpx(mp, lambda request: response())
                result = {'case':label}
                try:
                    result['upserted'] = t._sync(db, account, fx.window_start, fx.window_end)
                    result['mint_mode'] = subs[0].coverage_mode
                    result['mint_item_count'] = subs[0].coverage_item_count
                    result['in_transaction_freshness_ok'] = evaluate_calendar_freshness(db, fx.owner_id, settings, fx.mint_now).ok
                except Exception as exc:
                    result['exception'] = type(exc).__name__
                db.rollback()
                with SessionLocal() as verify:
                    durable = verify.get(CalendarSubscription, fx.sub_ids[0])
                    s = verify.query(UserSettings).filter(UserSettings.owner_id==fx.owner_id).one()
                    result['after_rollback_freshness_ok'] = evaluate_calendar_freshness(verify, fx.owner_id, s, fx.mint_now).ok
                    result['failure_cause'] = durable.coverage_last_failure_cause
                print(json.dumps(result))
    finally:
        db.close()
