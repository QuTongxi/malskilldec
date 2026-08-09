/** Shared source/sink definitions for the malicious-skill queries. */

import javascript
import semmle.javascript.security.dataflow.CodeInjectionCustomizations

/** A path that names a credential store, wallet or other secret material. */
bindingset[path]
predicate sensitivePath(string path) {
  path.regexpMatch("(?i).*(\\.ssh|\\.aws|\\.gnupg|\\.env|\\.netrc|\\.npmrc|\\.docker|\\.kube|" +
      "credential|id_rsa|id_ed25519|keychain|cookies|login data|wallet|keystore|mnemonic|" +
      "seed|secret|token|password|\\.git-credentials|/etc/passwd|/etc/shadow).*")
}

/** Reading an environment variable, i.e. where API keys usually live. */
predicate envSource(DataFlow::Node node) {
  node = NodeJSLib::process().getAPropertyRead("env")
  or
  node = NodeJSLib::process().getAPropertyRead("env").getAPropertyRead(_)
}

/** Reading a file whose path looks like a credential store. */
predicate sensitiveFileSource(DataFlow::Node node) {
  exists(FileSystemReadAccess read |
    sensitivePath(read.getAPathArgument().getStringValue()) and
    node = read.getADataNode()
  )
}

/** The response of an outbound HTTP request: attacker-controlled content. */
predicate remoteContentSource(DataFlow::Node node) {
  exists(ClientRequest request | node = request.getAResponseDataNode())
}

/** Base64/hex decoding: the classic payload-hiding step. */
predicate decodedSource(DataFlow::Node node) {
  exists(DataFlow::CallNode call |
    call = DataFlow::globalVarRef("atob").getACall() and node = call
  )
  or
  exists(DataFlow::CallNode call |
    call = DataFlow::moduleMember("buffer", "Buffer").getAPropertyRead("from").getACall() or
    call = DataFlow::globalVarRef("Buffer").getAPropertyRead("from").getACall()
  |
    call.getArgument(1).getStringValue() = ["base64", "hex", "base64url"] and node = call
  )
  or
  exists(DataFlow::CallNode call |
    call = DataFlow::moduleMember("zlib", ["gunzipSync", "inflateSync", "brotliDecompressSync"]).getACall() and
    node = call
  )
}

/** Anything that pushes bytes off the machine. */
predicate networkSink(DataFlow::Node node) {
  exists(ClientRequest request |
    node = request.getUrl() or
    node = request.getADataNode() or
    node = request.getAnArgument()
  )
}

/** Anything that turns data into running code or a shell command. */
predicate executionSink(DataFlow::Node node) {
  node instanceof CodeInjection::Sink
  or
  exists(SystemCommandExecution execution | node = execution.getACommandArgument())
}
