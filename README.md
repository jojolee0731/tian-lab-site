# Tian Lab Website

科研内容优先的静态网站，包含英文、中文和西班牙语三种语言。每种语言有首页、研究方向、研究成果、团队、加入、学术合作和新闻归档七个页面；34 名成员各有三语个人主页，共 123 个公开内容页面。另有需要登录的成员工作台 `members/`，不列入公开站点地图。

公开页面的正文、成员和论文直接写入生成后的 HTML。公开前台 JavaScript 负责导航折叠、论文筛选、旧锚点兼容等渐进增强；关闭 JavaScript 仍能阅读页面和使用普通链接。成员工作台则需要 JavaScript 和 Supabase 登录服务，私有草稿经审核与发布后才进入公开静态文件。

## 版本与线上入口

截至2026-09-20，真实管理员已完成登录，并通过正式网站管理员界面为34位现有成员开通权限；重新加载后已核对每人的邮箱与本人ID对应，34位成员均可编辑本人主页，其中33位为 `member`，1位按用户明确授权兼任 `admin`。原独立管理员保留，共2位管理员、35条访问记录；角色变更后已重新加载核对。此次开通未创建 Auth 用户、未发送邀请邮件；成员可使用已登记邮箱自行请求验证码登录。

管理员实际点击发布按钮，经 Edge 触发的[发布任务35478645703](https://github.com/jojolee0731/tian-lab-site/actions/runs/35478645703)构建与部署均成功。当前获批个人内容仍为0条；真实成员首次登录、草稿、上传、提交、审核及非空内容发布仍待实际使用验证，本地测试结果不替代这些云端流程。

历史部署记录（2026-09-19）：Pages 切换为 GitHub Actions（`build_type: workflow`），[首次 main push 部署](https://github.com/jojolee0731/tian-lab-site/actions/runs/35452195446)和[专用 PAT 调度](https://github.com/jojolee0731/tian-lab-site/actions/runs/35452251756)均成功；后者的bot提交 `ae2838b` 仅规范化空目录格式。3项云端迁移、邀请检查 Hook、QQ SMTP和两类验证码模板已配置，线上角色、Logo及 `enabled: true` 已核对。

单仓库 Actions 发布令牌已保存到 Supabase Edge Secret，GitHub Actions 的 Supabase URL/secret 也已保存。专用 GitHub 令牌于 **2027-09-19** 到期，届时需更换并更新 Edge Secret。直接 PAT 调度与真实管理员按钮调度均已验证，真实成员内容全流程仍待验证。

现有线上地址：[Tian Lab](https://jojolee0731.github.io/tian-lab-site/)。

成员及管理员操作见[工作台操作说明](docs/member-portal-guide.md)，服务配置见[后端说明](docs/member-portal-backend.md)，接口和发布边界见[实现契约](docs/member-portal-contract.md)。

## 构建与预览

在本目录运行，构建无需安装第三方Python包：

```sh
python3 scripts/build_site.py
```

本轮本地预览地址为`http://127.0.0.1:4186/`，中文入口为`http://127.0.0.1:4186/zh/`，西班牙语入口为`http://127.0.0.1:4186/es/`。如需自行启动服务器：

```sh
python3 -m http.server 4186 --bind 127.0.0.1
```

如果端口已占用，先确认是否已有本项目的预览；需要独立启动时可选择另一个空闲端口。不要停止未知进程或用户已有服务。`npm run dev`和`npm run preview`是保留的便捷命令，默认端口为4173。

## 内容与实现位置

| 文件 | 用途 |
| --- | --- |
| `data/publications.json` | 既有论文与已选新增论文的唯一目录、题名、作者、DOI、正式年份、已核实上线日期、类型、三语说明和展示ID |
| `data/people.json` | PI 及 34 名现有成员、分组、真实肖像、角色、单位、研究方向和已确认英文姓名 |
| `data/member-profiles.json` | 仅管理员获批并经导出校验的个人研究内容；当前初始为空 |
| `data/contact.json` | PI和行政联系方式、公开单位信息与官方入口 |
| `data/site.json` | 保留的旧版来源与校验基线；生成器仍从中读取已有封面、新闻及部分机构/合作文案 |
| `scripts/build_site.py` / `scripts/member_profile.py` | 页面结构、三语 UI 和个人内容安全校验；生成 123 个公开 HTML 页面及 sitemap |
| `styles.css` | 视觉层级、响应式布局、焦点样式及减少动态效果支持 |
| `script.js` | 渐进增强；生产域名才加载原有分析脚本，本地预览不加载 |
| `member-profile.css` | 个人主页的布局样式 |
| `members/` | 登录、本人编辑、管理员审核及权限界面；配置只能含公开 URL/publishable key |
| `scripts/export_member_profiles.py` / `scripts/member_publish_guard.py` | 获批快照导出、真实图片校验、公开提交及 Pages 产物范围检查 |
| `supabase/` / `.github/workflows/publish-members.yml` | 私有数据权限、发布接口、测试与 GitHub Actions 发布管线；不作为网页文件打包 |
| `assets/images/` | 已有科研插画、封面、肖像及其他真实图像资产 |
| `sitemap.xml` / `robots.txt` | 与静态页面路径对应的站点地图及爬虫入口 |

修改数据、页面结构或文案后，重新运行构建，不要直接修改生成的HTML，否则下一次构建会覆盖这些修改。`data/site.json`同时承担原始目录保留检查，本次应保持不动；后续若维护新闻和封面，可先将对应内容抽取为独立来源，再调整生成器及校验基线。

七个主页面文件为 `index.html`、`research.html`、`publications.html`、`people.html`、`join.html`、`collaborate.html`、`news.html`，成员个人页使用 `person-member-XX.html`。英文位于根目录，中文位于 `zh/`，西班牙语位于 `es/`。保持三语页面对应，新增或移除成员后重新构建对应个人页和站点地图。

## 内容维护边界

- 用户已授权从14篇候选中选择新增论文。选择依据与取舍见 `data/publication-selection.json`，书目信息和核验来源见[论文来源与修正说明](publication-source-notes.md)。原有16篇仍保留。
- 用户确认尹浩霖已毕业，已从当前成员名单移除；论文署名及历史科研报道保留。该变更记录在 `data/content-decisions.json`。
- 用户授权新增陶怡然，稳定 ID 为 `member-35`，归“技术组”；新增决策同样记录在 `data/content-decisions.json`。成员保留检查只接受明确记录的 ID 与姓名，不复用已移除成员的 ID。
- `year`使用正式期刊年；`publishedOnline`只填写已核实的首次上线日期。DOI中的年份不能替代发表日期，缺失日期不推算。论文类型、模型和证据范围须与正式来源一致。
- 成员英文姓名以已核实拼写为准，尚未确认时保留原姓名。缺失的研究方向不补造；学生与博士后统一显示博士生、硕士生、本科生、博士后，不展示年级。
- 团队没有合照，当前用真实成员肖像和分工展示。用户另要求移除合作页2017年UCL合照，三语页面均不再展示，源图片保留。不得合成合照或虚构实验室活动。
- 已有新闻示意图和封面用于介绍研究，与原始实验数据区分。申请页列出咨询路径，不承诺未确认的名额、资助或培养安排。
- 新增公开内容时同时维护三语版本；公众页面不承载内部维护说明。
- 成员个人项目和论文必须经管理员审核；个人论文不会自动进入课题组精选或总目录。成员英文自述可选，未提供时显示经标注的原文，不自动编造翻译或经历。

## 验证

运行现有检查命令：

```sh
npm run check
```

该命令依次检查JavaScript语法、生成页面与源文件的一致性，以及本地路径/锚点、页面语言与基础结构、论文和成员的保留情况。可单独运行：

```sh
python3 scripts/build_site.py --check
python3 scripts/check_site.py
```

发布导出需要 `requirements.txt` 中固定版本的 Pillow；建议在独立虚拟环境安装，不影响仅用标准库的静态构建。导出和发布权限测试命令：

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -p 'test_member_export.py'
node --test tests/*.test.mjs
```

修改成员客户端依赖时使用已固定版本的 `package-lock.json` 和 `npm run bundle:members` 重新生成 `members/vendor/supabase.js`。浏览器测试应另覆盖验证码、本人权限、保存冲突、审核、退回、恢复和上线版本核对；本地结构/权限测试不等于真实云端联测。

结构检查不代替实际视觉与交互检查。页面修改后，按受影响范围检查320、390、768、1440像素视窗，核对三语换行、菜单键盘操作、语言切换、论文筛选、链接与直接访问。外部出版商的验证码或访问限制，应与真正失效链接区分。

## 发布范围

GitHub Pages 的构建来源已设置为 GitHub Actions。`.github/workflows/publish-members.yml` 的普通 `main` push 与 `workflow_dispatch` 均已成功运行；2026-09-20又完成了真实管理员按钮经 Edge 调度的构建与部署。当前获批目录为空，真实成员图片与非空内容发布仍待验证。具体 secrets 配置见后端说明，密钥不进入公开配置。

保存草稿、提交审核、批准和上线是不同步骤。后台“已批准”只选定待公开版本；“发布任务已启动”只表示请求进入工作流。部署完成后须核对公开 JSON 的提交版本 ID 与实际个人页，不能将批准、推送或请求成功直接视为上线完成。检查失败时不部署，后台获批记录保留。

后续新增或移除内容时，应同步维护决策记录与校验规则：保留基线论文及其他成员，仅允许已记录的论文新增及成员增删，不为通过检查而清空保留约束。名册更新后另同步私有 registry；公开名册不自动批量邀请成员。
