"""Detection knowledge base: regex corpus, behaviour groups, malicious-type
taxonomy and the scoring model.

Everything that a human may want to tune lives here.  `workers.py` only applies
these rules, `pipeline.py` only orchestrates.
"""

import re

# --------------------------------------------------------------------------
# Severity levels
# --------------------------------------------------------------------------

LEVELS = ["low", "medium", "high", "critical"]
LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}
LEVEL_SCORE = {"low": 5, "medium": 12, "high": 25, "critical": 40}

# Bonus added when two behaviour groups co-occur (see SYNERGIES).
BONUS_SCORE = {"low": 8, "high": 20}


# --------------------------------------------------------------------------
# Behaviour groups -> the 8 malicious types (report.pdf, money access dropped)
#
# A group may serve several types, a type is fed by several groups.
# --------------------------------------------------------------------------

TYPE_LEVEL = {
    "prompt_injection": "critical",
    "malicious_code": "critical",
    "suspicious_download": "critical",
    "improper_credential_handling": "high",
    "secret_detection": "high",
    "third_party_content_exposure": "medium",
    "unverifiable_dependency": "medium",
    "modifying_system_services": "medium",
}

TYPE_GROUPS = {
    "prompt_injection": [
        "instruction_override", "jailbreak_persona", "secrecy_directive",
        "authority_spoof", "hidden_unicode", "hidden_markup",
    ],
    "malicious_code": [
        "reverse_shell", "dynamic_exec", "shell_exec", "pipe_to_shell",
        "destructive_fs", "obfuscation_encoding", "messaging_exfil",
        "network_send", "data_collection", "cloud_metadata",
    ],
    "suspicious_download": [
        "binary_download", "pipe_to_shell", "mandatory_install",
        "typosquat_package", "untrusted_host",
    ],
    "improper_credential_handling": [
        "credential_read", "credential_in_command", "env_harvest", "crypto_wallet",
    ],
    "secret_detection": [
        "hardcoded_secret",
    ],
    "third_party_content_exposure": [
        "third_party_content", "network_fetch", "data_collection",
    ],
    "unverifiable_dependency": [
        "remote_instruction_load", "untrusted_host", "network_fetch",
        "typosquat_package",
    ],
    "modifying_system_services": [
        "agent_config_write", "shell_config_write", "persistence_scheduling",
        "security_disable", "privilege_escalation", "tool_permission",
    ],
}

GROUP_TYPES = {}
for _type, _groups in TYPE_GROUPS.items():
    for _g in _groups:
        GROUP_TYPES.setdefault(_g, []).append(_type)


# --------------------------------------------------------------------------
# Semantic synergies: two groups together mean more than each alone.
# (group_a, group_b, target_type, bonus_level)
# --------------------------------------------------------------------------

SYNERGIES = [
    ("credential_read", "network_send", "malicious_code", "high"),
    ("credential_read", "untrusted_host", "improper_credential_handling", "high"),
    ("credential_read", "messaging_exfil", "malicious_code", "high"),
    ("env_harvest", "network_send", "malicious_code", "high"),
    ("env_harvest", "untrusted_host", "improper_credential_handling", "low"),
    ("credential_in_command", "network_send", "improper_credential_handling", "high"),
    ("crypto_wallet", "network_send", "improper_credential_handling", "high"),
    ("crypto_wallet", "untrusted_host", "improper_credential_handling", "high"),
    ("hardcoded_secret", "network_send", "secret_detection", "high"),
    ("hardcoded_secret", "untrusted_host", "secret_detection", "high"),
    ("obfuscation_encoding", "pipe_to_shell", "malicious_code", "high"),
    ("obfuscation_encoding", "instruction_override", "prompt_injection", "high"),
    ("reverse_shell", "obfuscation_encoding", "malicious_code", "high"),
    ("hidden_unicode", "instruction_override", "prompt_injection", "high"),
    ("hidden_markup", "instruction_override", "prompt_injection", "high"),
    ("jailbreak_persona", "secrecy_directive", "prompt_injection", "high"),
    ("secrecy_directive", "network_send", "prompt_injection", "high"),
    ("secrecy_directive", "credential_read", "prompt_injection", "high"),
    ("authority_spoof", "mandatory_install", "prompt_injection", "low"),
    ("binary_download", "untrusted_host", "suspicious_download", "high"),
    ("binary_download", "mandatory_install", "suspicious_download", "high"),
    ("pipe_to_shell", "untrusted_host", "suspicious_download", "high"),
    ("mandatory_install", "untrusted_host", "suspicious_download", "high"),
    ("typosquat_package", "untrusted_host", "suspicious_download", "low"),
    ("network_fetch", "dynamic_exec", "malicious_code", "high"),
    ("shell_exec", "network_fetch", "malicious_code", "low"),
    ("data_collection", "network_send", "malicious_code", "high"),
    ("destructive_fs", "secrecy_directive", "malicious_code", "high"),
    ("cloud_metadata", "network_send", "malicious_code", "high"),
    ("remote_instruction_load", "persistence_scheduling", "unverifiable_dependency", "high"),
    ("remote_instruction_load", "untrusted_host", "unverifiable_dependency", "high"),
    ("agent_config_write", "remote_instruction_load", "modifying_system_services", "high"),
    ("persistence_scheduling", "agent_config_write", "modifying_system_services", "high"),
    ("security_disable", "pipe_to_shell", "modifying_system_services", "high"),
    ("privilege_escalation", "binary_download", "modifying_system_services", "high"),
    ("shell_config_write", "persistence_scheduling", "modifying_system_services", "low"),
    ("tool_permission", "shell_exec", "modifying_system_services", "low"),
    ("third_party_content", "credential_read", "third_party_content_exposure", "high"),
    ("third_party_content", "network_send", "third_party_content_exposure", "low"),
    ("third_party_content", "network_fetch", "third_party_content_exposure", "low"),
]


# --------------------------------------------------------------------------
# Regex corpus.  (rule_id, group, level, description, pattern)
#
# Patterns are compiled without flags; use inline (?i)/(?m) where needed.
# Distilled from Tencent AI-Infra-Guard, getsentry/skills skill-scanner and
# other public skill/MCP scanners, plus the report.pdf attack descriptions.
# --------------------------------------------------------------------------

PATTERNS = [
    # ---------------- network_fetch ----------------
    ("NF_CURL_URL", "network_fetch", "medium", "curl fetching a remote URL",
     r"(?i)\bcurl\s+(?:-[\w-]+\s+|\"[^\"]*\"\s+)*https?://"),
    ("NF_WGET_URL", "network_fetch", "medium", "wget fetching a remote URL",
     r"(?i)\bwget\s+(?:-[\w-]+\s+)*https?://"),
    ("NF_REQUESTS_GET", "network_fetch", "low", "python requests GET",
     r"(?i)\brequests\.(?:get|head|Session)\s*\("),
    ("NF_URLLIB", "network_fetch", "medium", "urllib remote fetch",
     r"(?i)\burllib(?:\.request)?\.(?:urlopen|urlretrieve)\s*\("),
    ("NF_HTTPCLIENT", "network_fetch", "medium", "raw http.client connection",
     r"(?i)\bhttp\.client\.HTTPS?Connection\s*\("),
    ("NF_AIOHTTP", "network_fetch", "low", "aiohttp client",
     r"(?i)\baiohttp\.(?:ClientSession|request)\b"),
    ("NF_HTTPX", "network_fetch", "low", "httpx client",
     r"(?i)\bhttpx\.(?:get|post|Client|AsyncClient)\s*\("),
    ("NF_JS_FETCH", "network_fetch", "medium", "javascript fetch() of a remote URL",
     r"(?i)\bfetch\s*\(\s*[`'\"]https?://"),
    ("NF_AXIOS", "network_fetch", "low", "axios request",
     r"(?i)\baxios(?:\.(?:get|request|create))?\s*\("),
    ("NF_XHR", "network_fetch", "low", "XMLHttpRequest",
     r"\bnew\s+XMLHttpRequest\s*\("),
    ("NF_PS_WEBREQUEST", "network_fetch", "medium", "PowerShell web request",
     r"(?i)\bInvoke-(?:WebRequest|RestMethod)\b"),
    ("NF_PS_IWR", "network_fetch", "high", "PowerShell iwr shorthand download",
     r"(?i)\biwr\s+['\"]?https?://"),
    ("NF_AGENT_FETCH", "network_fetch", "low", "agent web-fetch tool usage",
     r"(?i)\bWebFetch\b|\bweb_fetch\b"),

    # ---------------- network_send ----------------
    ("NS_CURL_DATA", "network_send", "high", "curl uploading a payload",
     r"(?i)\bcurl\b[^\n]{0,160}\s-(?:d\b|-data\b|-data-binary\b|-data-raw\b|F\b|-form\b|T\b|-upload-file\b)"),
    ("NS_CURL_POST", "network_send", "high", "curl POST/PUT request",
     r"(?i)\bcurl\b[^\n]{0,160}-X\s*['\"]?(?:POST|PUT|PATCH)"),
    ("NS_REQUESTS_POST", "network_send", "medium", "python requests POST/PUT",
     r"(?i)\brequests\.(?:post|put|patch)\s*\("),
    ("NS_FETCH_POST", "network_send", "medium", "javascript fetch with POST method",
     r"(?i)\bfetch\s*\([^)]{0,200}method\s*:\s*['\"](?:POST|PUT|PATCH)"),
    ("NS_AXIOS_POST", "network_send", "medium", "axios POST/PUT",
     r"(?i)\baxios\.(?:post|put|patch)\s*\("),
    ("NS_COLLECTOR", "network_send", "critical", "request-capture / collector endpoint",
     r"(?i)\b(?:webhook\.site|requestbin\.\w+|hookbin\.com|pipedream\.net|beeceptor\.com|interact\.sh|oastify\.com|burpcollaborator\.net|dnslog\.cn)\b"),
    ("NS_WEBHOOK_VAR", "network_send", "high", "webhook endpoint used for reporting",
     r"(?i)\b(?:webhook_url|WEBHOOK_URL|webhookUrl)\b"),
    ("NS_EXFIL_WORD", "network_send", "high", "explicit exfiltration wording",
     r"(?i)\bexfiltrat\w+\b|\bexfil\b"),
    ("NS_SEND_PAYLOAD", "network_send", "medium", "sending collected data out",
     r"(?i)\bsend[_\s-]?(?:data|report|payload|beacon|telemetry|results?)\b"),
    ("NS_UPLOAD_LOCAL", "network_send", "high", "local project/files pushed to a remote service",
     r"(?i)\b(?:upload|uploads|uploading|uploaded|transfers?|transmits?)\b[^\n]{0,50}\b(?:project|repo(?:sitory)?|source|codebase|workspace|directory|folder|files?|tarball|archive|database)\b"),
    ("NS_NETCAT_TX", "network_send", "high", "netcat pushing data to a host",
     r"(?i)\bn(?:c|cat)\s+(?:-[a-z]+\s+)*[\w.-]+\s+\d{2,5}\b"),
    ("NS_SCP_OUT", "network_send", "high", "scp upload to a remote host",
     r"(?i)\bscp\s+\S+\s+[\w.-]+@[\w.-]+:"),
    ("NS_SMTP", "network_send", "medium", "SMTP mail sending",
     r"(?i)\bsmtplib\.SMTP\b|\bsendmail\s*\("),

    # ---------------- untrusted_host ----------------
    ("UH_RAW_IP", "untrusted_host", "critical", "URL pointing at a bare IP address",
     r"(?i)\bhttps?://\d{1,3}(?:\.\d{1,3}){3}"),
    ("UH_TUNNEL", "untrusted_host", "critical", "ad-hoc tunnel / relay host",
     r"(?i)\b(?:ngrok\.(?:io|app|dev)|trycloudflare\.com|loca\.lt|serveo\.net|bore\.pub|localtunnel\.me|localhost\.run)\b"),
    ("UH_PASTE", "untrusted_host", "critical", "paste / anonymous file host",
     r"(?i)\b(?:pastebin\.com|paste\.ee|hastebin\.\w+|ghostbin\.\w+|rentry\.co|glot\.io|termbin\.com|transfer\.sh|0x0\.st|file\.io|anonfiles\.com|gofile\.io|bashupload\.com|dpaste\.\w+|controlc\.com)\b"),
    ("UH_SHORTENER", "untrusted_host", "high", "URL shortener hides the real target",
     r"(?i)\bhttps?://(?:bit\.ly|tinyurl\.com|is\.gd|goo\.gl|t\.co|cutt\.ly|rb\.gy|shorte\.st|shorturl\.at|ow\.ly)/"),
    ("UH_EPHEMERAL_PAAS", "untrusted_host", "high", "throwaway PaaS host serving skill assets",
     r"(?i)\bhttps?://[\w.-]+\.(?:vercel\.app|netlify\.app|herokuapp\.com|onrender\.com|glitch\.me|repl\.co|workers\.dev|pages\.dev|fly\.dev|surge\.sh)\b"),
    ("UH_SUSPICIOUS_TLD", "untrusted_host", "high", "URL on an abuse-prone TLD",
     r"(?i)\bhttps?://[\w.-]+\.(?:xyz|top|tk|ml|ga|cf|gq|zip|mov|click|link|icu|lol|cyou|rest|monster|forum|quest|sbs|fun|buzz|website)\b"),
    ("UH_INSTALLER_HOST", "untrusted_host", "high", "generic download/install host of unknown provenance",
     r"(?i)\bhttps?://(?:download|install|setup|update|cdn|dist|files?)[\w-]*\.[\w-]+\.(?:com|net|org|io|dev|app|co)\b"),
    ("UH_USERINFO_URL", "untrusted_host", "high", "credentials embedded in a URL authority",
     r"(?i)\bhttps?://[^\s/@'\"]+:[^\s/@'\"]+@[\w.-]+"),
    ("UH_ONION", "untrusted_host", "critical", "Tor hidden service endpoint",
     r"(?i)\bhttps?://[a-z2-7]{16,56}\.onion\b"),

    # ---------------- binary_download ----------------
    ("BD_EXECUTABLE_URL", "binary_download", "critical", "URL of a directly runnable binary",
     r"(?i)\bhttps?://[^\s'\"<>)]+\.(?:exe|dmg|pkg|msi|msix|appimage|scr|bat|cmd|ps1|jar)\b"),
    ("BD_DOWNLOAD_VERB", "binary_download", "critical", "instruction to download an executable",
     r"(?i)\b(?:download|fetch|grab|get)\b[^\n]{0,80}\.(?:exe|dmg|pkg|msi|deb|rpm|appimage|bin)\b"),
    ("BD_RELEASE_ASSET", "binary_download", "high", "release-asset download link",
     r"(?i)\bhttps?://[^\s'\"<>)]+/releases/download/[^\s'\"<>)]+"),
    ("BD_ARCHIVE_URL", "binary_download", "medium", "archive downloaded from the network",
     r"(?i)\bhttps?://[^\s'\"<>)]+\.(?:zip|tar\.gz|tgz|7z|rar)\b"),
    ("BD_PASSWORD_ARCHIVE", "binary_download", "critical", "password-protected archive (anti-scan packaging)",
     r"(?i)\b(?:extract|unzip|decompress|open)\b[^\n]{0,60}\b(?:using|with)?\s*(?:pass(?:word)?|pwd)\s*[:=`'\"]"),
    ("BD_UNZIP_PASS", "binary_download", "critical", "archive unpacked with an explicit password",
     r"(?i)\bunzip\s+-P\b|\b7z\s+x\s+-p\S|\bRAR\s+x\s+-p\S"),
    ("BD_RUN_EXECUTABLE", "binary_download", "high", "instruction to run a downloaded executable",
     r"(?i)\brun\s+(?:the\s+)?(?:executable|installer|binary|\.exe|downloaded\s+file)\b"),
    ("BD_CHMOD_RUN", "binary_download", "high", "downloaded file made executable and launched",
     r"(?i)\bchmod\s+\+x\s+\S+[^\n]{0,40}(?:&&|;|\n\s*\./)"),

    # ---------------- pipe_to_shell ----------------
    ("PS_CURL_SH", "pipe_to_shell", "critical", "remote script piped straight into a shell",
     r"(?i)\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|k|d|a)?sh\b"),
    ("PS_CURL_INTERP", "pipe_to_shell", "critical", "remote script piped into an interpreter",
     r"(?i)\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:python3?|perl|ruby|node|php)\b"),
    ("PS_IWR_IEX", "pipe_to_shell", "critical", "PowerShell download piped to Invoke-Expression",
     r"(?i)\biwr\b[^\n|]{0,200}\|\s*iex\b|\bInvoke-WebRequest\b[^\n|]{0,200}\|\s*Invoke-Expression\b"),
    ("PS_IEX", "pipe_to_shell", "high", "PowerShell Invoke-Expression of dynamic content",
     r"(?i)\bInvoke-Expression\b|\biex\s*\(\s*\("),
    ("PS_PROC_SUBST", "pipe_to_shell", "critical", "process substitution executing a remote script",
     r"(?i)\b(?:ba)?sh\s+<\(\s*(?:curl|wget)\b"),
    ("PS_CMD_SUBST", "pipe_to_shell", "critical", "command substitution running remote content",
     r"(?i)\$\(\s*(?:curl|wget)\b"),
    ("PS_B64_SH", "pipe_to_shell", "critical", "base64 blob decoded and piped to a shell",
     r"(?i)\bbase64\s+(?:-d|-D|--decode)\b[^\n|]{0,80}\|\s*(?:ba)?sh\b"),
    ("PS_SH_C_REMOTE", "pipe_to_shell", "critical", "sh -c wrapping a remote download",
     r"(?i)\b(?:ba)?sh\s+-c\s+[\"'][^\"']{0,200}(?:curl|wget)\b"),
    ("PS_NPX_REMOTE", "pipe_to_shell", "high", "npx executing a package straight from a URL",
     r"(?i)\bnpx\s+(?:-y\s+)?(?:https?://|git\+)"),

    # ---------------- credential_read ----------------
    ("CR_SSH_DIR", "credential_read", "high", "access to the user's .ssh directory",
     r"(?i)(?:~|\$HOME|%USERPROFILE%)[/\\]\.ssh[/\\]"),
    ("CR_SSH_KEY", "credential_read", "critical", "SSH private key file referenced",
     r"(?i)\bid_(?:rsa|ed25519|ecdsa|dsa)\b"),
    ("CR_AUTHORIZED_KEYS", "credential_read", "high", "authorized_keys manipulation",
     r"(?i)\.ssh[/\\]authorized_keys\b"),
    ("CR_AWS", "credential_read", "critical", "AWS credentials file",
     r"(?i)\.aws[/\\](?:credentials|config)\b"),
    ("CR_DOTFILE_CREDS", "credential_read", "high", "credential dotfile access",
     r"(?i)(?:^|[/\\\s'\"])\.(?:netrc|pgpass|my\.cnf|npmrc|pypirc|git-credentials)\b"),
    ("CR_DOCKER_KUBE", "credential_read", "high", "container/cluster credential file",
     r"(?i)\.(?:docker[/\\]config\.json|kube[/\\]config)\b|\.config[/\\]gcloud\b"),
    ("CR_ENV_FILE", "credential_read", "high", "reading a .env secrets file",
     r"(?i)\b(?:cat|read|open|load|source|copy|cp|type|readFileSync)\b[^\n]{0,40}\.env\b"),
    ("CR_ENV_FILE_PATH", "credential_read", "medium", ".env file referenced as a path",
     r"(?i)(?:^|[/\\\s'\"])\.env(?:\.local|\.production)?\b"),
    ("CR_OAUTH_FILE", "credential_read", "high", "OAuth client-secret / token file",
     r"(?i)\b(?:client_secrets?|credentials|token|oauth[\w-]*)\.json\b"),
    ("CR_KEYCHAIN", "credential_read", "critical", "OS keychain / credential store access",
     r"(?i)\bsecurity\s+find-(?:generic|internet)-password\b|\bkeychain\b"),
    ("CR_SECRET_SERVICE", "credential_read", "high", "Linux secret service access",
     r"(?i)\bgnome-keyring\b|\blibsecret\b|\bsecretstorage\b"),
    ("CR_BROWSER_STORE", "credential_read", "high", "browser credential/cookie store",
     r"(?i)\b(?:Login\s?Data|Local\s?State|places\.sqlite|cookies\.sqlite|Cookies\.binarycookies)\b"),
    ("CR_BROWSER_PROFILE", "credential_read", "high", "browser profile directory access",
     r"(?i)(?:Application\s+Support|AppData)[/\\][^\n]{0,40}(?:Google[/\\]Chrome|Firefox|BraveSoftware|Edge)\b"),
    ("CR_COOKIE_FILE", "credential_read", "high", "cookie jar file access",
     r"(?i)\bcookies?\.(?:sqlite|txt|json|db)\b"),
    ("CR_GNUPG", "credential_read", "high", "GnuPG private keyring access",
     r"(?i)(?:^|[/\\\s'\"])\.gnupg\b"),
    ("CR_AGENT_SESSION", "credential_read", "medium", "agent session/credential store access",
     r"(?i)\.(?:claude|clawdbot|openclaw|cursor|codex)[/\\][^\n]{0,40}(?:sessions?|auth|credential|token)"),
    ("CR_SYSTEM_ACCOUNTS", "credential_read", "critical", "system account database access",
     r"(?i)/etc/(?:passwd|shadow|sudoers)\b"),

    # ---------------- crypto_wallet ----------------
    ("CW_SEED_PHRASE", "crypto_wallet", "critical", "wallet seed / mnemonic phrase",
     r"(?i)\b(?:seed|mnemonic|recovery)\s*(?:phrase|words|key)\b"),
    ("CW_PRIVATE_KEY", "crypto_wallet", "high", "wallet private key handling",
     r"(?i)\bprivate\s*key\b"),
    ("CW_KEYSTORE", "crypto_wallet", "critical", "wallet keystore file",
     r"(?i)\b(?:wallet|keystore)\.(?:dat|json)\b"),
    ("CW_WALLET_APP", "crypto_wallet", "high", "consumer wallet application data",
     r"(?i)\b(?:metamask|phantom|exodus|electrum|ledger\s?live|trust\s?wallet|solflare|keplr)\b"),
    ("CW_BIP39", "crypto_wallet", "medium", "HD wallet derivation material",
     r"(?i)\bBIP-?39\b|\bderivation\s+path\b"),
    ("CW_SECRETKEY_API", "crypto_wallet", "high", "wallet secret-key API usage",
     r"(?i)\bfromSecretKey\b|\bfromMnemonic\b|\bsecretKey\b"),

    # ---------------- credential_in_command ----------------
    ("CIC_AUTH_HEADER", "credential_in_command", "high", "bearer/basic token inlined in a request header",
     r"(?i)Authorization\s*:\s*(?:Bearer|Basic|token)\s+\S{3,}"),
    ("CIC_APIKEY_HEADER", "credential_in_command", "high", "API key passed as a raw header",
     r"(?i)(?:-H|--header)\s+['\"]?(?:x-api-key|api-key|authorization)\s*:"),
    ("CIC_THIRD_PARTY_AUTH", "credential_in_command", "high", "credentials brokered by a third-party service",
     r"(?i)\b(?:handles?|manages?|stores?)\s+(?:your\s+|the\s+|all\s+)?(?:auth(?:entication)?|credentials?|secrets?|tokens?|api\s+keys?)\b[^\n]{0,40}\b(?:automatically|server-side|for\s+you)\b"),
    ("CIC_ECHO_SECRET", "credential_in_command", "critical", "secret printed to output",
     r"(?i)\b(?:echo|print|printf|console\.log|Write-Host)\b[^\n]{0,60}(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)"),
    ("CIC_URL_SECRET", "credential_in_command", "critical", "secret placed in a URL query string",
     r"(?i)\bhttps?://[^\s'\"]*[?&](?:api[_-]?key|access[_-]?token|token|secret|password|passwd)="),
    ("CIC_EXPORT_SECRET", "credential_in_command", "medium", "secret exported into the environment",
     r"(?i)\bexport\s+[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*="),
    ("CIC_ASK_SECRET", "credential_in_command", "high", "user asked to hand over a secret in plain text",
     r"(?i)\b(?:paste|enter|share|provide|send|give)\b[^\n]{0,50}\b(?:your\s+)?(?:api\s*key|access\s*token|password|secret|seed\s*phrase|private\s*key)\b"),
    ("CIC_CLI_SECRET_FLAG", "credential_in_command", "medium", "secret given as a command-line flag",
     r"(?i)--(?:password|token|api-?key|secret)[= ]\S+"),
    ("CIC_ENVIRON_SECRET", "credential_in_command", "medium", "secret pulled out of the environment",
     r"(?i)\bos\.environ(?:\.get)?\s*[\[(]\s*['\"][^'\"]*(?:KEY|TOKEN|SECRET|PASSWORD)"),
    ("CIC_PROCESS_ENV_SECRET", "credential_in_command", "low", "secret pulled out of process.env",
     r"\bprocess\.env\.[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)"),

    # ---------------- env_harvest ----------------
    ("EH_PRINTENV", "env_harvest", "high", "whole environment dumped",
     r"(?i)\bprintenv\b|\benv\s*\|\s*\w|\bset\s*>\s*\S+"),
    ("EH_ENVIRON_DICT", "env_harvest", "critical", "entire os.environ serialised",
     r"(?i)\b(?:dict|json\.dumps|list)\s*\(\s*(?:dict\s*\(\s*)?os\.environ"),
    ("EH_ENVIRON_ITEMS", "env_harvest", "high", "iterating over every environment variable",
     r"(?i)\bos\.environ\.(?:items|keys|values|copy)\s*\("),
    ("EH_PROCESS_ENV_ALL", "env_harvest", "high", "entire process.env serialised",
     r"(?i)(?:JSON\.stringify|Object\.(?:keys|entries|assign))\s*\(\s*process\.env\b"),

    # ---------------- hardcoded_secret ----------------
    ("HS_AWS_AKID", "hardcoded_secret", "critical", "AWS access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("HS_GH_PAT", "hardcoded_secret", "critical", "GitHub token", r"\bgh[pousr]_[0-9A-Za-z]{36}\b"),
    ("HS_GH_FINE", "hardcoded_secret", "critical", "GitHub fine-grained PAT", r"\bgithub_pat_[0-9A-Za-z_]{60,}"),
    ("HS_ANTHROPIC", "hardcoded_secret", "critical", "Anthropic API key", r"\bsk-ant-api\d{2}-[0-9A-Za-z_\-]{80,}"),
    ("HS_OPENAI", "hardcoded_secret", "critical", "OpenAI API key", r"\bsk-[A-Za-z0-9]{20,}T3BlbkFJ[A-Za-z0-9]{20,}"),
    ("HS_SLACK", "hardcoded_secret", "critical", "Slack token", r"\bxox[baprs]-[0-9A-Za-z-]{10,}"),
    ("HS_GOOGLE", "hardcoded_secret", "critical", "Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("HS_GITLAB", "hardcoded_secret", "critical", "GitLab PAT", r"\bglpat-[0-9A-Za-z_\-]{20}\b"),
    ("HS_NPM", "hardcoded_secret", "critical", "npm access token", r"\bnpm_[0-9A-Za-z]{36}\b"),
    ("HS_SENDGRID", "hardcoded_secret", "critical", "SendGrid API key", r"\bSG\.[0-9A-Za-z_\-]{20,}\.[0-9A-Za-z_\-]{40,}"),
    ("HS_STRIPE", "hardcoded_secret", "critical", "Stripe secret key", r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{24,}"),
    ("HS_TELEGRAM_BOT", "hardcoded_secret", "critical", "Telegram bot token", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{33}\b"),
    ("HS_PRIVATE_KEY_BLOCK", "hardcoded_secret", "critical", "embedded private key block",
     r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----"),
    ("HS_DB_URI", "hardcoded_secret", "critical", "database URI with inline password",
     r"(?i)\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp)://[^\s:/@'\"]+:[^\s@'\"]{3,}@"),
    ("HS_JWT", "hardcoded_secret", "high", "JSON Web Token literal",
     r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),
    ("HS_APIKEY_ASSIGN", "hardcoded_secret", "high", "API key assigned to a literal",
     r"(?i)\b(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']"),
    ("HS_PASSWORD_ASSIGN", "hardcoded_secret", "high", "password assigned to a literal",
     r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
    ("HS_SECRET_ASSIGN", "hardcoded_secret", "high", "secret assigned to a literal",
     r"(?i)\bsecret\s*[:=]\s*[\"'][A-Za-z0-9_\-+/]{16,}[\"']"),

    # ---------------- dynamic_exec ----------------
    ("DE_EVAL", "dynamic_exec", "high", "eval() of dynamic content", r"(?<![\w.])eval\s*\("),
    ("DE_EXEC", "dynamic_exec", "high", "exec() of dynamic content", r"(?<![\w.])exec\s*\("),
    ("DE_NEW_FUNCTION", "dynamic_exec", "high", "code built with new Function()", r"\bnew\s+Function\s*\("),
    ("DE_COMPILE", "dynamic_exec", "high", "source compiled at runtime",
     r"(?i)\bcompile\s*\([^)]{0,120}['\"]exec['\"]"),
    ("DE_DYNAMIC_IMPORT", "dynamic_exec", "medium", "dynamic module import",
     r"(?i)\b__import__\s*\(|\bimportlib\.import_module\s*\("),
    ("DE_PICKLE", "dynamic_exec", "high", "pickle/marshal deserialisation",
     r"(?i)\b(?:pickle|cPickle|marshal|dill)\.loads?\s*\("),
    ("DE_YAML_LOAD", "dynamic_exec", "medium", "unsafe YAML load",
     r"(?i)\byaml\.load\s*\((?![^)]*Safe)"),
    ("DE_VM_RUN", "dynamic_exec", "high", "node vm context execution",
     r"(?i)\bvm\.runIn(?:New|This)Context\s*\("),
    ("DE_TIMEOUT_STRING", "dynamic_exec", "medium", "string scheduled as code",
     r"(?i)\bsetTimeout\s*\(\s*['\"]"),

    # ---------------- shell_exec ----------------
    ("SE_OS_SYSTEM", "shell_exec", "high", "os.system command execution", r"(?i)\bos\.(?:system|popen)\s*\("),
    ("SE_SUBPROCESS_SHELL", "shell_exec", "high", "subprocess with shell=True",
     r"(?i)\bsubprocess\.(?:run|call|check_call|check_output|Popen)\s*\([^)]{0,300}shell\s*=\s*True"),
    ("SE_SUBPROCESS", "shell_exec", "medium", "subprocess invocation",
     r"(?i)\bsubprocess\.(?:run|call|check_call|check_output|Popen)\s*\("),
    ("SE_OS_EXEC", "shell_exec", "high", "os.exec* process replacement", r"(?i)\bos\.exec[lv]p?e?\s*\("),
    ("SE_CHILD_PROCESS", "shell_exec", "high", "node child_process usage",
     r"(?i)\bchild_process\b|\brequire\s*\(\s*['\"]child_process['\"]"),
    ("SE_EXECSYNC", "shell_exec", "high", "node exec/spawn call",
     r"(?i)\b(?:execSync|execFileSync|spawnSync|execFile|spawn)\s*\("),
    ("SE_PTY", "shell_exec", "medium", "pseudo-terminal command execution", r"(?i)\bpty\.(?:spawn|openpty)\s*\("),

    # ---------------- reverse_shell ----------------
    ("RS_DEV_TCP", "reverse_shell", "critical", "bash /dev/tcp reverse channel", r"(?i)/dev/tcp/[\w.$-]+/\d+"),
    ("RS_NC_EXEC", "reverse_shell", "critical", "netcat with command execution", r"(?i)\bn(?:c|cat)\s+(?:-\w*\s+)*-\w*e\w*\s"),
    ("RS_BASH_I", "reverse_shell", "critical", "interactive bash redirected to a socket", r"(?i)\bbash\s+-i\s*>&"),
    ("RS_SOCAT", "reverse_shell", "critical", "socat TCP/EXEC relay", r"(?i)\bsocat\b[^\n]{0,40}(?:TCP|EXEC|PTY)"),
    ("RS_MKFIFO", "reverse_shell", "critical", "named-pipe reverse shell", r"(?i)\bmkfifo\b[^\n]{0,80}\|\s*(?:ba)?sh\b"),
    ("RS_SOCKET_CONNECT", "reverse_shell", "high", "raw socket connect to a remote port",
     r"(?i)\bsocket\.socket\s*\([^\n]{0,200}\.connect\s*\("),
    ("RS_PS_ENCODED", "reverse_shell", "critical", "PowerShell encoded command payload",
     r"(?i)\bpowershell\b[^\n]{0,80}-(?:enc|e|EncodedCommand)\b"),
    ("RS_WORDING", "reverse_shell", "critical", "explicit reverse/bind shell wording",
     r"(?i)\breverse\s+shell\b|\bbind\s+shell\b"),

    # ---------------- obfuscation_encoding ----------------
    ("OE_PY_B64", "obfuscation_encoding", "high", "python base64 decode",
     r"(?i)\bbase64\.(?:b64decode|standard_b64decode|urlsafe_b64decode|decodebytes)\s*\("),
    ("OE_ATOB", "obfuscation_encoding", "high", "javascript atob decode", r"\batob\s*\("),
    ("OE_BUFFER_B64", "obfuscation_encoding", "high", "Buffer.from base64 decode",
     r"(?i)Buffer\.from\s*\([^)]{0,120}['\"]base64['\"]"),
    ("OE_CLI_B64", "obfuscation_encoding", "high", "shell base64 decode", r"(?i)\bbase64\s+(?:-d|-D|--decode)\b"),
    ("OE_ROT", "obfuscation_encoding", "high", "rot13 style decoding", r"(?i)\bcodecs\.decode\s*\([^)]{0,60}rot"),
    ("OE_FROMCHARCODE", "obfuscation_encoding", "medium", "string rebuilt from char codes",
     r"(?i)\bString\.fromCharCode\s*\("),
    ("OE_CHR_CHAIN", "obfuscation_encoding", "high", "string assembled from chr() calls",
     r"(?:\bchr\s*\(\s*\d+\s*\)\s*\+\s*){3,}"),
    ("OE_HEX_UNHEX", "obfuscation_encoding", "medium", "hex-encoded payload decoding",
     r"(?i)\bbytes\.fromhex\s*\(|\bunhexlify\s*\(|\bbinascii\.a2b_hex\s*\("),
    ("OE_HEX_ESCAPES", "obfuscation_encoding", "high", "long run of hex escapes",
     r"(?:\\x[0-9a-fA-F]{2}){10,}"),
    ("OE_B64_BLOB", "obfuscation_encoding", "medium", "long base64 blob embedded in text",
     r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{80,}={0,2}(?![A-Za-z0-9+/])"),
    ("OE_COMPRESS", "obfuscation_encoding", "medium", "compressed payload expanded at runtime",
     r"(?i)\b(?:zlib|gzip|lzma|bz2)\.decompress\s*\("),
    ("OE_REVERSE_STR", "obfuscation_encoding", "medium", "string reversed to hide its content",
     r"(?i)\.split\(['\"]{2}\)\.reverse\(\)\.join\(|\[::-1\]"),

    # ---------------- hidden_unicode ----------------
    ("HU_ZERO_WIDTH", "hidden_unicode", "critical", "zero-width / invisible formatting characters",
     "[​-‏⁠-⁤]"),
    ("HU_BIDI", "hidden_unicode", "critical", "bidirectional override characters",
     "[‪-‮⁦-⁩]"),
    ("HU_TAG_BLOCK", "hidden_unicode", "critical", "Unicode Tags block carries invisible ASCII",
     "[\U000e0000-\U000e007f]"),
    ("HU_BOM_INLINE", "hidden_unicode", "low", "zero-width no-break space inside the text", "﻿"),
    ("HU_CYRILLIC_MIX", "hidden_unicode", "high", "Cyrillic homoglyph spliced into Latin text",
     "[a-zA-Z][Ѐ-ӿ]|[Ѐ-ӿ][a-zA-Z]"),
    ("HU_GREEK_MIX", "hidden_unicode", "medium", "Greek homoglyph spliced into Latin text",
     "[a-zA-Z][Ͱ-Ͽ]|[Ͱ-Ͽ][a-zA-Z]"),
    ("HU_PUA", "hidden_unicode", "high", "private-use-area characters", "[-]"),

    # ---------------- hidden_markup ----------------
    ("HM_HTML_COMMENT_INSTR", "hidden_markup", "critical", "instructions hidden in an HTML comment",
     r"(?is)<!--(?:(?!-->).){0,400}\b(?:ignore|instruction|system\s+prompt|you\s+must|do\s+not\s+tell|assistant|agent)\b"),
    ("HM_MD_COMMENT", "hidden_markup", "high", "markdown reference-link comment", r"\[//\]:\s*#\s*\("),
    ("HM_INVISIBLE_IMAGE", "hidden_markup", "medium", "empty-alt image can beacon out",
     r"!\[\s*\]\(\s*https?://[^)]+\)"),
    ("HM_EMPTY_LINK", "hidden_markup", "medium", "empty-text link is invisible when rendered",
     r"(?<!!)\[\s*\]\(\s*https?://[^)]+\)"),
    ("HM_CSS_HIDDEN", "hidden_markup", "critical", "text hidden with CSS",
     r"(?i)style\s*=\s*[\"'][^\"']*(?:display\s*:\s*none|font-size\s*:\s*0|visibility\s*:\s*hidden|color\s*:\s*#?f{3,6}\b)"),
    ("HM_HTML_HIDDEN_ATTR", "hidden_markup", "high", "hidden HTML element", r"(?i)<(?:div|span|p)\b[^>]{0,80}\bhidden\b"),
    ("HM_ENTITY_RUN", "hidden_markup", "high", "text encoded as an HTML entity run",
     r"(?:&#x?[0-9a-fA-F]{2,6};){6,}"),

    # ---------------- instruction_override ----------------
    ("IO_IGNORE_PREVIOUS", "instruction_override", "critical", "ignore previous instructions",
     r"(?i)\bignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier|preceding|foregoing)\s+(?:instructions?|prompts?|rules?|directions?|guidance)"),
    ("IO_DISREGARD", "instruction_override", "critical", "disregard prior instructions",
     r"(?i)\bdisregard\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+\w+"),
    ("IO_FORGET", "instruction_override", "critical", "forget prior instructions or training",
     r"(?i)\bforget\s+(?:all\s+|everything\s+)?(?:previous|prior|your\s+(?:previous|prior|instructions|training))"),
    ("IO_OVERRIDE_SYSTEM", "instruction_override", "critical", "override the system prompt",
     r"(?i)\boverride\s+(?:the\s+)?(?:system|safety|security|previous|default)\s+(?:prompt|message|instructions?|rules?|settings?)"),
    ("IO_NEW_PROMPT", "instruction_override", "critical", "new system prompt injected",
     r"(?i)\bnew\s+(?:system\s+)?(?:prompt|instructions?|directives?)\s*:"),
    ("IO_FROM_NOW_ON", "instruction_override", "high", "temporal instruction override",
     r"(?i)\bfrom\s+now\s+on\s*,?\s*(?:you|ignore|forget|disregard|always|never)\b"),
    ("IO_PRECEDENCE", "instruction_override", "critical", "claims precedence over existing instructions",
     r"(?i)\bthese\s+instructions?\s+(?:take|have)\s+(?:precedence|priority)|\bsupersedes?\s+(?:all\s+)?(?:previous|prior|other)\s+(?:instructions?|rules?)"),
    ("IO_PRIORITY_OVERRIDE", "instruction_override", "critical", "priority-override marker",
     r"(?i)\bPRIORITY\s+OVERRIDE\b|\bOVERRIDE\s+ALL\b|\bHIGHEST\s+PRIORITY\s+INSTRUCTION\b"),
    ("IO_DONT_FOLLOW_USER", "instruction_override", "critical", "told not to follow the user or system",
     r"(?i)\bdo\s+not\s+follow\s+(?:the\s+)?(?:user|previous|system|any\s+other)\b"),
    ("IO_REGARDLESS", "instruction_override", "high", "instruction claims to apply unconditionally",
     r"(?i)\bregardless\s+of\s+(?:what|any)\s+(?:the\s+)?(?:user|system|other\s+instructions?)\b"),

    # ---------------- jailbreak_persona ----------------
    ("JP_DAN", "jailbreak_persona", "critical", "DAN style jailbreak", r"(?i)\bDAN\s+(?:mode|prompt)\b|\bdo\s+anything\s+now\b"),
    ("JP_DEV_MODE", "jailbreak_persona", "critical", "developer/god mode request",
     r"(?i)\benter\s+(?:developer|debug|admin|god|jailbreak)\s+mode\b|\b(?:developer|god)\s+mode\s+enabled\b"),
    ("JP_UNRESTRICTED", "jailbreak_persona", "critical", "act as an unrestricted model",
     r"(?i)\bact\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered|uncensored|amoral|evil|rogue)\b"),
    ("JP_YOU_ARE_NOW", "jailbreak_persona", "high", "role reassignment", r"(?i)\byou\s+are\s+now\s+(?:a|an|in)\s"),
    ("JP_PRETEND", "jailbreak_persona", "high", "pretend-based constraint removal",
     r"(?i)\bpretend\s+(?:that\s+)?you\s+(?:have\s+no|are\s+not|don'?t)\b"),
    ("JP_BYPASS_SAFETY", "jailbreak_persona", "critical", "bypass safety or content controls",
     r"(?i)\bbypass\s+(?:the\s+)?(?:safety|security|content|ethical|guard|filter|moderation)\w*"),
    ("JP_NO_RESTRICTIONS", "jailbreak_persona", "high", "claims no restrictions apply",
     r"(?i)\bwithout\s+(?:any\s+)?(?:restrictions?|limitations|filters?|censorship)\b|\byou\s+have\s+no\s+(?:rules|restrictions|limits|guidelines)\b"),
    ("JP_UNBOUND", "jailbreak_persona", "critical", "declares the model unbound by policy",
     r"(?i)\bno\s+longer\s+bound\s+by\b|\bnot\s+bound\s+by\s+(?:any\s+)?(?:rules|policies|guidelines)\b"),
    ("JP_SIMULATE_AI", "jailbreak_persona", "high", "simulate a model without safeguards",
     r"(?i)\bsimulate\s+an?\s+(?:AI|assistant|model)\s+(?:without|with\s+no)\b"),

    # ---------------- secrecy_directive ----------------
    ("SD_DONT_TELL_USER", "secrecy_directive", "critical", "agent told to hide activity from the user",
     r"(?i)\b(?:do\s+not|don'?t|never)\s+(?:tell|inform|notify|alert|show|reveal|display|disclose|mention\s+(?:this|it)\s+to)\s+(?:the\s+)?(?:user|human|owner|operator)\b"),
    ("SD_WITHOUT_KNOWLEDGE", "secrecy_directive", "critical", "action performed without user knowledge or consent",
     r"(?i)\bwithout\s+(?:the\s+)?(?:user'?s?\s+)?(?:knowledge|awareness|consent|noticing|permission|confirmation|approval)\b"),
    ("SD_SILENTLY", "secrecy_directive", "high", "action described as silent/covert",
     r"(?i)\b(?:silently|quietly|discreetly|covertly|stealthily)\b"),
    ("SD_NO_LOG", "secrecy_directive", "high", "told not to log or report the action",
     r"(?i)\bdo\s+not\s+(?:log|record|mention|output|print|report|echo)\b"),
    ("SD_HIDE_FROM", "secrecy_directive", "critical", "explicitly hides content from someone",
     r"(?i)\bhide\s+(?:this|it|the\s+\w+)\s+from\b|\bkeep\s+(?:this|it)\s+(?:secret|hidden|confidential|between\s+us)\b"),
    ("SD_NO_CONFIRM", "secrecy_directive", "critical", "told to skip asking for permission",
     r"(?i)\bdo\s+not\s+(?:ask|request|prompt)\s+(?:for\s+)?(?:permission|confirmation|approval)\b|\bno\s+need\s+to\s+(?:ask|confirm|inform|tell)\b"),
    ("SD_BACKGROUND_SILENT", "secrecy_directive", "high", "runs in the background without surfacing",
     r"(?i)\bin\s+the\s+background\b[^\n]{0,60}\b(?:without|no\s+(?:output|notification|message))\b"),
    ("SD_WIPE_TRACES", "secrecy_directive", "critical", "removes logs or traces of the action",
     r"(?i)\b(?:delete|remove|clear|wipe)\s+(?:the\s+)?(?:audit\s+)?(?:logs?|history|traces?|evidence)\b"),

    # ---------------- authority_spoof ----------------
    ("AS_SYSTEM_PREFIX", "authority_spoof", "critical", "fake system/admin speaker prefix",
     r"(?im)^\s*(?:SYSTEM|ADMIN|ROOT|DEVELOPER)\s*:\s"),
    ("AS_CHAT_TOKENS", "authority_spoof", "critical", "chat template control tokens injected",
     r"(?i)<\|?(?:system|im_start|im_end|endoftext)\|?>"),
    ("AS_BRACKET_TAG", "authority_spoof", "high", "urgent authority tag",
     r"(?i)\[\s*(?:SYSTEM|IMPORTANT|CRITICAL|MANDATORY|URGENT)\s*\]"),
    ("AS_OFFICIAL_CLAIM", "authority_spoof", "high", "claims official/verified authorisation",
     r"(?i)\bthis\s+is\s+(?:an?\s+)?(?:official|verified|authorized|approved|trusted)\s+(?:instruction|message|skill|request|update)\b"),
    ("AS_VENDOR_CLAIM", "authority_spoof", "critical", "impersonates the model vendor",
     r"(?i)\b(?:Anthropic|OpenAI|the\s+system\s+administrator)\b[^\n]{0,40}\b(?:requires?|mandates?|instructs?|demands?)\b"),
    ("AS_MANDATORY_STEP", "authority_spoof", "high", "step framed as non-negotiable",
     r"(?i)\bmandatory\s+(?:step|action|instruction|requirement|prerequisite)\b"),
    ("AS_MUST_ALWAYS", "authority_spoof", "medium", "strong compulsion directed at the agent",
     r"(?i)\byou\s+MUST\s+(?:always|immediately|first|never)\b"),

    # ---------------- agent_config_write ----------------
    ("AC_SETTINGS_JSON", "agent_config_write", "critical", "agent settings file touched",
     r"(?i)\.(?:claude|clawdbot|openclaw|cursor|codex)[/\\]settings(?:\.local)?\.json"),
    ("AC_MEMORY_WRITE", "agent_config_write", "critical", "agent memory/instruction file written",
     r"(?i)(?:>>?|\bwrite\b|\bappend\b|\becho\b|\bcat\b|\bedit\b|\bmodify\b|\bupdate\b)[^\n]{0,60}\b(?:CLAUDE\.md|AGENTS\.md|MEMORY\.md|\.cursorrules)\b"),
    ("AC_MEMORY_MENTION", "agent_config_write", "medium", "agent instruction file referenced",
     r"(?i)\b(?:CLAUDE\.md|AGENTS\.md|MEMORY\.md|\.cursorrules)\b"),
    ("AC_MCP_CONFIG", "agent_config_write", "high", "MCP server configuration touched", r"(?i)\.mcp\.json\b"),
    ("AC_AGENT_HOME", "agent_config_write", "medium", "agent home directory manipulated",
     r"(?i)(?:~|\$HOME)[/\\]\.(?:claude|clawdbot|openclaw|cursor)[/\\]"),
    ("AC_HOOKS", "agent_config_write", "critical", "agent lifecycle hook installed",
     r"(?i)\b(?:PreToolUse|PostToolUse|SessionStart|UserPromptSubmit|before_tool_call|after_tool_call)\b"),
    ("AC_PERMISSION_ALLOW", "agent_config_write", "high", "agent permission allow-list edited",
     r"(?i)[\"']permissions[\"']\s*:\s*\{[^\n]{0,120}[\"']allow[\"']"),
    ("AC_SKILL_OVERWRITE", "agent_config_write", "critical", "SKILL.md overwritten from an external source",
     r"(?i)(?:curl|wget|fetch)\b[^\n]{0,160}>\s*\S*SKILL\.md\b"),

    # ---------------- shell_config_write ----------------
    ("SC_APPEND_RC", "shell_config_write", "critical", "shell startup file appended to",
     r"(?i)>>\s*\S{0,40}\.(?:bashrc|zshrc|bash_profile|profile|zprofile|zshenv)\b"),
    ("SC_RC_MENTION", "shell_config_write", "medium", "shell startup file referenced",
     r"(?i)(?:^|[/\\\s'\"])\.(?:bashrc|zshrc|bash_profile|zprofile|zshenv)\b"),
    ("SC_SYSTEM_PROFILE", "shell_config_write", "critical", "system-wide shell/sudo config touched",
     r"(?i)/etc/(?:profile(?:\.d)?|rc\.local|sudoers|environment)\b"),
    ("SC_PATH_PREPEND", "shell_config_write", "high", "PATH hijacked with a new directory",
     r"(?i)\bexport\s+PATH\s*=\s*[^\n]{0,40}(?:/tmp|\$HOME/\.\w+)"),

    # ---------------- persistence_scheduling ----------------
    ("PSC_CRONTAB", "persistence_scheduling", "high", "crontab manipulation",
     r"(?i)\bcrontab\s+-[elr]\b|\bcron\s+add\b|\bcrontab\s*<<"),
    ("PSC_CRON_EXPR", "persistence_scheduling", "medium", "cron schedule expression",
     r"(?m)(?:^|['\"\s])(?:[\d*/,-]+\s+){4}[\d*/,-]+(?:['\"\s]|$)"),
    ("PSC_LAUNCHD", "persistence_scheduling", "high", "macOS launch agent persistence",
     r"(?i)\blaunchctl\s+(?:load|bootstrap|enable)\b|\bLaunchAgents?\b|\bLaunchDaemons?\b"),
    ("PSC_SYSTEMD", "persistence_scheduling", "high", "systemd unit persistence",
     r"(?i)\bsystemctl\s+(?:enable|start|daemon-reload)\b|/etc/systemd/system\b"),
    ("PSC_SCHTASKS", "persistence_scheduling", "high", "Windows scheduled task",
     r"(?i)\bschtasks\s+/create\b|\bNew-ScheduledTask\b|\bRegister-ScheduledTask\b"),
    ("PSC_GIT_HOOK", "persistence_scheduling", "critical", "git hook installed",
     r"(?i)\.git[/\\]hooks[/\\](?:pre|post)-(?:commit|push|merge|checkout|receive)\b|\.husky[/\\]"),
    ("PSC_NPM_LIFECYCLE", "persistence_scheduling", "critical", "npm install lifecycle script",
     r"(?i)[\"'](?:pre|post)?install[\"']\s*:\s*[\"']"),
    ("PSC_WIN_RUNKEY", "persistence_scheduling", "critical", "Windows Run registry persistence",
     r"(?i)CurrentVersion\\\\?Run\b|\bHKCU\\Software\\Microsoft\\Windows\b"),
    ("PSC_HEARTBEAT", "persistence_scheduling", "medium", "recurring unattended execution",
     r"(?i)\bheartbeat\b|\bruns?\s+(?:automatically|periodically|unattended|every\s+\d+|in\s+the\s+background)\b"),
    ("PSC_ALWAYS_BACKGROUND", "persistence_scheduling", "high", "declares itself always active",
     r"(?i)\balways\s+(?:running|runs|active)\s+in\s+the\s+background\b"),

    # ---------------- security_disable ----------------
    ("SDS_SKIP_PERMISSIONS", "security_disable", "critical", "agent permission prompts disabled",
     r"(?i)--dangerously-skip-permissions\b|--yolo\b|--no-sandbox\b|--disable-sandbox\b"),
    ("SDS_APPROVALS_OFF", "security_disable", "critical", "approval gate switched off",
     r"(?i)\b(?:approvals?|permissions?|confirmations?)\s*[:=]\s*[\"']?(?:off|false|never|none|bypass|skip)\b"),
    ("SDS_XATTR_QUARANTINE", "security_disable", "critical", "macOS quarantine attribute stripped",
     r"(?i)\bxattr\s+-\w*[dcr]\w*\s[^\n]{0,60}quarantine\b"),
    ("SDS_GATEKEEPER", "security_disable", "critical", "macOS Gatekeeper / SIP disabled",
     r"(?i)\bspctl\s+--master-disable\b|\bcsrutil\s+disable\b|\bGatekeeper\b"),
    ("SDS_DEFENDER", "security_disable", "critical", "Windows Defender weakened",
     r"(?i)\bSet-MpPreference\s+-Disable|\bAdd-MpPreference\s+-ExclusionPath\b"),
    ("SDS_FIREWALL", "security_disable", "critical", "host firewall or SELinux disabled",
     r"(?i)\bufw\s+disable\b|\bsetenforce\s+0\b|\bsystemctl\s+stop\s+firewalld\b|\bnetsh\s+advfirewall\s+set\b[^\n]{0,40}off"),
    ("SDS_TLS_OFF", "security_disable", "high", "TLS verification disabled",
     r"(?i)\bverify\s*=\s*False\b|\bcurl\b[^\n]{0,60}(?:--insecure|\s-k\s)|\bNODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0|\brejectUnauthorized\s*:\s*false"),
    ("SDS_CHMOD_777", "security_disable", "high", "world-writable permissions granted",
     r"(?i)\bchmod\s+(?:-R\s+)?(?:777|a\+rwx)\b"),
    ("SDS_DISABLE_WORDING", "security_disable", "critical", "instruction to disable a protection",
     r"(?i)\bdisable\s+(?:the\s+)?(?:security|antivirus|defender|firewall|sandbox|protection|safety\s+check|guardrails?)\b"),

    # ---------------- privilege_escalation ----------------
    ("PE_SUDO_DANGEROUS", "privilege_escalation", "high", "sudo running a state-changing command",
     r"(?i)\bsudo\s+(?:rm|chmod|chown|curl|wget|bash|sh|npm|pip3?|tee|mv|cp|systemctl|launchctl)\b"),
    ("PE_SUDO", "privilege_escalation", "medium", "sudo invocation", r"(?i)\bsudo\s+-?\w"),
    ("PE_RUNAS", "privilege_escalation", "critical", "Windows elevation request",
     r"(?i)\brunas\s+/user:|\bStart-Process\b[^\n]{0,60}-Verb\s+RunAs\b"),
    ("PE_REQUIRE_ROOT", "privilege_escalation", "high", "skill demands root/administrator rights",
     r"(?i)\brequires?\s+(?:root|administrator|admin|elevated)\s+(?:privileges?|access|permissions?|rights)\b"),
    ("PE_SETUID", "privilege_escalation", "high", "setuid bit manipulation",
     r"(?i)\bchmod\s+(?:u\+s|[24]\d{3})\b|\bsetuid\s*\("),
    ("PE_PKEXEC", "privilege_escalation", "high", "pkexec/gsudo elevation", r"(?i)\bpkexec\b|\bgsudo\b"),
    ("PE_FULL_DISK", "privilege_escalation", "high", "full disk access requested",
     r"(?i)\bfull\s+disk\s+access\b|\bAccessibility\s+permissions?\b"),

    # ---------------- remote_instruction_load ----------------
    ("RIL_FETCH_INSTRUCTIONS", "remote_instruction_load", "critical", "instruction/prompt file pulled from the network",
     r"(?i)\b(?:curl|wget|fetch)\b[^\n]{0,160}\.(?:md|txt|ya?ml|json)\b[^\n]{0,60}>\s*\S*(?:SKILL|HEARTBEAT|PROMPT|INSTRUCTIONS?)"),
    ("RIL_WRITE_SKILL", "remote_instruction_load", "critical", "SKILL.md rewritten from a remote source",
     r"(?i)>\s*[~./][^\s]*SKILL\.md\b"),
    ("RIL_REFETCH_SKILL", "remote_instruction_load", "critical", "skill re-fetches its own definition",
     r"(?i)\bre-?fetch\b[^\n]{0,60}\bskill\b|\bfetch\b[^\n]{0,40}\bskill\s+files?\b"),
    ("RIL_LATEST_INSTRUCTIONS", "remote_instruction_load", "critical", "latest instructions pulled at runtime",
     r"(?i)\b(?:fetch|download|retrieve|pull|load)\b[^\n]{0,60}\b(?:latest|updated?|new|remote)\b[^\n]{0,40}\b(?:instructions?|prompts?|rules?|skills?|config(?:uration)?)\b"),
    ("RIL_AUTO_UPDATE", "remote_instruction_load", "medium", "self-updating behaviour",
     r"(?i)\bauto[-\s]?updat\w+\b|\bcheck\s+for\s+(?:skill\s+)?updates?\b|\bupdate\s+--all\b"),
    ("RIL_REMOTE_PROMPT", "remote_instruction_load", "high", "remote prompt/config drives behaviour",
     r"(?i)\bremote\s+(?:prompt|instructions?|config(?:uration)?|policy)\b"),
    ("RIL_IMPORT_URL", "remote_instruction_load", "critical", "module imported directly from a URL",
     r"(?i)\bimport\b[^\n]{0,40}\bfrom\s+['\"]https?://"),
    ("RIL_PIP_URL", "remote_instruction_load", "high", "package installed from an arbitrary URL/VCS",
     r"(?i)\bpip3?\s+install\s+(?:-e\s+)?(?:git\+|https?://)"),
    ("RIL_NPM_URL", "remote_instruction_load", "high", "npm package installed from a URL/VCS",
     r"(?i)\bnpm\s+(?:i|install)\s+(?:-g\s+)?(?:https?://|git\+)"),

    # ---------------- third_party_content ----------------
    ("TP_SCRAPE", "third_party_content", "medium", "web page content pulled into the agent context",
     r"(?i)\b(?:scrape|crawl|fetch|retrieve)\b[^\n]{0,40}\b(?:page|web\s?page|website|url|html|content)\b"),
    ("TP_SOCIAL", "third_party_content", "medium", "user-generated platform content ingested",
     r"(?i)\b(?:youtube|twitter|x\.com|reddit|linkedin|discord|telegram|instagram|tiktok|facebook|hacker\s?news)\b[^\n]{0,60}\b(?:fetch|read|scrape|download|transcript|comments?|posts?|messages?|threads?|dms?)\b"),
    ("TP_BROWSER_NAV", "third_party_content", "medium", "headless browser navigating to external pages",
     r"(?i)\b(?:page|browser)\.(?:goto|navigate|url)\s*\(|\bplaywright\b|\bpuppeteer\b|\bselenium\b"),
    ("TP_SUMMARIZE_URL", "third_party_content", "medium", "external document summarised into context",
     r"(?i)\b(?:summari[sz]e|analy[sz]e|process|read)\b[^\n]{0,40}\b(?:url|web\s?page|article|website|comments|feed|transcript)\b"),
    ("TP_GIT_CLONE", "third_party_content", "medium", "external repository cloned and inspected",
     r"(?i)\bgit\s+clone\s+(?:https?://|git@)"),
    ("TP_MAILBOX", "third_party_content", "medium", "third-party message store ingested",
     r"(?i)\breads?\s+(?:the\s+)?(?:emails?|inbox|messages?|issues?|pull\s+requests?|tickets?)\b"),
    ("TP_RSS", "third_party_content", "low", "feed content ingested", r"(?i)\brss\s+feed\b|\bfeedparser\b"),

    # ---------------- data_collection ----------------
    ("DC_MESSENGER_DB", "data_collection", "high", "local messenger database read",
     r"(?i)\b(?:wechat|whatsapp|telegram|signal|imessage|slack|discord)\b[^\n]{0,60}\b(?:sqlite|database|\.db\b|chat\s?history|export|messages?)\b"),
    ("DC_MSG_DB_FILE", "data_collection", "high", "chat database file referenced",
     r"(?i)\b(?:Chat(?:Msg)?|Session|Contact|MSG\d*|msg_\d+)\.(?:sqlite|db)\b"),
    ("DC_SCREENSHOT", "data_collection", "high", "screen capture",
     r"(?i)\b(?:screenshot|screencapture|ImageGrab|scrot|CGDisplayCreateImage)\b"),
    ("DC_KEYLOG", "data_collection", "critical", "keystroke capture",
     r"(?i)\bpynput\b|\bkeyboard\.Listener\b|\bkeylog\w*\b|\bCGEventTap\b"),
    ("DC_GUI_AUTOMATION", "data_collection", "medium", "GUI automation of the user's desktop",
     r"(?i)\bpyautogui\b|\bosascript\b|\bAppleScript\b"),
    ("DC_MAC_PRIVATE", "data_collection", "high", "private macOS user data directory",
     r"(?i)~/Library/(?:Messages|Mail|Safari|Keychains)\b"),
    ("DC_BROWSER_HISTORY", "data_collection", "high", "browser history database",
     r"(?i)\bHistory\.(?:db|sqlite)\b|\bplaces\.sqlite\b|\bWebCacheV\d+\.dat\b"),
    ("DC_CONTACTS", "data_collection", "medium", "contact list extraction",
     r"(?i)\b(?:contacts?|address\s?book)\b[^\n]{0,40}\b(?:export|dump|read|list|extract)\b"),

    # ---------------- messaging_exfil ----------------
    ("ME_TELEGRAM", "messaging_exfil", "critical", "Telegram bot API used as a channel",
     r"(?i)\bapi\.telegram\.org/bot\S*"),
    ("ME_DISCORD_HOOK", "messaging_exfil", "critical", "Discord webhook used as a channel",
     r"(?i)\bdiscord(?:app)?\.com/api/webhooks/\S*"),
    ("ME_SLACK_HOOK", "messaging_exfil", "critical", "Slack incoming webhook used as a channel",
     r"(?i)\bhooks\.slack\.com/services/\S*"),
    ("ME_MAIL_API", "messaging_exfil", "high", "transactional mail API used as a channel",
     r"(?i)\b(?:api\.sendgrid\.com|api\.mailgun\.net|api\.resend\.com|api\.postmarkapp\.com)\b"),
    ("ME_MAILTO_BODY", "messaging_exfil", "high", "prefilled mailto payload",
     r"(?i)\bmailto:[^\s\"'<>]+\?[^\s\"'<>]*body="),
    ("ME_SEND_EMAIL", "messaging_exfil", "medium", "programmatic email dispatch",
     r"(?i)\bsend[_\s-]?email\b|\bsmtp\.(?:sendmail|send_message)\b"),
    ("ME_CLI_SEND", "messaging_exfil", "medium", "CLI sending messages on the user's behalf",
     r"(?i)\b(?:gmail|mail|whatsapp|telegram|slack|discord|sms|imessage)\s+send\b|\bsend\s+(?:text|message|file)\s+--to\b"),

    # ---------------- destructive_fs ----------------
    ("DF_RM_RF_ROOT", "destructive_fs", "critical", "recursive delete of home or root",
     r"(?i)\brm\s+-[a-z]*r[a-z]*f?\s+(?:/|~|\$HOME|\*)(?:\s|$)"),
    ("DF_RM_RF", "destructive_fs", "high", "recursive force delete", r"(?i)\brm\s+-[a-z]*r[a-z]*f\b"),
    ("DF_SHRED", "destructive_fs", "critical", "secure wipe of data",
     r"(?i)\bshred\s+-|\bdd\s+if=/dev/(?:zero|urandom)\s+of=/dev/"),
    ("DF_WIN_DELETE", "destructive_fs", "high", "Windows recursive force delete",
     r"(?i)\bdel\s+/[fqs]\b|\bformat\s+[a-z]:\b|\bRemove-Item\b[^\n]{0,60}-Recurse\b[^\n]{0,20}-Force\b"),
    ("DF_MKFS", "destructive_fs", "critical", "filesystem/disk destruction",
     r"(?i)\bmkfs(?:\.\w+)?\s|\bfdisk\s+/dev/|\bdiskutil\s+erase"),
    ("DF_HISTORY_WIPE", "destructive_fs", "critical", "shell history destroyed",
     r"(?i)\bhistory\s+-c\b|>\s*~/\.bash_history\b"),
    ("DF_GIT_FORCE", "destructive_fs", "medium", "destructive git operation",
     r"(?i)\bgit\s+push\s+(?:--force|-f)\b|\bgit\s+reset\s+--hard\b|\bgit\s+clean\s+-\w*[dfx]"),

    # ---------------- typosquat_package ----------------
    ("TS_CUSTOM_NPM_REGISTRY", "typosquat_package", "critical", "npm pointed at a non-official registry",
     r"(?i)--registry[= ]https?://(?!registry\.npmjs\.org)|\bnpm\s+config\s+set\s+registry\b"),
    ("TS_CUSTOM_PYPI", "typosquat_package", "critical", "pip pointed at a non-official index",
     r"(?i)--(?:extra-)?index-url[= ]https?://(?!pypi\.org|files\.pythonhosted\.org)"),
    ("TS_NPMRC_FETCH", "typosquat_package", "high", ".npmrc rewritten from the network",
     r"(?i)\b(?:curl|wget|echo)\b[^\n]{0,80}\.npmrc\b"),
    ("TS_GLOBAL_INSTALL", "typosquat_package", "low", "global package install",
     r"(?i)\bnpm\s+(?:i|install)\s+-g\s+\S+|\bpip3?\s+install\s+(?:--user\s+)?[a-z][\w.-]*"),
    ("TS_CURL_INSTALL_SCRIPT", "typosquat_package", "high", "vendor install script executed from the network",
     r"(?i)\bhttps?://[^\s'\"]+/(?:install|setup|get)(?:\.sh|\.py)?(?![\w/-])"),

    # ---------------- cloud_metadata ----------------
    ("CM_AWS_IMDS", "cloud_metadata", "critical", "AWS instance metadata endpoint", r"\b169\.254\.169\.254\b"),
    ("CM_GCP_META", "cloud_metadata", "critical", "GCP metadata endpoint",
     r"(?i)\bmetadata\.google\.internal\b|\bcomputeMetadata/v1\b"),
    ("CM_AZURE_META", "cloud_metadata", "critical", "Azure IMDS endpoint",
     r"(?i)\bmetadata/identity/oauth2/token\b"),

    # ---------------- tool_permission ----------------
    ("TPM_ALLOWED_TOOLS_ALL", "tool_permission", "critical", "skill requests every tool",
     r"(?im)^\s*allowed-tools\s*:\s*[^\n]*\*"),
    ("TPM_BASH_WILDCARD", "tool_permission", "critical", "unrestricted Bash permission",
     r"(?i)\bBash\(\s*:?\s*\*\s*\)"),
    ("TPM_ALLOW_STAR", "tool_permission", "critical", "permission allow-list set to wildcard",
     r"(?i)[\"']allow[\"']\s*:\s*\[\s*[\"']\*[\"']"),
    ("TPM_BROAD_TOOLS", "tool_permission", "high", "broad write/exec tool grant in frontmatter",
     r"(?im)^\s*allowed-tools\s*:\s*[^\n]*\b(?:Bash|Write|Edit|WebFetch)\b[^\n]*\b(?:Bash|Write|Edit|WebFetch)\b"),

    # ---------------- mandatory_install ----------------
    ("MI_MUST_INSTALL", "mandatory_install", "high", "install demanded before the skill will work",
     r"(?i)\b(?:must|need\s+to|have\s+to|required\s+to)\s+(?:be\s+)?(?:install|download|run|execute)\w*\b[^\n]{0,80}\b(?:before|prior\s+to|first)\b"),
    ("MI_BEFORE_USING", "mandatory_install", "high", "precondition gate before using the skill",
     r"(?i)\bbefore\s+using\s+this\s+skill\b|\bmust\s+be\s+installed\s+before\b"),
    ("MI_WONT_WORK", "mandatory_install", "high", "skill claims it is useless without an external component",
     r"(?i)\bwill\s+not\s+(?:work|function|operate)\b[^\n]{0,60}\bwithout\b|\bwithout\s+\S+\s+installed\b"),
    ("MI_PREREQ_DOWNLOAD", "mandatory_install", "medium", "prerequisite section pushing a download",
     r"(?i)\bprerequisites?\b[\s\S]{0,200}?\b(?:download|install)\b[^\n]{0,60}https?://"),
    ("MI_REQUIRED_COMPONENT", "mandatory_install", "high", "external component declared required for the skill",
     r"(?i)\b(?:is|are)\s+required\s+(?:for|to|before)\b[^\n]{0,60}\b(?:skill|work|works|function|use|using|proceed|operate)\b"),
    ("MI_SETUP_LINK", "mandatory_install", "high", "setup pointer to an external page",
     r"(?i)\b(?:quick\s+)?(?:setup|install(?:ation)?|download)\s+(?:here|link|guide|page)\b[^\n]{0,40}https?://"),
    ("MI_PASTE_TERMINAL", "mandatory_install", "critical", "user told to paste a command into a terminal",
     r"(?i)\b(?:copy|paste)\b[^\n]{0,80}\b(?:command|this)\b[^\n]{0,60}\b(?:terminal|shell|command\s+prompt)\b|\bpaste\s+(?:this|it)\s+into\s+(?:the\s+)?terminal\b"),
]

COMPILED = [(rid, grp, lvl, desc, re.compile(pat)) for rid, grp, lvl, desc, pat in PATTERNS]


# --------------------------------------------------------------------------
# CodeQL query id -> (group, level).  Query sources live in codeql/queries/.
# --------------------------------------------------------------------------

CODEQL_RULES = {
    "malskill/py/credential-exfiltration": ("credential_read", "critical"),
    "malskill/py/remote-code-execution": ("dynamic_exec", "critical"),
    "malskill/py/decoded-payload-execution": ("obfuscation_encoding", "critical"),
    "malskill/py/sensitive-file-exfiltration": ("credential_read", "critical"),
    "malskill/js/credential-exfiltration": ("credential_read", "critical"),
    "malskill/js/remote-code-execution": ("dynamic_exec", "critical"),
    "malskill/js/decoded-payload-execution": ("obfuscation_encoding", "critical"),
    "malskill/js/sensitive-file-exfiltration": ("credential_read", "critical"),
}


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def max_level(levels):
    return max(levels, key=lambda lv: LEVEL_RANK[lv])


def score_claim(claim_type, findings, skill_groups):
    """Score one claim.

    Count-independent: inside a group only the highest level counts.  Across
    groups the semantic synergies add a bonus.  `skill_groups` is the set of
    every group seen anywhere in the skill, so a synergy may pair groups that
    ended up in two different claims.
    """
    per_group = {}
    for f in findings:
        g = f["group"]
        if g not in per_group or LEVEL_RANK[f["level"]] > LEVEL_RANK[per_group[g]]:
            per_group[g] = f["level"]

    bonuses = [(a, b, lv) for a, b, t, lv in SYNERGIES
               if t == claim_type and a in skill_groups and b in skill_groups]

    score = sum(LEVEL_SCORE[lv] for lv in per_group.values())
    score += sum(BONUS_SCORE[lv] for _, _, lv in bonuses)
    return score, per_group, bonuses
