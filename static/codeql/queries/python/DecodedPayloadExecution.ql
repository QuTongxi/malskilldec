/**
 * @name Decoded payload is executed
 * @description A base64/hex/compressed blob is decoded and then executed, which is how
 *              malicious skills hide their payload from review.
 * @kind path-problem
 * @problem.severity error
 * @id malskill/py/decoded-payload-execution
 * @tags security
 */

import python
import semmle.python.dataflow.new.TaintTracking
import Sources

module DecodedExecConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { decodedSource(source) }

  predicate isSink(DataFlow::Node sink) { executionSink(sink) }
}

module DecodedExecFlow = TaintTracking::Global<DecodedExecConfig>;

import DecodedExecFlow::PathGraph

from DecodedExecFlow::PathNode source, DecodedExecFlow::PathNode sink
where DecodedExecFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "A payload decoded at $@ is executed.", source.getNode(),
  "this decoding step"
