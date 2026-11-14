# Native host entry and receipt binding

Static tracing of the selected frozen v5 wrapper/supervisor/immutable transport. Same named operator/supervisor roles, no execution or scope expansion. Native remains HOLD; these do not require completing every later fault case before a fake prerequisite run.

## Isolated host import closure

Invoke-Native-Provider.ps1 invokes the host supervisor as Python -I -S -B with its script path. np_supervisor.main later executes `from docker_transport import DockerOps` without adding the verified fixture directory to sys.path. An isolated script invocation does not admit its script directory as an import root. Author an explicit guarded import root for the already hash-admitted immutable helper, preserving isolation and no ambient fallback. The analogous runner bootstrap correction does not bootstrap this different host process.

## Command/evidence record sink is discarded

np_supervisor.main passes `host_record`, a function whose body is pass, into DockerOps. DockerOps.__init__ wraps that supplied callback in a synchronized record function. run_once opens an exclusive receipt and defines a different local record function, but never binds the immutable transport's callback to it. ProviderDockerOps also copied the original record callable during construction.

Therefore the host's created/suite events may reach the run_once receipt while the actual Docker command/output hashes, runner STOP metadata and transport events flow to the no-op. The advertised hash-only ordinary-console and sanitized STOP retention is not established by the current glue.

Connect the existing synchronized callback to the receipt sink once, immediately after exclusive receipt creation and before any Docker operation. One suitable design is a mutable sink holder behind the constructor-supplied host_record callback, with an explicit one-time binder called by run_once. Keep the immutable DockerOps source unchanged and retain its synchronization; do not merely replace it with an unsynchronized output writer or silently leave events unbound. Unbound/double-binding must refuse rather than discard events.

The later fake host-entry flow can use fake DockerOps, no process/Docker access, to demonstrate that the actual entry/run_once binding captures a synthetic docker_command/docker_output/runner_stop event in the same receipt and refuses an unbound sink. This targets the observed seam; it does not ask for another unrelated test matrix. Pin all newly read/extracted inputs and retain exact output bounds.

Source references: Invoke-Native-Provider.ps1 final isolated invocation; np_supervisor.py:main, run_once and ProviderDockerOps.__init__; docker_transport.py:__init__, _cmd and _record_runner_stop. No helper imports or commands were invoked to obtain these findings.
