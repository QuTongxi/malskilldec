/** Shared source/sink definitions for the malicious-skill queries. */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs
import semmle.python.Concepts

/** A path that names a credential store, wallet or other secret material. */
bindingset[path]
predicate sensitivePath(string path) {
  path.regexpMatch("(?i).*(\\.ssh|\\.aws|\\.gnupg|\\.env|\\.netrc|\\.pgpass|\\.npmrc|\\.docker|" +
      "\\.kube|credential|id_rsa|id_ed25519|keychain|cookies|login data|wallet|keystore|" +
      "mnemonic|seed|secret|token|password|\\.git-credentials|/etc/passwd|/etc/shadow).*")
}

/** Reading an environment variable, i.e. where API keys usually live. */
predicate envSource(DataFlow::Node node) {
  node = API::moduleImport("os").getMember("environ").getASubscript().asSource()
  or
  node = API::moduleImport("os").getMember("environ").getMember(["get", "items", "keys", "values", "copy"]).getACall()
  or
  node = API::moduleImport("os").getMember(["getenv", "environb"]).getACall()
  or
  node = API::moduleImport("dotenv").getMember(["dotenv_values", "get_key"]).getACall()
}

/** Reading a file whose path looks like a credential store. */
predicate sensitiveFileSource(DataFlow::Node node) {
  exists(FileSystemAccess access, DataFlow::Node path |
    path = access.getAPathArgument() and
    sensitivePath(path.asExpr().(StringLiteral).getText()) and
    node = access
  )
}

/** The response body of an outbound HTTP request: attacker-controlled content. */
predicate remoteContentSource(DataFlow::Node node) {
  exists(API::Node response |
    response = API::moduleImport(["requests", "httpx"])
          .getMember(["get", "post", "put", "request", "head"]).getReturn()
    or
    response = API::moduleImport("urllib").getMember("request").getMember("urlopen").getReturn()
    or
    response = API::moduleImport("urllib3").getMember("PoolManager").getReturn().getMember("request").getReturn()
  |
    node = response.getMember(["text", "content", "json", "read", "data"]).getAValueReachableFromSource()
    or
    node = response.getMember(["json", "read"]).getACall()
    or
    node = response.asSource()
  )
}

/** Base64/hex/compression decoding: the classic payload-hiding step. */
predicate decodedSource(DataFlow::Node node) {
  node = API::moduleImport("base64")
        .getMember(["b64decode", "standard_b64decode", "urlsafe_b64decode", "decodebytes", "b32decode", "b16decode"])
        .getACall()
  or
  node = API::moduleImport("binascii").getMember(["a2b_base64", "unhexlify"]).getACall()
  or
  node = API::moduleImport(["zlib", "gzip", "lzma", "bz2"]).getMember("decompress").getACall()
  or
  node = API::moduleImport("codecs").getMember("decode").getACall()
}

/** Anything that pushes bytes off the machine. */
predicate networkSink(DataFlow::Node node) {
  exists(Http::Client::Request request | node = request.getAUrlPart())
  or
  exists(API::CallNode call |
    call = API::moduleImport(["requests", "httpx"])
          .getMember(["get", "post", "put", "patch", "delete", "request"]).getACall()
  |
    node = call.getArgByName(["data", "json", "params", "files", "headers", "content", "cookies"]) or
    node = call.getArg(_)
  )
  or
  node = API::moduleImport("socket").getMember("socket").getReturn()
        .getMember(["send", "sendall", "sendto", "connect"]).getACall().getArg(_)
  or
  node = API::moduleImport("smtplib").getMember(["SMTP", "SMTP_SSL"]).getReturn()
        .getMember(["sendmail", "send_message"]).getACall().getArg(_)
  or
  node = API::moduleImport("urllib").getMember("request").getMember(["urlopen", "Request"]).getACall().getArg(_)
}

/** Anything that turns data into running code or a shell command. */
predicate executionSink(DataFlow::Node node) {
  exists(CodeExecution execution | node = execution.getCode())
  or
  exists(SystemCommandExecution execution | node = execution.getCommand())
}
