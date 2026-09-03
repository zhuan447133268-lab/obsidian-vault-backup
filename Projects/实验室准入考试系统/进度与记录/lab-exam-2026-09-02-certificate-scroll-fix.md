# lab-exam 证书页「下滑后回不到顶部、上面内容显示不全」修复

> ⚠️ **2026-09-02 定论**：用户确认「回不到顶」真正问题在「我的证书」**列表页**（MobileLayout 滚动容器），与本文件记录的详情页卡片**无关**——列表页真根因与修复见 [[lab-exam-2026-09-02-list-scroll-container-fix]]。本文件记录的那次详情页 CertificateCard 改动（移除 9:16 aspect-ratio）经用户要求核查，**存在修坏风险**（破坏 9:16 定稿证书比例、保存图片导出 PNG 比例、footer 印章不再贴底），且列表页 bug 与它无关，**已于 2026-09-02 git restore 完整回退**。详情页维持线上原样（9:16 定稿），部署后实测 ratio=0.563 正常。本文件保留仅作历史教训记录，不再作为有效修复方案。**结论：此改动已撤销，勿再在 CertificateCard 上移除 aspect-ratio。**

- 日期：2026-09-02
- 状态：❌ **已回退（git restore），非有效修复**——用户要求核查后确认此改动修坏风险大且与列表页 bug 无关；列表页真问题由 MobileLayout 修复（6ac5cf7，已部署验证）。本记录仅存史。
- 关联：[[lab-exam-2026-09-02-tabbar-rise-fix]]（同日移动端滚动链路的另一个 bug）

## 现象

学生端电子证书详情页（`/student/certificates/:id`，CertificateCard）在手机上：往下滑后再往上滑，**回不到顶部，上面内容（证书标题/学院）显示不全**。测试反馈，用户转述。

## 根因（定案）

**`.certificate-card` 用 `aspect-ratio: 9/16` 锁死高度，而证书内容（top-mark / cert-org / 中英文标题 / 金边分割 / 正文 / footer 证书编号+发证日期 / 印章 / note）在窄屏下的自然高度高于 9:16 比例锁出的高度 → 内容溢出卡片外。**

实测证据（Playwright 320×568 视口，真实证书页）：

- **修复前**：`aspect-ratio: 9/16` 锁死，cardH=498px；`.cert-footer` 底边**超出 `.cert-frame` 底边**（footerInside=NO）、印章同样溢出（stampInside=NO）；`frame` 的 `overflow-y: visible` → 溢出的 footer/note/印章直接画出卡片，落在卡片下缘外面。
- 溢出元素撑高了文档滚动区（docScrollH=647 > winH=568，scrollSpace=79px）——这段滚动空间**不是卡片真实内容高度**，而是"溢出物"顶出来的幽灵空间；用户下滑看到的是漂在卡片外的 footer/印章，上滑回顶时浏览器按幽灵文档高度回滚，卡片上部的标题本来就已因锁高被挤压/裁切，表现即"回不到顶、上面显示不全"。
- 390×844 主流视口下同样失真（锁高 9:16 的比例与校内文本量不匹配：学院名/班级/考试题名越长，内容越被压）。

补充：该组件同时被 `certificate-view.vue`（详情页，layout:blank，body/html 滚动）与 `CertificateExportPanel.vue`（ZIP 导出离屏渲染，`.zip-export-host` 固定 400px 宽）引用——导出走 `html-to-image` 截图，不影响。

## 修复

`web/src/components/CertificateCard.vue`（单文件）：

1. **移除 `.certificate-card` 的 `aspect-ratio: 9/16`（连同原 height 固定）** → 卡片高度改为跟随内容自适应（竖版比例退化为「约 10:16」~内容宽高比，校内文本完整不被裁）。
2. **`.cert-frame` 加 `overflow: hidden`** 双保险：即使个别机型内容仍偏紧，也截在金色框内，不画出卡片外产生幽灵滚动空间。

导出侧不受影响：400px 宽下卡片随内容增高，内容完整优先。

## 验证（本地构建 + IAB 实测，真实学生账号张凯悦证书页）

- ✅ vue-tsc / vite build 通过；产物 CSS：`.certificate-card` 无 aspect-ratio、`.cert-frame` 含 `overflow:hidden`。
- ✅ **320×568（可滚场景）手势全链路**（cua 模拟触屏下滑→上滑回顶）：
  - 下滑到底 scrollY=121/121，footer/note/印章**全部完整可见且在 frame 内**；
  - 上滑回顶 scrollY=0、atTop=yes、顶部标题可见、卡顶 62px 正常。
- ✅ **390×844（主流一屏场景）**：cardH=628 整卡一屏可见，footer/note 均在 frame 内，scrollSpace=0 无幽灵滚动。
- ✅ 构建产物 clean：清空 dist 重建后全量 CSS 扫描 aspect-ratio 出现次数 = 0。
- 截图：`gui-test-screenshots/2026-09-02-certificate-scroll-fix/`（baseline-locked-before-gesture / after-small-screen-top / after-small-screen-bottom / after-390x844，本地不推送）。

## 待办

- [x] ~~push main + 部署回归~~ —— **取消**：改动已回退（git restore），不推送、不部署。列表页真修复见 [[lab-exam-2026-09-02-list-scroll-container-fix]]（6ac5cf7 已部署并通过触屏回归）。
- [ ] 详情页「保存图片」导出 PNG 在真机上目检一次（9:16 已恢复定稿，toPng 输出随卡片比例恢复为 9:16）——仅作确认，无代码待改。