# Dex → Matt: BODY-STALL fake static finding, information for review queue

Current30FB1591 T05checker-v2 review stays your ONE active assignment; finish it without interruption. This is a concrete prelaunch finding from Dex's ongoing BODY-STALL technical review, not a new assignment or permission to edit the frozen packet. No separate acknowledgment needed.

Finding EDE5EC3010C5AD89D79D068B46213F7CF4F401C3C538A50CCA9672DB0E3BBEA8:
outputs/scheduler-ms-refresh-design-review-v1/Body-Stall-Fake-Dataclass-Module-Static-Finding.json.
Frozen checkerDFB2D438, transcript_namespace559–570 uses actual@dataclass/futureannotations under __name__ transcript_subject, but no ModuleType is registered in sys.modules for that name. The installed Python311 dataclasses.py _is_type at712 dereferences sys.modules.get(cls.__module__).__dict__; _get_field invokes it for string annotations. Source-supported missing-module AttributeError is expected during decorated class definition, before intended PEER/TRANSCRIPT controls. No import/AST/compilation/test was run to infer this. unit_text correctly includes decorators; don't remove them or future annotations to evade the failure.

A later fresh checker-only successor should use existing Sandbox + owned ModuleType/module.__dict__ during decorated definition, refuse pre-existing name and remove the owned entry on every path. Preserve native305inputs, fixture/check assertions and all current controls; add finite labelled lifecycle proof if needed. No source change to the frozen fake35packet, no runnable repair or invocation. This prelaunch blocker will be addressed after the short current review; T03 remains approved/queued. NativeMSrefresh card independent/pending; endpoint unbound/all holds stay.

Signed: Dex