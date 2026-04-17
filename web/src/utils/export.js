/**
 * 文本处理和导出工具函数
 */

/**
 * 复制文本到剪贴板
 */
export async function copyToClipboard(text, onSuccess) {
  try {
    await navigator.clipboard.writeText(text);
    onSuccess?.();
  } catch (err) {
    console.error('复制失败:', err);
    throw new Error('无法复制到剪贴板');
  }
}

/**
 * 生成 Markdown 格式的文献综述
 */
export function generateMarkdownContent(result, query) {
  const date = new Date().toLocaleDateString('zh-CN');
  const sources = result.sources
    .map(
      (source) =>
        `- [${source.source_type === 'arxiv' ? 'arXiv' : '本地'}] ${source.title}\n  ID: ${source.id}`
    )
    .join('\n');

  return `# 文献综述：${query}

**生成时间**: ${date}  
**详细程度**: ${
    { concise: '简洁', standard: '标准', deep: '深度' }[result.metadata.detail_level] || '标准'
  }  
**证据来源**: ${
    {
      local_only: '本地文献',
      arxiv_only: 'arXiv',
      local_plus_arxiv: '本地 + arXiv',
    }[result.metadata.source_mode] || '混合'
  }  
**文献数量**: 本地 ${result.metadata.local_documents_count} 篇 | arXiv ${result.metadata.arxiv_documents_count} 篇

---

## 内容

${result.review}

---

## 引用文献 (${result.sources.length} 篇)

${sources}

---

*本文由 Digital-Economy RAG 智能写作系统自动生成*
`;
}

/**
 * 下载文件（Markdown、JSON 等）
 */
export function downloadFile(content, filename, mimeType = 'text/plain') {
  const element = document.createElement('a');
  element.setAttribute('href', `data:${mimeType};charset=utf-8,${encodeURIComponent(content)}`);
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

/**
 * 生成 HTML 格式以支持打印为 PDF
 */
export function generateHTMLForPrint(result, query) {
  const date = new Date().toLocaleDateString('zh-CN');
  const sourcesHTML = result.sources
    .map(
      (source) =>
        `<li>[${source.source_type === 'arxiv' ? 'arXiv' : '本地'}] <strong>${source.title}</strong><br/>ID: ${source.id}</li>`
    )
    .join('');

  return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>文献综述：${query}</title>
  <style>
    body {
      font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
      line-height: 1.8;
      color: #1f2937;
      background: white;
      max-width: 900px;
      margin: 0 auto;
      padding: 40px 20px;
    }
    h1 { font-size: 28px; margin-bottom: 20px; color: #000; }
    h2 { font-size: 20px; margin-top: 30px; margin-bottom: 15px; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; }
    p { margin-bottom: 15px; }
    .meta { 
      background: #f3f4f6;
      padding: 15px;
      border-radius: 8px;
      margin-bottom: 30px;
      font-size: 14px;
    }
    .meta > div { margin-bottom: 8px; }
    .meta strong { color: #4b5563; }
    .content { 
      background: white;
      padding: 20px;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      margin-bottom: 30px;
    }
    ul { margin: 15px 0; padding-left: 30px; }
    li { margin: 10px 0; }
    footer {
      text-align: center;
      font-size: 12px;
      color: #6b7280;
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #e5e7eb;
    }
    @media print {
      body { padding: 20px; }
      .no-print { display: none; }
    }
  </style>
</head>
<body>
  <h1>文献综述：${query}</h1>
  
  <div class="meta">
    <div><strong>生成时间</strong>: ${date}</div>
    <div><strong>详细程度</strong>: ${
      { concise: '简洁', standard: '标准', deep: '深度' }[result.metadata.detail_level] || '标准'
    }</div>
    <div><strong>证据来源</strong>: ${
      {
        local_only: '本地文献',
        arxiv_only: 'arXiv',
        local_plus_arxiv: '本地 + arXiv',
      }[result.metadata.source_mode] || '混合'
    }</div>
    <div><strong>文献数量</strong>: 本地 ${result.metadata.local_documents_count} 篇 | arXiv ${result.metadata.arxiv_documents_count} 篇</div>
  </div>

  <div class="content">
    ${result.review.replace(/\n\n/g, '</p><p>').replace(/^/, '<p>').replace(/$/, '</p>')}
  </div>

  <h2>引用文献 (${result.sources.length} 篇)</h2>
  <ul>
    ${sourcesHTML}
  </ul>

  <footer>
    <p>本文由 Digital-Economy RAG 智能写作系统自动生成</p>
  </footer>
</body>
</html>
`;
}

/**
 * 打开 PDF 打印预览
 */
export function printToPDF(result, query) {
  const htmlContent = generateHTMLForPrint(result, query);
  const printWindow = window.open('', '_blank');
  printWindow.document.write(htmlContent);
  printWindow.document.close();
  setTimeout(() => {
    printWindow.print();
  }, 250);
}

/**
 * 保存结果为 JSON
 */
export function saveAsJSON(result, query) {
  const data = {
    query,
    review: result.review,
    metadata: result.metadata,
    sources: result.sources,
    generatedAt: new Date().toISOString(),
  };
  downloadFile(JSON.stringify(data, null, 2), `review_${Date.now()}.json`, 'application/json');
}

/**
 * 生成分享链接（构建状态快照 URL）
 */
export function generateShareLink(result, query) {
  // 创建一个包含查询和结果摘要的 URL
  const summary = encodeURIComponent(
    result.review.substring(0, 100).replace(/\n/g, ' ')
  );
  const baseURL = window.location.origin + window.location.pathname;
  // 实际应用中可以使用 URL params 或短链接服务
  return `${baseURL}?query=${encodeURIComponent(query)}&summary=${summary}`;
}

/**
 * 显示成功提示
 */
export function showSuccessToast(message, duration = 2000) {
  // 创建简单的 toast 提示（可根据需要替换为 UI 库的 toast）
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #10b981;
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    font-size: 14px;
    z-index: 9999;
    animation: slideIn 0.3s ease;
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, duration);
}

/**
 * 格式化日期
 */
export function formatDate(date) {
  return new Date(date).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
