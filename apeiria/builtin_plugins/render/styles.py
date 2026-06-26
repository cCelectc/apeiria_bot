from __future__ import annotations

_DEFAULT_MARKDOWN_STYLE = """
body {
  margin: 0;
  background: #0b0e14;
  color: #e6edf3;
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
}

.markdown-body {
  width: 100%;
  padding: 28px 30px;
  line-height: 1.7;
  font-size: 16px;
  color: #e6edf3;
}

.markdown-body > *:first-child { margin-top: 0; }
.markdown-body > *:last-child { margin-bottom: 0; }

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin: 1.2em 0 0.55em;
  line-height: 1.35;
  font-weight: 800;
  color: #f7fbff;
}

.markdown-body h1 { font-size: 2em; }
.markdown-body h2 { font-size: 1.6em; }
.markdown-body h3 { font-size: 1.3em; }

.markdown-body p,
.markdown-body ul,
.markdown-body ol,
.markdown-body blockquote,
.markdown-body pre,
.markdown-body table {
  margin: 0 0 1em;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 1.5em;
}

.markdown-body li + li {
  margin-top: 0.25em;
}

.markdown-body a {
  color: #72b4ff;
  text-decoration: none;
}

.markdown-body code {
  padding: 0.16em 0.38em;
  border-radius: 6px;
  background: rgba(110, 118, 129, 0.22);
  color: #c9d1d9;
  font-family: "JetBrains Mono", "Noto Sans Mono", "Consolas", monospace;
  font-size: 0.92em;
}

.markdown-body pre {
  overflow: hidden;
  padding: 14px 16px;
  border-radius: 12px;
  background: #161b22;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.markdown-body pre code {
  padding: 0;
  background: transparent;
}

.markdown-body blockquote {
  padding: 0.2em 1em;
  color: rgba(230, 237, 243, 0.76);
  border-left: 4px solid #4e96f7;
  background: rgba(78, 150, 247, 0.08);
  border-radius: 0 10px 10px 0;
}

.markdown-body hr {
  margin: 1.5em 0;
  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: 12px;
  border-style: hidden;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.markdown-body th,
.markdown-body td {
  padding: 10px 12px;
  text-align: left;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.markdown-body th {
  background: rgba(78, 150, 247, 0.14);
  color: #f7fbff;
  font-weight: 700;
}

.markdown-body tr:nth-child(even) td {
  background: rgba(255, 255, 255, 0.02);
}

.markdown-body img {
  display: block;
  max-width: 100%;
  border-radius: 12px;
}
""".strip()
