/**
 * Runtime layout probe for html-ppt-maker decks (dual-track pipeline, step 3).
 *
 * 在打开成品 deck 的浏览器里执行（DevTools console 或 CDP Runtime.evaluate,
 * awaitPromise: true）。逐页 show + revealAll 后检查：
 *   - overflow:   可见元素超出 1280x720 舞台边界（容差 4px）
 *   - clipped:    文本被裁切（scrollWidth/Height 超出 clientWidth/Height 6px 以上）
 *   - overlap:    两个含文字的叶子元素重叠面积超过较小者的 35%
 *   - line-text-overlap: 显式连接线穿过文字叶子元素
 *   - stroke-text-overlap: SVG 描边（path/circle/line 等）穿过或压住文字叶子元素
 *   - offstage:   绝对定位元素完全跑出舞台
 *   - weak-anchor: 第一视觉锚点字阶偏弱时给 warning，不阻断几何布局验收
 *   - numeric-font-mismatch: 大号纯数字仍继承衬线标题字体时给 warning
 *   - aggressive-image-crop: cover 裁切比例过高且未经人工确认时给 warning
 *   - inspect-image-cropped: 检查型图片被严重裁切时判定 violation
 *
 * 返回 { pass, violations, warnings }。
 * FAIL 判定：violations 非空即未通过，修完重跑。
 */
(async () => {
  const stage = document.querySelector('.stage');
  const slides = [...document.querySelectorAll('.slide')];
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const violations = [];
  const warnings = [];

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const label = (el) => {
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 24);
    return `${el.tagName.toLowerCase()}.${[...el.classList].join('.')}${text ? ` "${text}"` : ''}`;
  };

  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i];
    if (typeof show === 'function') show(i);
    if (typeof revealAll === 'function') revealAll(slide);
    await wait(650); // 等过渡与揭示动画走完

    const stageRect = stage.getBoundingClientRect();
    const layout = [...slide.classList].find((c) => c.startsWith('layout-')) || '?';
    const els = [...slide.querySelectorAll('*')].filter(visible);

    for (const el of els) {
      const r = el.getBoundingClientRect();
      const tol = 4 * (stageRect.width / 1280);
      // 舞台外溢出（redline 等有意出血的装饰，用 data-bleed 标记豁免）
      if (!el.closest('[data-bleed]')) {
        if (r.right > stageRect.right + tol || r.left < stageRect.left - tol ||
            r.bottom > stageRect.bottom + tol || r.top < stageRect.top - tol) {
          const fully_out = r.left > stageRect.right || r.right < stageRect.left ||
                            r.top > stageRect.bottom || r.bottom < stageRect.top;
          violations.push({
            slide: i + 1, layout, type: fully_out ? 'offstage' : 'overflow',
            text: label(el),
            detail: `rect=(${Math.round(r.left - stageRect.left)},${Math.round(r.top - stageRect.top)},${Math.round(r.width)}x${Math.round(r.height)}) stage=${Math.round(stageRect.width)}x${Math.round(stageRect.height)}`,
          });
        }
      }
      // 文本裁切
      const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (hasText && (el.scrollWidth > el.clientWidth + 6 || el.scrollHeight > el.clientHeight + 6)) {
        const cs = getComputedStyle(el);
        if (cs.overflow !== 'visible' || el.scrollWidth > el.clientWidth + 6) {
          violations.push({
            slide: i + 1, layout, type: 'clipped', text: label(el),
            detail: `scroll=${el.scrollWidth}x${el.scrollHeight} client=${el.clientWidth}x${el.clientHeight}`,
          });
        }
      }
    }

    // 第一视觉锚点字号比例：防止整页字号都挤在同一档。
    const textEls = els.filter((el) =>
      [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
    const fontRows = textEls.map((el) => {
      const size = parseFloat(getComputedStyle(el).fontSize || '0');
      const txt = (el.textContent || '').trim();
      return { el, size, txt };
    }).filter((row) => row.size > 0 && row.txt.length > 0);
    const bodyRows = fontRows.filter((row) => row.txt.length >= 8 && row.size >= 12 && row.size <= 30);
    const anchor = fontRows.reduce((best, row) => (!best || row.size > best.size ? row : best), null);
    const bodyMedian = bodyRows.length ? bodyRows.map((row) => row.size).sort((a, b) => a - b)[Math.floor(bodyRows.length / 2)] : 18;
    const minRatio = /layout-(hero|section|quote|end)/.test(layout) ? 2.2 : 1.8;
    if (anchor && bodyMedian && anchor.size / bodyMedian < minRatio) {
      warnings.push({
        slide: i + 1, layout, type: 'weak-anchor', text: label(anchor.el),
        detail: `largestFont=${Math.round(anchor.size)}px bodyMedian=${Math.round(bodyMedian)}px ratio=${(anchor.size / bodyMedian).toFixed(2)} need>=${minRatio}`,
      });
    }

    // 大号纯数字必须使用独立数字字体，避免宋体/Georgia 数字破坏字面比例。
    for (const row of fontRows) {
      const compact = row.txt.replace(/\s+/g, '');
      if (row.size < 40 || !/^[+%$¥€£.,:/→\-]*\d[\d+%$¥€£.,:/→\-]*$/.test(compact)) continue;
      const family = getComputedStyle(row.el).fontFamily.toLowerCase();
      if (/georgia|serif|songti|stsong|ming/.test(family) && !/sans-serif/.test(family)) {
        warnings.push({
          slide: i + 1, layout, type: 'numeric-font-mismatch', text: label(row.el),
          detail: `fontFamily=${getComputedStyle(row.el).fontFamily}; use a dedicated --font-number lining/tabular stack`,
        });
      }
    }

    // 图片适配：检查型图片优先保证可读，激进 cover 必须显式人工确认。
    const images = els.filter((el) => el.tagName === 'IMG' && el.naturalWidth > 0 && el.naturalHeight > 0);
    for (const img of images) {
      const r = img.getBoundingClientRect();
      const naturalRatio = img.naturalWidth / img.naturalHeight;
      const displayRatio = r.width / r.height;
      const fit = getComputedStyle(img).objectFit;
      if (fit !== 'cover' || !Number.isFinite(displayRatio) || displayRatio <= 0) continue;
      const retained = naturalRatio > displayRatio ? displayRatio / naturalRatio : naturalRatio / displayRatio;
      const approved = Boolean(img.closest('[data-crop-approved]'));
      const inspect = img.matches('[data-image-role="inspect"]');
      if (inspect && retained < 0.72 && !approved) {
        violations.push({
          slide: i + 1, layout, type: 'inspect-image-cropped', text: label(img),
          detail: `estimated retained content=${Math.round(retained * 100)}%; reflow the grid, use a content-safe viewport, or approve the crop after visual review`,
        });
      } else if (retained < (inspect ? 0.9 : 0.65) && !approved) {
        warnings.push({
          slide: i + 1, layout, type: 'aggressive-image-crop', text: label(img),
          detail: `estimated retained content=${Math.round(retained * 100)}%; verify focal content and add data-crop-approved only after screenshot review`,
        });
      }
    }

    // 文字叶子元素两两重叠
    const leaves = els.filter((el) =>
      [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) &&
      ![...el.children].some(visible));
    for (let a = 0; a < leaves.length; a++) {
      for (let b = a + 1; b < leaves.length; b++) {
        if (leaves[a].contains(leaves[b]) || leaves[b].contains(leaves[a])) continue;
        const ra = leaves[a].getBoundingClientRect();
        const rb = leaves[b].getBoundingClientRect();
        const ix = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const iy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (ix > 0 && iy > 0) {
          const inter = ix * iy;
          const smaller = Math.min(ra.width * ra.height, rb.width * rb.height);
          if (smaller > 0 && inter / smaller > 0.35) {
            violations.push({
              slide: i + 1, layout, type: 'overlap',
              text: `${label(leaves[a])} × ${label(leaves[b])}`,
              detail: `${Math.round((inter / smaller) * 100)}% of smaller element`,
            });
          }
        }
      }
    }

    // 关系线必须走专用轨道。data-connector 是强约定，常见旧类名用于兼容审计。
    const connectors = els.filter((el) =>
      el.matches('[data-connector],.connector,.relation-line,.flow-lane,.road,.team-arrow'));
    for (const connector of connectors) {
      const rc = connector.getBoundingClientRect();
      for (const leaf of leaves) {
        if (connector.contains(leaf) || leaf.contains(connector)) continue;
        const rt = leaf.getBoundingClientRect();
        const ix = Math.min(rc.right, rt.right) - Math.max(rc.left, rt.left);
        const iy = Math.min(rc.bottom, rt.bottom) - Math.max(rc.top, rt.top);
        if (ix > 2 && iy > 2) {
          violations.push({
            slide: i + 1, layout, type: 'line-text-overlap',
            text: `${label(connector)} × ${label(leaf)}`,
            detail: `intersection=${Math.round(ix)}x${Math.round(iy)}px; move the connector into a dedicated track`,
          });
        }
      }
    }

    // SVG 描边不得穿字：沿 path/circle/line 等几何体的描边采样，
    // 采样点落入文字块外接矩形（按半线宽膨胀）即判重合。
    // 文字块 = 任何带有直接文字节点的元素，不限于无子元素的叶子；
    // 否则像「数字徽标 + 标签」这种容器里的文字会成为检查盲区。
    // 例外 1：描边被文字所在卡片/节点的不透明背景遮住（DOM 序更靠后、z-index 不低于
    // SVG），视觉上看不到重合，不报。例外 2：有意让描边从文字下方经过的装饰
    // （如轮廓圆环衬底），用 data-stroke-under-text 豁免。
    const occludedByCard = (leaf, svgEl, px, py) => {
      for (let n = leaf; n && n !== slide; n = n.parentElement) {
        const m = getComputedStyle(n).backgroundColor.match(/rgba?\(([^)]+)\)/);
        if (!m) continue;
        const parts = m[1].split(',').map((v) => parseFloat(v));
        if ((parts.length === 4 ? parts[3] : 1) < 0.9) continue;
        const rn = n.getBoundingClientRect();
        if (px < rn.left || px > rn.right || py < rn.top || py > rn.bottom) continue;
        const rel = svgEl.compareDocumentPosition(n);
        if (!(rel & Node.DOCUMENT_POSITION_FOLLOWING)) return false; // n 包含 svg 或在 svg 之前，画在描边下方
        const zN = parseFloat(getComputedStyle(n).zIndex) || 0;
        const zS = parseFloat(getComputedStyle(svgEl).zIndex) || 0;
        return zN >= zS;
      }
      return false;
    };
    const strokeEls = [...slide.querySelectorAll(
      'svg path, svg circle, svg ellipse, svg line, svg polyline, svg polygon, svg rect')]
      .filter((el) => {
        if (el.closest('[data-stroke-under-text]') || el.hasAttribute('data-stroke-under-text')) return false;
        if (!visible(el)) return false;
        const cs = getComputedStyle(el);
        const sw = parseFloat(cs.strokeWidth || '0');
        return cs.stroke && cs.stroke !== 'none' && sw > 0 && typeof el.getTotalLength === 'function';
      });
    const textBlocks = els.filter((el) =>
      !el.closest('svg') &&
      [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
    for (const sel of strokeEls) {
      let len;
      try { len = sel.getTotalLength(); } catch (e) { continue; }
      if (!Number.isFinite(len) || len <= 0) continue;
      const ctm = sel.getScreenCTM();
      if (!ctm) continue;
      const svgRoot = sel.closest('svg') || sel;
      const halfStroke = parseFloat(getComputedStyle(sel).strokeWidth || '1') / 2;
      const samples = Math.min(240, Math.max(32, Math.ceil(len / 6)));
      for (const leaf of textBlocks) {
        if (sel.contains(leaf) || leaf.contains(sel)) continue;
        const rt = leaf.getBoundingClientRect();
        const pad = halfStroke + 1;
        let visibleHit = false;
        for (let k = 0; k <= samples && !visibleHit; k++) {
          const p = sel.getPointAtLength((len * k) / samples).matrixTransform(ctm);
          if (p.x >= rt.left - pad && p.x <= rt.right + pad &&
              p.y >= rt.top - pad && p.y <= rt.bottom + pad &&
              !occludedByCard(leaf, svgRoot, p.x, p.y)) visibleHit = true;
        }
        if (visibleHit) {
          violations.push({
            slide: i + 1, layout, type: 'stroke-text-overlap',
            text: `${label(sel)} × ${label(leaf)}`,
            detail: 'SVG stroke crosses text; place labels beside the stroke (>=8px gap), stop connectors at node borders, or mark intentional underlays with data-stroke-under-text',
          });
        }
      }
    }
  }

  if (typeof show === 'function') show(0);
  return { pass: violations.length === 0, checked_slides: slides.length, violations, warnings };
})();
