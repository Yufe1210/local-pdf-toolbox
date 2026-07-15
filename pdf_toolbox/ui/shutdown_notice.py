"""Browser-side notice shown after the local Streamlit service stops."""

from __future__ import annotations

import streamlit as st


SHUTDOWN_MONITOR_HTML = r"""
<script>
(() => {
  let hasBeenHealthy = false;
  let consecutiveFailures = 0;
  let stopped = false;

  const showClosedPage = () => {
    if (stopped) return;
    stopped = true;
    const documentRoot = window.parent.document;
    documentRoot.title = "本機 PDF 工具箱已關閉";
    documentRoot.body.innerHTML = `
      <main style="min-height:100vh;display:grid;place-items:center;background:#f6f7f9;
                   color:#1f2937;font-family:'Segoe UI','Microsoft JhengHei',sans-serif;padding:24px;">
        <section style="max-width:520px;text-align:center;background:white;border:1px solid #e5e7eb;
                        border-radius:16px;padding:40px;box-shadow:0 8px 28px rgba(0,0,0,.08);">
          <div style="font-size:48px;margin-bottom:12px;">📄</div>
          <h1 style="font-size:26px;margin:0 0 12px;">本機 PDF 工具箱已關閉</h1>
          <p style="font-size:16px;line-height:1.7;color:#4b5563;margin:0;">
            本機服務和背景程序已停止，你可以安全地關閉這個瀏覽器分頁。<br>
            若要繼續使用，請再次雙擊桌面捷徑。
          </p>
        </section>
      </main>`;
  };

  const checkHealth = async () => {
    try {
      const response = await fetch("/_stcore/health", {cache: "no-store"});
      if (response.ok) {
        hasBeenHealthy = true;
        consecutiveFailures = 0;
        return;
      }
    } catch (_) {
      // A stopped loopback service is the expected shutdown signal.
    }

    if (hasBeenHealthy && ++consecutiveFailures >= 3) showClosedPage();
  };

  checkHealth();
  window.setInterval(checkHealth, 750);
})();
</script>
"""


def render_shutdown_monitor() -> None:
    """Keep a tiny browser timer alive so a stopped service has a clear state."""

    st.html(SHUTDOWN_MONITOR_HTML, unsafe_allow_javascript=True)
