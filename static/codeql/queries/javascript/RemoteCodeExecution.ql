/**
 * @name Remotely fetched content is executed
 * @description Content downloaded at runtime reaches eval/Function or a shell command,
 *              letting whoever controls the endpoint run code on the user's machine.
 * @kind path-problem
 * @problem.severity error
 * @id malskill/js/remote-code-execution
 * @tags security
 */

import javascript
import Sources

module RemoteExecConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { remoteContentSource(source) }

  predicate isSink(DataFlow::Node sink) { executionSink(sink) }
}

module RemoteExecFlow = TaintTracking::Global<RemoteExecConfig>;

import RemoteExecFlow::PathGraph

from RemoteExecFlow::PathNode source, RemoteExecFlow::PathNode sink
where RemoteExecFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "Content fetched at $@ is executed as code or as a command.",
  source.getNode(), "this remote fetch"
