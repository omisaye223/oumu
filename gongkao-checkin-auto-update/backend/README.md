# 自动更新申论内容

1. 在 `backend/sources.json` 中填入可靠来源的 RSS/Atom 地址。优先使用中国政府网、国务院、新华社、人民日报、半月谈及山西省政府/人事考试机构的公开订阅地址。
2. 在电脑上测试：`python backend/update_feed.py`。
3. 确认生成的 `feed.json` 后，将整个文件夹上传到 GitHub 仓库，并开启 GitHub Pages/Netlify。
4. 工作流每天北京时间 07:00 自动运行，更新 `feed.json`；App 打开时读取该文件。

注意：不要把来源网页的整篇文章复制进 App；只保存标题、摘要、来源、日期和原文链接，并遵守来源网站的 robots.txt、版权和使用条款。
