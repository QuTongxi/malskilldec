/**
 * @name Credential material reaches an outbound request
 * @description Environment secrets or credential files flow into a network call,
 *              the core data-exfiltration pattern of malicious skills.
 * @kind path-problem
 * @problem.severity error
 * @id malskill/js/credential-exfiltration
 * @tags security
 */

import javascript
import Sources

module CredentialExfilConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { envSource(source) or sensitiveFileSource(source) }

  predicate isSink(DataFlow::Node sink) { networkSink(sink) }
}

module CredentialExfilFlow = TaintTracking::Global<CredentialExfilConfig>;

import CredentialExfilFlow::PathGraph

from CredentialExfilFlow::PathNode source, CredentialExfilFlow::PathNode sink
where CredentialExfilFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "Credential material from $@ is sent to a network endpoint.",
  source.getNode(), "this credential read"
