import sys,json
from pathlib import Path
root=Path(r'F:\Code Repo\ThePlan\apps\api'); sys.path[:0]=[str(root),str(root/'tests')]
import test_t1e_microsoft as t
import httpx,pytest
from datetime import datetime,timezone
from app.db import SessionLocal
from app.models import CalendarSubscription,UserSettings
from app.scheduler.calendar_freshness import evaluate_calendar_freshness

t.assert_t1a_container_isolated()
t.assert_disposable_database_url(t.engine.url.render_as_string(hide_password=False))
for label,payload in [('bad_expiry',{'access_token':'synthetic','expires_in':'invalid'}),('bad_token_type',{'access_token':{'unexpected':'object'},'expires_in':3600})]:
    db=SessionLocal()
    try:
        with t._committed_ms(db,calendars=[('dex-auth-a','A'),('dex-auth-b','B')]) as fx:
            with pytest.MonkeyPatch.context() as mp:
                _,_,account,_=t._load(db,fx)
                account.token_expires_at=datetime(2000,1,1,tzinfo=timezone.utc)
                db.flush()
                def handler(request):
                    assert 'oauth2/v2.0/token' in str(request.url)
                    return httpx.Response(200,json=payload)
                t._patch_httpx(mp,handler)
                result={'case':label}
                try: t._sync(db,account,fx.window_start,fx.window_end)
                except Exception as exc: result['exception']=type(exc).__name__
                db.rollback()
                with SessionLocal() as verify:
                    settings=verify.query(UserSettings).filter(UserSettings.owner_id==fx.owner_id).one()
                    result['after_rollback_freshness_ok']=evaluate_calendar_freshness(verify,fx.owner_id,settings,fx.mint_now).ok
                    result['failure_causes']=[verify.get(CalendarSubscription,i).coverage_last_failure_cause for i in fx.sub_ids]
                print(json.dumps(result))
    finally: db.close()
