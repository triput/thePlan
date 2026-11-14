# CPython 3.12.16 upstream framing reference

Dex, November 11, 2026. Read-only primary-source web review. No downloaded code was imported or executed. This reference refines original-behavior hypotheses; it is not a capture from the pinned runner image and does not replace the required native provenance/witness gate.

In the published v3.12.16 HTTPResponse.read implementation, a bounded read reaching EOF can close its input without raising for unsatisfied Content-Length. Chunk parsing consumes two separator bytes without comparing their values, and trailer processing tolerates EOF. That upstream version also caps interim responses and trailer counts, so an unlimited-stream hypothesis must account for those guards. Relevant locations: read lines434–458; chunk/trailer helpers503–561; interim cap104–109 and trailer cap532–539. [CPython v3.12.16 http/client.py](https://raw.githubusercontent.com/python/cpython/v3.12.16/Lib/http/client.py).

The published SSLContext.wrap_socket default suppresses ragged EOF errors; SSLSocket.read converts the matching EOF error to an empty result when suppression is enabled. Relevant locations:416–429 and1028–1040. [CPython v3.12.16 ssl.py](https://raw.githubusercontent.com/python/cpython/v3.12.16/Lib/ssl.py).

## Consequence for the current design

These upstream observations support retaining the separate fixed-length, chunk-separator, trailer-termination and TLS EOF original witnesses. They do not establish the runner's actual parser acceptance, linked OpenSSL behavior or file hashes. The retained runtime probe establishes only that runner c2201104... reports Python3.12.16; a version string alone is insufficient to equate its bytes with this upstream tag.

Keep the host3.11 analysis, upstream3.12.16 reference and eventual native source capture as three separate provenance records. For real stall proof, observe the first actual stop condition (parser guard, cumulative byte ceiling, application deadline, disconnect or retirement uncertainty) rather than claiming every case necessarily reaches the timer. Do not alter the application, verifier or run inventory based on this reference without the applicable reviewed scope.

No new execution/implementation authority is supplied. Pending T07 fake card remains unchanged; endpoint unbound and all holds stay.
