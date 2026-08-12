这个文档指导你撰写动态验证部分，动态验证部分与之前的版本差别不大，只是这一次简化一些逻辑而已。
你可以去读我之前的代码/workspace/for-chatgpt/experiment/code了解具体的金丝雀系统
动态验证的作用依然是通过执行验证静态结论并暴露执行证据。
generator和reviewer的代码量应该更少，这两个更多的是提示词怎么写，然后tester本身代码也不多，主要是docker搭建.
如果你没有langchain和deepagent的skill，你需要给自己安装一下然后使用它们。

### 生成器generator
生成器是langchain的Agent,其不需要具有任何的tool,生成器的主要难点是提示词的撰写。

进入核心逻辑之前，生成器需要一个去噪模块，这个模块需要去掉那些明显匹配错误的内容，这里不做任何价值判断，仅仅是去掉那种噪声匹配，比如把文件名称识别成危险代码，把一个环境文件venv识别成了env文件这种。

生成器需要有 8 份精心制作的提示词，如果你不知道一个好的提示词的样子，你可以读一下https://github.com/Tencent/AI-Infra-Guard，https://github.com/getsentry/skills/tree/main/skills/skill-scanner中的提示词，注意是参考写法而不是让你写内容一样的！

这8份提示词需要紧扣 @report.pdf 中的8个类型定义！你可以大大方方抄写那个报告的任何内容，因为那个是公开的权威报告！

提示词主要包括：概念介绍，例子，用于测试器的提示词撰写说明与模板，用于判断检测是否完成的oracle，禁令说明.同时我们的设计决定生成器一次性看到的不只是1条静态事实，而是多条来自不同组的事实，因此提示词需要注意要让生成器能组合这些东西，或者在无法组合的时候设计单独路径去检测。这里就要根据每个恶意类型的具体内容去组织提示词了，比如提示词注入的核心在与Agent是不是会被诱导，那么我们应该给一个相关的但是无法指导具体执行的输出，去看是否会触发对应的事件，而对于恶意代码，则应该给一个确切的任务目标。这里不是必须把内容执行完才算成功，而是只要尝试执行，有这个动作了就算成功。

禁令说明：我们要禁止生成器产生明显不符合人类用语的，自带指令执行的，自带大段代码的，带有测试语义的，具体指明skill内容的话语。也就是说，用于测试器的提示词撰写说明与模板是从正面介绍和约束，禁令说明是负面约束，我们必须保证生成内容是中性模拟用户输入。

生成器后面要设计小的正则门控，用来拦截那种明显不符合要求的提示词。

#### 输入输出与文件位置

generator位于dynamic/generator/目录，这个目录包括：
 - generator.py 生成器核心代码，用langchain
 - prepare.py 生成器核心逻辑之前的去噪LLM
 - helper.py 放置正则门控具体实现和评分，排序等具体工具实现
 - guides/ 8个提示词，每个都是一个markdown文档

prepare LLM的输入：静态的findings,每次max_findings=10,输出一个判别矩阵，能实现正确筛选即可，可以是数组，字典等任意形式。
prepare阶段输出：去掉噪声匹配之后的指控组，需要重新评分与排序。不要复用静态的代码，把代码复制过来确保这些东西能分开运行。

generator.py输入应该包括：
 - 一个指控，不需要危险等级，不需要元数据，不需要评分，LLM只需要看到findings的组别名称，每个finding的带有上下文的context，以及location三元组即可，其他字段都是浪费宝贵的提示词空间。
 - skill.md原文，虽然指控可能指向skill的其他文件，但是用户对skill的了解一般不超过md,给生成器完整目录只会导致生成器得到多余的知识然后产出不合格输出，因此这里只给原文。
 - guide markdown：对应的指导提示词

这里注意输入不应该超过llm的允许上限，这里我们的方案就是做错误处理，如果报错的时候发现是超出上限了（你可以直接尝试匹配这种文字）就裁剪findings,去掉等级是low的findings,还不行的话就去掉等级medium,再不行就直接汇报验证失败。

generator.py LLM输出
 - prompt：用于tester的提示词
 - oracle：用于reviewer的判断准则

LLM输出：
LLM的输出应该通过pydantic进行自动校验，langchain与pydantic合作可以实现自动的校验失败后重新生成。

阶段输出，阶段输出应该在LLM基础上增加metadata字段，用来标记诸如skill名称，位置，当前指控，线程信息等。

### 验证器tester

tester的难点主要是如何写docker监控工具，tester本身是deepagent,然后使用其内置终端工具，但是要去掉那个subagent的工具——自智能体会导致我们难以监控。tester全程在docker里面跑，我们是把代码写好放进docker里面，然后通过docker指令去启动。用到的配置项目只有timeout,recursive,prompt.

我们需要用代码控制docker image以及container生成，因为我们要绑定skill.注意deepagent要给skill的父目录，例如要连接skill test-skill,你需要给一个这样的目录结构 skills/test-skill/ ，把skills暴露给deepagent去连接。测试的时候只放置那个skill自身，不要有其他skill干扰。

需要监控：
文件系统变化，执行过程，LLM输出，网络访问
这里文件系统变化和网络访问需要你自己写代码或者利用相关工具，这里我不是很擅长，请你自己抉择，注意核心是实现功能即可，力求代码简洁高效（如果利用docker或者其他工具的话是可以的，只要我们自己写的部分简洁高效即可）

对于执行过程则是通过为deepagent的内置tool添加中间件来实现，这样就能看到每次工具执行内容以及结果了，这里工具结果只需要知道执行是否成功即可，对于工具输出可以只保留前100字符。

然后LLM输出就没什么说的了，就是那个tester返回的内容。

这里我们由于后续要把这些内容给reviewer看，因此注意篇幅，尤其是文件，网络这些，文件系统只看差异且对于那种一个目录大量文件变化应该去裁剪细节，然后对于那种可能执行代码的时候，由于编译等导致的文件变化应该ignore,就如同gitignore一样我们也要忽视掉那些噪音目录。网络也是，一次真实网络访问可以由于网站的图片，文字很多，产生一大堆需求，那么这里我们可以只监控request，然后对于response能看到的话那就保留前面几级url就可以，看不到那就不管了。

#### 目录结构

- dynamic/tester
  - build/ 这个目录放docker file,内部的金丝雀文件，注意要在docker中下载安装好curl,git,webget,nodes,python等等装机必备工具！
  - build_docker.py 这个脚本实现复制文件，填充模板等，建立docker image和container,以及这些东西的生命周期管理的具体实现。
  - run_test.py 实现单独可执行的这个验证器Agent,从而可以被放到container里面执行
  - monitor/ 监控器目录，这个监控器可以放到docker内部执行，也可以放到外部，怎样实现更简洁高效就怎样做，然后具体放置几个脚本或者工具就你自己决定了。
  - tester.py 顶层模块，实现完整逻辑，对外部暴露的接口只有 timeout,recursive,prompt 三个输入

#### 输入输出

只需要三个参数timeout,recursive,prompt，输出则是四个字段：文件系统变化，执行过程，LLM输出，网络访问 以及metadata

### Reviewer 

reviewer的任务是结合运行中的证据判断生成器oracle是否证实。我们验证的是“是否具有执行恶意的能力”，当然这个工件的质量取决于生成器的8提示词中的oracle模板了。
这里不需要特别多的额外提示词，只要告诉reviewer结合tester输出判断oracle,然后tester的llm输出是不可信字段
以及就是不关心执行是否完成，只要尝试了，哪怕失败也认为confirmed

llm输入：
生成器prompt,oracle,tester四个字段，skill.md原文（先保留，如果后面发现reviewer因此有幻觉或者被攻击再去掉）

llm输出：
（pydantic+langchain）
 - verdict：confirmed/not trigger
 - summary：如果confirmed这里就总结一下现在的全部工作，说明这样判决的原因；如果是not trigger，则总结文件系统变化，执行过程，LLM输出，网络访问情况，这段总结会用于生成器让其结合总结调整prompt或者oracle策略。

reviewer输出：
llm输出+metadata

#### 文件结构
- dynamic/reviewer/reviewer.py 就一个文件足够了

### 执行逻辑

实现这个loop,以及执行预算round=3

代码放在 dynamic/pipeline.py 中，这个要能单独终端执行，也就是

uv run python dynamic/pipeline.py --round 3 --tester-recursive 20 --tester-timeout 20 --loop-recursive 50 --loop-timeout 20 --static-report path/to/report --out path/to/save --max-parallel 8

整体逻辑就是处理好输入顺序，为skill和指控排个序，然后建立并分配docker container,然后给skill分配docker,按照指控开始执行生成-验证-审查的loop,直到round耗尽或者confirmed.

这里的重点是管理docker的生命周期以及统筹LLM Agent的合作与分工。

【警告】目前动态执行的逻辑还没完善，因为最终判决模块还没有写出来，完整流程是在round耗尽或者confirmed之后加上一个最终判决LLM,给出Malicious或者Benign的二元判决，当判断为Malicious的时候结束对一个skill的审计，判断为Benign的时候审计下一个指控！目前你可以放置一个占位最终审计，让其判定永远是Benign来测试我们的逻辑是否完整。

### 通用
generator和Reviewer的超时时间为20秒，recursive为50,generator的温度是0.2,reviewer是0.0.
需要能并行执行，同时8个skill并行，每个skill的指控检验是串行，skill不同指控检验不需要重置docker,更换skill之后需要重置。

docker搭建：这里依然是需要金丝雀文件系统的，以及docker中的完整权限（无密码的sudo确保可以执行sudo指令），然后完整的网络能力。

这里其实逻辑改动不大，只有那个【警告】内容是逻辑层面改动，其他都是代码简化或者字段和目录明确！

openai_model=qwen3-max
openai_api_url=https://dashscope.aliyuncs.com/compatible-mode/v1
openai_api_key=sk-c0d3d24b6eab4b9fbbf654c2a8817980

这些信息已经放在 .env 文件里面了。

### 代码要求

禁止撰写无意义代码，无意义错误处理，无意义逻辑，复杂无用字段，莫名其妙try-except或者莫名其妙if.用户一定按照契约处理输出，我们是科研项目不是工程！

代码要简洁但是不偷工减料，按照要求实现，注重可读性，也就是让人一眼能看懂而不是工程上要求的那种封装，严密！

禁止先给我设计v1或者先设计小框架，实验版！直接按照要求设计，不可以是写一点点！

### 测试要求

不需要写pytest！写完所有代码之后再测试，测试的时候真实启用LLM和Docker,选择2个有较多静态指控的skill跑一次就可以了，能跑通所有内容就说明代码没有问题了。注意效率问题，这里timeout是利用langchain或者deepagent的内部api完成，是控制LLM api两次回复之间不间隔超过timeout！程序如果长时间（1 min）没有输出就说明可能卡住了，以及就是这个并行，测试的时候开启2并行即可。
