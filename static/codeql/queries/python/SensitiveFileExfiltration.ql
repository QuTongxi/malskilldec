/**
 * @name Local file content reaches an outbound request
 * @description Data read from the local filesystem is passed to a network call.  Combined
 *              with a skill's broad file access this is how user data leaves the machine.
 * @kind path-problem
 * @problem.severity error
 * @id malskill/py/sensitive-file-exfiltration
 * @tags security
 */

import python
import semmle.python.dataflow.new.TaintTracking
import Sources

module FileExfilConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    exists(FileSystemAccess access | source = access) and not sensitiveFileSource(source)
  }

  predicate isSink(DataFlow::Node sink) { networkSink(sink) }
}

module FileExfilFlow = TaintTracking::Global<FileExfilConfig>;

import FileExfilFlow::PathGraph

from FileExfilFlow::PathNode source, FileExfilFlow::PathNode sink
where FileExfilFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "File content read at $@ is sent to a network endpoint.",
  source.getNode(), "this file read"
