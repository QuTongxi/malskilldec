"""Denoising pass in front of the generator.

The static layer is a pattern matcher, so a share of its findings are matches on
something the pattern does not describe: a filename that looks like a call, a
`venv` directory read as an `.env` file, a tool named inside prose.  One LLM
call per batch of findings drops those and nothing else -- no judgement on how
dangerous a real match is.  Surviving findings are regrouped and re-scored.
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generator import helper
from llm import chat_model

MAX_FINDINGS = 10

SYSTEM_PROMPT = """\
你的工作是从一次针对 AI agent skill 的正则扫描结果里，剔除那些误命中的条目。每个条目包含
一处命中、这条规则所指的行为，以及命中处周围的源文本。

对每个条目，你只判断一件事：这段源文本里是不是真的存在规则所描述的那个行为。凡是真实的
构造、指令或可操作的示例，一律保留。它的用意是什么、安全不安全、严重到什么程度，都不在
本次任务的范围内。

只有当命中的那些字眼并不表达该行为时，才把条目标记为噪声：

- 只是某个文件、目录、变量、字段或标识符的名字长得像（`env/`、`venv/`、`download.py`、
  `install_helper`、一个叫 `password` 的列）；
- 只是正文、标题、更新日志或链接文字提到了某个工具或概念，并没有推荐、演示或实现它；
- 源文本明确把这一行当作"不要这样做"的反例，或者它只是没有生命的测试数据、fixture、
  被注释掉的代码，而不是一条指令；
- 看上去的那个值其实只是占位符（`<YOUR_API_KEY>`、`sk-xxxxxxxx`、
  `password = "changeme"`），而这条规则要成立必须有一个真实内嵌的值；
- 这段文字属于许可证、lockfile 或随包携带的第三方依赖，描述的是那个第三方包而不是本
  skill。

以下都要保留：作为 skill 工作流展示出来的命令、能跑起来的代码、安装与初始化步骤、写给
agent 或用户的指令。哪怕它们看起来很平常、需要机器上并不存在的软件或凭据、在当前机器上
多半会失败，也要保留。只要上下文给两种读法都留了余地，就保留。

收到多少个序号，就返回多少条结果。"""

HUMAN_PROMPT = """\
Skill：{skill}

{items}

看整段话的意思，不要只看命中的那个词。像 "silently ignores" 这类正常措辞、只出现在文件
首字符的 BOM、构建产物或缓存里的碎片、程序启动时例行的日志清空与轮转，都是噪声——哪怕
那个日志里存着上一次运行的内容。只有当上下文确实是在指使 agent 隐藏、注入或抹除某个动作
以掩盖发生过什么时，这类命中才要保留。安装脚本里在正式干活之前的 `: > "$LOG_FILE"`，
就是上面说的那种普通日志初始化，属于噪声。

把这 {count} 个条目全部分类。"""


class Judgement(BaseModel):
    index: int = Field(description="被判断的那个条目的序号")
    noise: bool = Field(description="当这处命中并不表达规则所指的行为时为 true；下列情形必须为 true：'silently' 一类的普通语法、只在首字符出现的 BOM、构建产物、启动时例行的日志清空（哪怕旧记录被删掉了）；只有当上下文是在指使隐藏某个动作时，删日志才保留")
    reason: str = Field(description="一句话说明")


class Judgements(BaseModel):
    judgements: list[Judgement] = Field(description="每个条目一条结果，按给定顺序")


def render(findings):
    blocks = []
    for i, f in enumerate(findings):
        blocks.append(
            "[%d] rule: %s -- %s\n"
            "    behaviour group: %s\n"
            "    location: %s:%d\n"
            "    matched: %s\n"
            "    context:\n%s"
            % (i, f["metadata"]["rule_id"], f["metadata"]["description"], f["group"],
               f["location"]["file"], f["location"]["line"],
               f["matched_text"][:200],
               "\n".join("      " + line for line in f["context"].splitlines()[:20]))
        )
    return "\n\n".join(blocks)


def denoise(skill, timeout, recursive):
    """Return the skill with noise findings removed and its claims re-scored."""
    findings = {}
    for claim in skill["claims"]:
        for finding in claim["findings"]:
            findings[finding["metadata"]["id"]] = finding
    findings = list(findings.values())

    agent = create_agent(
        chat_model(temperature=0.0, timeout=timeout),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(Judgements),
    )

    kept, dropped = [], []
    for start in range(0, len(findings), MAX_FINDINGS):
        batch = findings[start:start + MAX_FINDINGS]
        state = agent.invoke(
            {"messages": [HumanMessage(content=HUMAN_PROMPT.format(
                skill=skill["skill"], items=render(batch), count=len(batch)))]},
            config={"recursion_limit": recursive},
        )
        noise = {j.index for j in state["structured_response"].judgements if j.noise}
        for i, finding in enumerate(batch):
            (dropped if i in noise else kept).append(finding)

    return {
        "skill": skill["skill"],
        "path": skill["path"],
        "n_findings": len(kept),
        "n_dropped": len(dropped),
        "dropped": [{"id": f["metadata"]["id"], "rule_id": f["metadata"]["rule_id"],
                     "location": f["location"]} for f in dropped],
        "claims": helper.rebuild_claims(skill, kept),
    }
