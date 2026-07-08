"""
Publisher — renders summaries to Markdown/HTML and streams to GitHub Pages.

Streaming mode (default):
  - Call publish_one(result) for each bill as soon as Gemma finishes it.
  - Each call appends one JSON line to bills.jsonl and commits+pushes immediately.
  - The site updates in near real-time; partial runs publish what completed.

Batch mode (legacy / --dry-run):
  - Call publish(results) with the full list.
  - Writes bills.jsonl once, then does a single commit+push.
"""

import json
import re
import subprocess
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone


def _gh_remote_url(repo: str) -> str:
    """Prefer HTTPS+gh token; fall back to SSH."""
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    token = result.stdout.strip()
    if token:
        return f"https://{token}@github.com/{repo}.git"
    return f"git@github.com:{repo}.git"

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
JSONL_PATH = OUTPUT_DIR / "bills.json"


class Publisher:
    def __init__(self, output_config: dict):
        self.config = output_config
        self.gh_pages = output_config.get("github_pages", {})
        self._clone_dir: str | None = None  # reused across streaming calls

    # ── Public API ────────────────────────────────────────────────────────────

    def publish_one(self, result: dict):
        """Stream a single summarised bill: write files, append JSONL, commit+push."""
        OUTPUT_DIR.mkdir(exist_ok=True)
        self._write_html(result)
        entry = self._build_entry(result)
        self._append_jsonl(entry)
        if self.gh_pages.get("enabled"):
            self._stream_push(result["bill"]["id"])

    def publish(self, results: list):
        """Batch publish (legacy path). Writes all files then does one commit."""
        OUTPUT_DIR.mkdir(exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Wipe existing JSONL so we start clean on a batch run
        if JSONL_PATH.exists():
            JSONL_PATH.unlink()

        for r in results:
            self._write_html(r)
            entry = self._build_entry(r)
            self._append_jsonl(entry)

        self._write_index(results, date_str)

        if self.gh_pages.get("enabled"):
            self._batch_push(date_str)

    # ── Entry builder ─────────────────────────────────────────────────────────

    def _build_entry(self, result: dict) -> dict:
        bill = result["bill"]
        source_locale = result.get("source", {})
        summary = result["summary"]
        level = source_locale.get("type", "federal")
        safe_id = self._safe_id(bill["id"])
        return {
            "id":          bill.get("id", ""),
            "title":       bill.get("title", ""),
            "summary":     summary,
            "status":      bill.get("status", ""),
            "status_date": bill.get("status_date", ""),
            "source":      bill.get("source", source_locale.get("name", "")),
            "url":         bill.get("url", ""),
            "level":       level,
            "state":       source_locale.get("state", ""),
            "tags":        bill.get("tags", []),
            "file":        f"{safe_id}.html",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    # ── File writers ──────────────────────────────────────────────────────────

    def _write_html(self, result: dict):
        bill = result["bill"]
        summary = result["summary"]
        safe_id = self._safe_id(bill["id"])
        out_file = OUTPUT_DIR / f"{safe_id}.html"

        title = bill.get("title", "Untitled")
        url = bill.get("url", "")
        source = bill.get("source", "")
        status = bill.get("status", "Unknown")
        status_date = bill.get("status_date", "")
        level = bill.get("level", "federal")
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Parse structured sections from summary
        sections = self._parse_summary(summary)

        def esc(s):
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        def render_section(label, items, kind):
            html = f'<div class="summary-section"><div class="summary-section-label">{esc(label)}</div>'
            if kind == "p":
                html += f"<p>{esc(items[0])}</p>"
            else:
                html += "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"
            html += "</div>"
            return html

        body_html = ""
        if sections["overview"]:
            body_html += render_section("Overview", [sections["overview"]], "p")
        if sections["affected"]:
            body_html += render_section("Who Is Affected", sections["affected"], "ul")
        if sections["changes"]:
            body_html += render_section("What Changes", sections["changes"], "ul")
        if sections["debated"]:
            body_html += render_section("What\u2019s Debated", sections["debated"], "ul")
        if sections["status"]:
            body_html += render_section("Status", [sections["status"]], "p")
        if not body_html:
            # Fallback: render raw summary as paragraphs
            for para in summary.split("\n\n"):
                para = para.strip()
                if para:
                    body_html += f"<p>{esc(para)}</p>\n"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} — Plain Law</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #fff; --text: #1a1a1a; --text-muted: #6b6b6b;
      --border: #1a1a1a; --rule: #e0e0e0;
      --serif: Georgia, "Times New Roman", Times, serif;
      --sans: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
    }}
    body {{ font-family: var(--serif); background: var(--bg); color: var(--text); line-height: 1.65; font-size: 17px; }}
    a {{ color: var(--text); }}
    a:hover {{ text-decoration: underline; }}
    .masthead {{ border-top: 3px solid var(--border); border-bottom: 1px solid var(--border); padding: 0.5rem 0 0.75rem; }}
    .masthead-inner {{ max-width: 800px; margin: 0 auto; padding: 0 1.5rem; }}
    .masthead-top {{ display: flex; align-items: flex-end; justify-content: space-between; padding: 0.75rem 0 0.5rem; border-bottom: 1px solid var(--rule); margin-bottom: 0.4rem; }}
    .wordmark {{ font-family: var(--serif); font-size: 2.4rem; font-weight: 700; letter-spacing: -0.03em; color: var(--text); text-decoration: none; }}
    .masthead-nav {{ display: flex; gap: 1.25rem; }}
    .masthead-nav a {{ font-family: var(--sans); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text); text-decoration: none; }}
    .masthead-nav a:hover {{ text-decoration: underline; }}
    .article {{ max-width: 800px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
    .article-kicker {{ font-family: var(--sans); font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-muted); margin-bottom: 0.75rem; }}
    .article-title {{ font-family: var(--serif); font-size: 2rem; font-weight: 700; line-height: 1.2; margin-bottom: 1rem; }}
    .article-meta {{ font-family: var(--sans); font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 0.6rem 0; margin-bottom: 2rem; display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }}
    .article-meta .sep {{ color: #ccc; }}
    .summary-section {{ margin-bottom: 1.75rem; }}
    .summary-section-label {{ font-family: var(--sans); font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-muted); margin-bottom: 0.6rem; padding-bottom: 0.3rem; border-bottom: 2px solid var(--border); }}
    .summary-section p {{ font-size: 1rem; line-height: 1.7; }}
    .summary-section ul {{ list-style: none; padding: 0; }}
    .summary-section ul li {{ font-size: 0.95rem; line-height: 1.6; padding: 0.55rem 0 0.55rem 1.25rem; position: relative; border-bottom: 1px solid var(--rule); }}
    .summary-section ul li:last-child {{ border-bottom: none; }}
    .summary-section ul li::before {{ content: '\u2022'; position: absolute; left: 0; color: var(--text-muted); }}
    .disclaimer {{ font-family: var(--sans); font-size: 0.76rem; font-style: italic; color: var(--text-muted); border-top: 1px solid var(--rule); padding-top: 1rem; margin-top: 2rem; line-height: 1.55; }}
    .official-link {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--rule); }}
    .official-link a {{ font-family: var(--sans); font-size: 0.82rem; color: var(--text); border-bottom: 1px solid var(--text); text-decoration: none; padding-bottom: 0.05rem; }}
    .official-link a:hover {{ opacity: 0.6; }}
    footer {{ border-top: 2px solid var(--border); padding: 1.25rem 0; margin-top: 2rem; }}
    footer .inner {{ max-width: 800px; margin: 0 auto; padding: 0 1.5rem; font-family: var(--sans); font-size: 0.73rem; color: var(--text-muted); }}
    @media (max-width: 600px) {{ .wordmark {{ font-size: 1.8rem; }} .article-title {{ font-size: 1.4rem; }} }}
  </style>
</head>
<body>
<header class="masthead">
  <div class="masthead-inner">
    <div class="masthead-top">
      <a href="index.html" class="wordmark">PlainLaw</a>
      <nav class="masthead-nav">
        <a href="index.html">&larr; All bills</a>
        <a href="faq.html">About</a>
      </nav>
    </div>
  </div>
</header>
<article class="article">
  <div class="article-kicker">{esc(level.upper())} &middot; {esc(source)}</div>
  <h1 class="article-title">{esc(title)}</h1>
  <div class="article-meta">
    <span>{esc(status)}</span>
    {f'<span class="sep">&middot;</span><span>{esc(status_date)}</span>' if status_date else ''}
    {f'<span class="sep">&middot;</span><a href="{esc(url)}" target="_blank" rel="noopener">Official source &#8599;</a>' if url else ''}
  </div>
  {body_html}
  <div class="official-link">
    {f'<a href="{esc(url)}" target="_blank" rel="noopener">Read full official text &#8599;</a>' if url else ''}
  </div>
  <p class="disclaimer">This summary was generated by a local Gemma AI model on {generated}. It may contain errors or omissions. Always read the official source before making decisions. Not legal advice.</p>
</article>
<footer>
  <div class="inner">
    Plain Law is an independent personal project. Content does not represent the views of the operator or any affiliated organization.
    &nbsp;&middot;&nbsp;<a href="index.html">Browse all bills</a>
    &nbsp;&middot;&nbsp;<a href="https://github.com/callmeradical/plain-law">GitHub</a>
  </div>
</footer>
</body>
</html>"""
        with open(out_file, "w") as f:
            f.write(html)

    def _parse_summary(self, raw: str) -> dict:
        result = {"overview": "", "affected": [], "changes": [], "debated": [], "status": ""}
        current = None
        for line in raw.split("\n"):
            t = line.strip()
            if not t:
                continue
            if re.match(r"^OVERVIEW:", t, re.I):
                current = "overview"
                val = re.sub(r"^OVERVIEW:\s*", "", t, flags=re.I).strip()
                if val:
                    result["overview"] = val
            elif re.match(r"^WHO\s+IS\s+AFFECTED", t, re.I):
                current = "affected"
            elif re.match(r"^WHAT\s+CHANGES", t, re.I):
                current = "changes"
            elif re.match(r"^WHAT.?S\s+DEBATED", t, re.I):
                current = "debated"
            elif re.match(r"^STATUS:", t, re.I):
                current = "status"
                val = re.sub(r"^STATUS:\s*", "", t, flags=re.I).strip()
                if val:
                    result["status"] = val
            elif current == "overview" and not result["overview"]:
                result["overview"] = t
            elif current == "status" and not result["status"]:
                result["status"] = t
            elif current in ("affected", "changes", "debated"):
                bullet = re.sub(r"^[-*\u2022]\s*", "", t).strip()
                if bullet and not re.match(r"^https?://", bullet, re.I):
                    result[current].append(bullet)
        return result

    def _append_jsonl(self, entry: dict):
        with open(JSONL_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logging.debug(f"Appended to bills.jsonl: {entry['id']}")

    def _write_index(self, results: list, date_str: str):
        index_path = OUTPUT_DIR / "index.md"
        with open(index_path, "w") as f:
            f.write(f"# Plain Law — {date_str}\n\n")
            f.write("Plain-language summaries of legislation, generated by a local Gemma model.\n\n")
            f.write("> ⚠️ These summaries are AI-generated and may contain errors. "
                    "Each entry links to its official source — always read the original before acting on this information.\n\n")
            f.write("---\n\n")
            by_source: dict[str, list] = {}
            for r in results:
                src = r["bill"]["source"]
                by_source.setdefault(src, []).append(r)
            for src, items in sorted(by_source.items()):
                f.write(f"### {src}\n\n")
                for r in items:
                    bill = r["bill"]
                    safe_id = self._safe_id(bill["id"])
                    official = f" — [official source]({bill['url']})" if bill.get("url") else ""
                    f.write(f"- [{bill['title']}]({safe_id}.md){official}\n")
                f.write("\n")

    # ── Git helpers ───────────────────────────────────────────────────────────

    def _get_clone(self) -> str:
        """Return path to a persistent clone dir; create+clone on first call.

        We clone sparse (no-checkout) so the working tree starts empty, then
        only ever add/update the files we explicitly copy in — never the whole
        source repo.
        """
        if self._clone_dir and Path(self._clone_dir).exists():
            return self._clone_dir

        repo = self.gh_pages.get("repo")
        branch = self.gh_pages.get("branch", "gh-pages")
        if not repo:
            raise ValueError("GitHub Pages repo not configured")

        tmpdir = tempfile.mkdtemp(prefix="plain-law-pages-")
        subprocess.run(
            ["git", "clone", _gh_remote_url(repo), "--branch", branch,
             "--depth", "1", "--no-local", tmpdir],
            check=True,
        )
        # Remove any source-repo directories that don't belong on the pages branch
        # (pipeline/, sources/, etc.) but keep existing .md summaries and static files
        keep_extensions = {".md", ".html", ".json", ".txt", ".css", ".js", ".png", ".ico"}
        keep_names = {"bills.json", "CNAME"}
        for item in Path(tmpdir).iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)  # remove any subdirectories (pipeline/, sources/, etc.)
            elif item.suffix not in keep_extensions and item.name not in keep_names:
                item.unlink()
        self._clone_dir = tmpdir
        logging.info(f"Cloned {repo}@{branch} → {tmpdir}")
        return tmpdir

    def _stream_push(self, bill_id: str):
        """Copy changed files into the persistent clone and push one commit."""
        try:
            clone = self._get_clone()
            clone_path = Path(clone)

            # Always keep index.html + faq.html current in the pages branch
            gh_pages_dir = BASE_DIR / "gh-pages"
            for static in ["index.html", "faq.html"]:
                src = gh_pages_dir / static
                if src.exists():
                    shutil.copy(src, clone_path / static)

            # Copy the new/changed files
            safe_id = self._safe_id(bill_id)
            md_src = OUTPUT_DIR / f"{safe_id}.md"
            if md_src.exists():
                shutil.copy(md_src, clone)

            if JSONL_PATH.exists():
                shutil.copy(JSONL_PATH, clone)

            # Stage, commit, push
            subprocess.run(["git", "-C", clone, "add", "."], check=True)

            # Check if there's anything to commit (git returns 1 if nothing staged)
            diff = subprocess.run(
                ["git", "-C", clone, "diff", "--cached", "--quiet"],
                capture_output=True,
            )
            if diff.returncode == 0:
                logging.debug(f"Nothing new to commit for {bill_id}")
                return

            msg = f"feat: add summary for {bill_id}"
            subprocess.run(["git", "-C", clone, "commit", "-m", msg], check=True)
            subprocess.run(["git", "-C", clone, "push", "origin", self.gh_pages.get("branch", "gh-pages")], check=True)
            logging.info(f"Pushed stream commit: {msg}")

        except subprocess.CalledProcessError as e:
            logging.error(f"Stream push failed for {bill_id}: {e}")

    def _batch_push(self, date_str: str):
        """One-shot clone, copy all output, commit, push."""
        repo = self.gh_pages.get("repo")
        branch = self.gh_pages.get("branch", "gh-pages")
        raw_msg = self.gh_pages.get("commit_message", "chore: update summaries [{date}]")
        commit_msg = raw_msg.replace("{date}", date_str)

        if not repo:
            logging.warning("GitHub Pages repo not configured — skipping push")
            return

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    ["git", "clone", _gh_remote_url(repo), "--branch", branch, tmpdir],
                    check=True,
                )
                for f in OUTPUT_DIR.glob("*.md"):
                    shutil.copy(f, tmpdir)
                if JSONL_PATH.exists():
                    shutil.copy(JSONL_PATH, tmpdir)
                subprocess.run(["git", "-C", tmpdir, "add", "."], check=True)
                subprocess.run(["git", "-C", tmpdir, "commit", "-m", commit_msg], check=True)
                subprocess.run(["git", "-C", tmpdir, "push", "origin", branch], check=True)
            logging.info(f"Batch pushed to GitHub Pages: {repo}@{branch}")
        except subprocess.CalledProcessError as e:
            logging.error(f"GitHub Pages batch push failed: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_id(bill_id: str) -> str:
        return bill_id.replace("/", "-").replace(" ", "_")
