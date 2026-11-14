# Worker-observer diagnostic attempt: exact-ID cleanup request

One authorized invocation stopped. The bounded diagnostic identifies SuiteStop -> CoveringRootOutcomeUnknown -> CoveringTransportRefused at api/app/services/covering_joined_https.py56 (nonzero socket SO_ERROR after readiness). The diagnostic is truncated; exact errno/message and deeper cause were not retained. No native PASS or success cleanup.

Two read-only inspections passed the immutable helper's full frozen identity,image,labels,argv,user,isolation,namespace,mount,bind and tmpfs checks. Runner fa60bb508fe07186d55ba86e3ab3674b4a2af4e853bedc307613177179386818 exited125; DB1b7f0e807a0a4064d62468fc9474fa58f5de64b49530e1aa7ce8241f7d5f086c is running. All283 input pins unchanged.

Proposed nine-call sequence,requiring separate state-change approval:
1. Recheck exact runner identity/exited125;remove it;require same ID;verify absence.
2. Recheck exact DB identity/running;SIGINT it;require same ID;wait and require exit0.
3. Recheck exact DB identity/exited0;remove it;require same ID;verify absence. Save receipts.

Use unchanged Docker helper7F7EA8204879D312624DAEB7941504FEA1402F45C48BDA79DDAD94A23711AC53,frozen Docker executable8985CD8AC002C3240B5AA48FE401FCB55DCA5D849B537E3C835564E8E8C49A70,exact endpoint npipe:////./pipe/dockerDesktopLinuxEngine,and host/docker-ops-config.json8F93471ED6C8487DB15C195DBB0725F4B8E6F81B9246581A75CBCD7E4C812C56 in the worker-diagnostic-launch-dex-v1 nested packet.30s per call within300s cleanup admission;existing local CLI kill does not wait or prove daemon cancellation. Three identity checks plus six state/absence operations.

Stop on failure,mismatch,timeout or UNKNOWN. No force,retries,repairs,restart,rerun,fallback or extra cleanup. This changes container state and is outside launch success-only disposal authority. Product endpoint unbound;all other holds stay. The standing offline source trace may continue while this decision is pending.
