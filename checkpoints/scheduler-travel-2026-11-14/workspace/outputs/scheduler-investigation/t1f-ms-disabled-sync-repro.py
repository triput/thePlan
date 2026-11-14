import sys
sys.path.insert(0,r'F:\Code Repo\ThePlan\apps\api')
sys.path.insert(0,r'F:\Code Repo\ThePlan\apps\api\tests')
import test_t1f_alias_canonicalize as t
import pytest
t._disposable_db_only.__wrapped__()
class ReachedPull(Exception): pass
with t.SessionLocal() as db, pytest.MonkeyPatch.context() as mp:
    owner,_=t._owner(db); account=t._account(db,owner,provider=t.CalendarProvider.microsoft)
    alias=t._sub(db,account,calendar_id='primary')
    target=t._sub(db,account,calendar_id='real-id',enabled=False,role=t.CalendarSubscriptionRole.informational)
    t._patch_ms_token(mp); t._patch_ms_default_and_list(mp,'real-id')
    def stop(*a,**k):
        print('REACHED_PROVIDER_PULL', 'target_enabled=',target.is_enabled,'alias_enabled=',alias.is_enabled)
        raise ReachedPull()
    mp.setattr(t.ms_cal,'_pull_subscription_changes',stop)
    try:
        t.ms_cal.sync_account_events(db,settings=t._settings(),account=account,time_min=t._NOW-t.timedelta(days=1),time_max=t._NOW+t.timedelta(days=1))
        assert target.is_enabled is False, 'disabled stable calendar was re-enabled'
        assert alias.is_enabled is True, 'selected alias was disabled'
        print('PASS: full MS sync did not pull; disabled target and selected alias preserved')
    except ReachedPull: raise AssertionError('blocked collision reached provider pull')
    finally: db.rollback()

