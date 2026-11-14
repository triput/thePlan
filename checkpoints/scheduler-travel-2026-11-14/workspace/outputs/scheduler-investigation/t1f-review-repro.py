import sys
sys.path.insert(0, r'F:\Code Repo\ThePlan\apps\api')
sys.path.insert(0, r'F:\Code Repo\ThePlan\apps\api\tests')
import test_t1f_alias_canonicalize as t
from app.services.calendar_alias_canonicalize import AccountIdentityEvidence, canonicalize_calendar_account
from app.models.enums import CalendarSubscriptionRole
from sqlalchemy.exc import IntegrityError
t._disposable_db_only.__wrapped__()
for case in ('disabled_target','primary_role'):
    with t.SessionLocal() as db:
        try:
            owner,_=t._owner(db); account=t._account(db,owner)
            alias=t._sub(db,account,calendar_id='primary')
            target=t._sub(db,account,calendar_id='real-id',enabled=case!='disabled_target',role=CalendarSubscriptionRole.informational)
            ev=AccountIdentityEvidence(provider=account.provider,fetch_succeeded=True,google_primary_id='real-id')
            canonicalize_calendar_account(db,account,evidence=ev,now=t._NOW)
            db.flush()
            print(case, 'enabled primary count=',len([s for s in (alias,target) if s.is_enabled and s.role==CalendarSubscriptionRole.primary]))
        except IntegrityError as e:
            print(case, type(e).__name__, str(e.orig).splitlines()[0])
        finally: db.rollback()

