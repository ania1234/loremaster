/** Decorative renderer adapted from the supplied Engraver's Ripple demo.
 * @param {HTMLCanvasElement} canvas
 */
export function mountEngraverRipple(canvas) {
  /* ============================================================
     CONFIG — change the background text and look here.
     ============================================================ */
  const DEFAULT_TEXT = `
Is anyone else weirded out by the huge amount of sexual/romantic things that get posted about in games?
My group has been playing for over ten years, and not once has a single one of our characters gotten into any kind of sexual or romantic situation. I can't even imagine having an NPC described to me and thinking 'yes, I am going to roleplay hitting on this character, with my old friend the DM playing the person I am hitting on'.
Maybe playing with people I've known for a long time makes it weirder- I know a lot of people are playing online with strangers, maybe that has a different kind of vibe to it. I did once play with people from work and the DM did make it sexually weird at one point- a lot of what I see in this category is actually on r/rpghorrorstories, and this encounter belongs there too. But in a game about fantasy and monsters and treasure and dungeons, sex and romance is for me an instant game killer. It makes it super weird and uncomfortable. I can see that there is a big difference between someone doing what their character would do, and someone using the game to act out bizarre fantasies, but even the former I woud find uncomfortable to sit through.
People play how they play and like what they like, maybe this comes down to people enjoying the roleplay element a lot more than the stats and numbers and combat element. I can't be the only one who is 100% put off the game by any sex and romance. Monsters and dungeons for me please. Does anyone else have absolutely none of this in their games?
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.`;

  const CONFIG = {
    text: DEFAULT_TEXT,
    fontSize: 10,            // px
    font: "engr",            // "engr" (IM Fell English) or "type" (Special Elite)
    ink:   "#6E655A",        // text colour
    paper: "#E1DCC6",        // background
    glow:  "#F6F2E7",        // hover / crest colour
    hoverRadius: 90,         // px
    wobble: 1.7,             // px of hover wobble
    waveSpeed: 150,          // px per second
    wavelength: 80,          // px between ripple crests (bigger = thicker waves)
    crests: 2,               // crests (rings) per ripple
    refraction: 3.2,         // px glyph displacement at a crest
    // Glyphs shown on the crests (Japanese kana + Chinese/Japanese characters)
    gibberish: "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン日月火水木金土山川田人口目耳手足心気天雨雪風花草竹石糸文字書言語道龍鳥魚馬虎門国家春夏秋冬東西南北光影夢墨筆紙波海",
  };
  const FONTS = {
    engr: `${getComputedStyle(canvas).getPropertyValue("--font-ripple-engraving")}, Georgia, serif`,
    type: '"Special Elite", "Courier New", monospace',
  };
  const CJK_FONT = `${getComputedStyle(canvas).getPropertyValue("--font-ripple-cjk")}, "Yu Mincho", serif`;
  const GIB = Array.from(CONFIG.gibberish);

  /* ============================================================ */
  const ctx = canvas.getContext("2d");
  const layer = document.createElement("canvas");
  const lctx = layer.getContext("2d");
  if (!ctx || !lctx) return () => {};
  const motion = 1;
  let animationId = 0;
  let disposed = false;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

  let W = 0, H = 0, dpr = 1, cols = 0, rows = 0, cellW = 6.4, lineH = 12.5, base = 9.6;
  let glyphs = [];
  let seen, hf, wh, wx, wy, wc, stamp = 0;
  const list = [], gibList = [];

  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const INK = hex(CONFIG.ink), GLOW = hex(CONFIG.glow);
  const STEPS = 24;
  const palette = Array.from({ length: STEPS + 1 }, (_, i) => {
    const k = i / STEPS;
    const c = INK.map((v, j) => Math.round(v + (GLOW[j] - v) * k));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  });


  function normalise(t) {
    const s = String(t || "").replace(/\s+/g, " ").trim();
    return (s || DEFAULT_TEXT) + " ";
  }
  function fontString() { return `${CONFIG.fontSize}px ${FONTS[CONFIG.font]}`; }

  function rebuild() {
    if (disposed) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    W = window.innerWidth; H = window.innerHeight;
    for (const c of [canvas, layer]) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    canvas.style.width = W + "px"; canvas.style.height = H + "px";

    cellW = CONFIG.fontSize * 0.64;
    lineH = CONFIG.fontSize * 1.25;
    base = lineH * 0.77;
    cols = Math.ceil(W / cellW) + 1;
    rows = Math.ceil(H / lineH) + 1;

    const text = normalise(CONFIG.text);
    const n = cols * rows;
    glyphs = new Array(n);
    for (let i = 0; i < n; i++) glyphs[i] = text[i % text.length];
    seen = new Int32Array(n); hf = new Float32Array(n);
    wh = new Float32Array(n); wx = new Float32Array(n); wy = new Float32Array(n); wc = new Uint8Array(n);

    lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lctx.fillStyle = CONFIG.paper;
    lctx.fillRect(0, 0, W, H);
    lctx.font = fontString();
    lctx.textAlign = "center";
    lctx.textBaseline = "alphabetic";
    lctx.fillStyle = CONFIG.ink;
    for (let r = 0; r < rows; r++) {
      const y = r * lineH + base;
      for (let c = 0; c < cols; c++) {
        const ch = glyphs[r * cols + c];
        if (ch !== " ") lctx.fillText(ch, c * cellW + cellW / 2, y);
      }
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(layer, 0, 0);
  }

  /* ---------- interaction state ---------- */
  let mx = -1e4, my = -1e4, hover = 0, hoverTarget = 0;
  const drops = [];

  function mark(i) {
    if (seen[i] !== stamp) {
      seen[i] = stamp; hf[i] = 0; wh[i] = 0; wx[i] = 0; wy[i] = 0; wc[i] = 0; list.push(i);
    }
  }

  function hash(i, s) {
    let x = (Math.imul(i, 374761393) + Math.imul(s, 668265263)) | 0;
    x = Math.imul(x ^ (x >>> 13), 1274126177);
    return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
  }

  const LAMBDA = CONFIG.wavelength, PACKET = CONFIG.wavelength * CONFIG.crests;
  // Flat-topped packet so every crest is equally strong
  function envelope(x) {                    // x = distance behind the leading edge
    if (x <= 0 || x >= PACKET) return 0;
    const ramp = LAMBDA * 0.3;
    const e = Math.min(1, x / ramp, (PACKET - x) / ramp);
    return e * e * (3 - 2 * e);
  }
  const wave = x => Math.sin(2 * Math.PI * x / LAMBDA);

  function dropAmp(d, t) {
    const age = t - d.t0, front = age * CONFIG.waveSpeed;
    return { age, front, amp: Math.exp(-age / 10) / (1 + front / 1400) };
  }

  /* ---------- frame ---------- */
  let last = performance.now();
  function frame(now) {
    const t = now / 1000;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    hover += (hoverTarget - hover) * Math.min(1, dt * 7);

    const diag = Math.hypot(W, H);
    for (let k = drops.length - 1; k >= 0; k--) {
      const { front, amp } = dropAmp(drops[k], t);
      if (front - PACKET > diag + 50 || amp < 0.03) drops.splice(k, 1);
    }

    stamp++; list.length = 0;

    // Hover field
    if (hover > 0.005 && mx > -1e3) {
      const R = CONFIG.hoverRadius;
      const c0 = Math.max(0, Math.floor((mx - R) / cellW)), c1 = Math.min(cols - 1, Math.ceil((mx + R) / cellW));
      const r0 = Math.max(0, Math.floor((my - R) / lineH)), r1 = Math.min(rows - 1, Math.ceil((my + R) / lineH));
      for (let r = r0; r <= r1; r++) {
        const cy = r * lineH + lineH / 2;
        for (let c = c0; c <= c1; c++) {
          const d = Math.hypot(c * cellW + cellW / 2 - mx, cy - my);
          if (d >= R) continue;
          let f = 1 - d / R; f = f * f * (3 - 2 * f) * hover;
          if (f < 0.004) continue;
          const i = r * cols + c; mark(i); hf[i] = f;
        }
      }
    }

    // Ripples
    for (const d of drops) {
      const { front, amp } = dropAmp(d, t);
      const rIn = Math.max(0, front - PACKET), rOut = front;
      if (rOut <= 0) continue;
      const r0 = Math.max(0, Math.floor((d.y - rOut) / lineH)), r1 = Math.min(rows - 1, Math.ceil((d.y + rOut) / lineH));
      for (let r = r0; r <= r1; r++) {
        const cy = r * lineH + lineH / 2, dy = cy - d.y;
        const span = Math.sqrt(Math.max(0, rOut * rOut - dy * dy));
        const c0 = Math.max(0, Math.floor((d.x - span) / cellW)), c1 = Math.min(cols - 1, Math.ceil((d.x + span) / cellW));
        const inner = Math.abs(dy) < rIn ? Math.sqrt(rIn * rIn - dy * dy) : -1;
        const s0 = inner > 0 ? Math.ceil((d.x - inner) / cellW) + 1 : 1e9;
        const s1 = inner > 0 ? Math.floor((d.x + inner) / cellW) - 1 : -1e9;
        for (let c = c0; c <= c1; c++) {
          if (c >= s0 && c <= s1) { c = s1; continue; }
          const dx = c * cellW + cellW / 2 - d.x;
          const dist = Math.hypot(dx, dy);
          const x = front - dist, s = wave(x), ea = envelope(x) * amp;
          const h = s * ea;
          if (Math.abs(h) < 0.01) continue;
          const i = r * cols + c; mark(i);
          wh[i] += h;
          if (s > 0.55 && ea > 0.12) wc[i] = 1;
          const inv = dist > 0.001 ? 1 / dist : 0;
          wx[i] += dx * inv * h; wy[i] += dy * inv * h;
        }
      }
    }

    // Draw: static layer, cleared cells, ripple shading, live glyphs
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(layer, 0, 0);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (list.length) {
      ctx.fillStyle = CONFIG.paper;
      for (const i of list) {
        const r = (i / cols) | 0, c = i - r * cols;
        ctx.fillRect(c * cellW, r * lineH, cellW, lineH);
      }
    }


    if (list.length) {
      ctx.font = fontString();
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      const tick = Math.floor(t * 14);
      const amp = CONFIG.wobble * motion, refr = CONFIG.refraction * motion;
      gibList.length = 0;
      for (const i of list) {
        if (wc[i]) { gibList.push(i); continue; }
        const r = (i / cols) | 0, c = i - r * cols;
        const f = hf[i];
        const ch = glyphs[i];
        if (ch === " ") continue;
        let dx = wx[i] * refr, dy = wy[i] * refr;
        if (f > 0) {
          dx += Math.sin(t * 6.1 + c * 0.73 + r * 1.31) * amp * f;
          dy += Math.cos(t * 5.3 + c * 1.07 - r * 0.91) * amp * f;
        }
        ctx.fillStyle = palette[Math.round(f * STEPS)];
        ctx.fillText(ch, c * cellW + cellW / 2 + dx, r * lineH + base + dy);
      }
      // Crest glyphs: Japanese / Chinese, drawn a touch smaller so they fit the narrow cells
      if (gibList.length) {
        ctx.font = `${CONFIG.fontSize * 0.78}px ${CJK_FONT}`;
        for (const i of gibList) {
          const r = (i / cols) | 0, c = i - r * cols;
          const f = hf[i];
          const ch = GIB[(hash(i, tick) * GIB.length) | 0];
          let dx = wx[i] * refr, dy = wy[i] * refr;
          if (f > 0) {
            dx += Math.sin(t * 6.1 + c * 0.73 + r * 1.31) * amp * f;
            dy += Math.cos(t * 5.3 + c * 1.07 - r * 0.91) * amp * f;
          }
          ctx.fillStyle = palette[Math.round(f * STEPS)];
          ctx.fillText(ch, c * cellW + cellW / 2 + dx, r * lineH + base + dy);
        }
      }
    }

    animationId = 0;
    if (hoverTarget || hover > 0.005 || drops.length) schedule();
  }

  // Observe pointer events without intercepting application controls.
  function onContentSurface(event) {
    const target = event.target;
    if (!(target instanceof Element)) return false;
    return getComputedStyle(target).getPropertyValue("--engraver-content-surface").trim() === "1"
      || Boolean(target.closest("a, button, input, select, textarea, [role='button'], [contenteditable='true']"));
  }

  function schedule() {
    if (!animationId && !disposed && !document.hidden && !reducedMotion.matches) {
      last = performance.now();
      animationId = requestAnimationFrame(frame);
    }
  }
  function pointerMove(e) {
    if (e.pointerType === "touch") return;
    if (onContentSurface(e)) {
      pointerLeave();
      return;
    }
    mx = e.clientX; my = e.clientY;
    hoverTarget = 1;
    schedule();
  }
  function pointerLeave() { hoverTarget = 0; schedule(); }
  function pointerDown(e) {
    if (e.button > 0 || reducedMotion.matches || onContentSurface(e)) return;
    drops.push({ x: e.clientX, y: e.clientY, t0: performance.now() / 1000 });
    if (drops.length > 8) drops.shift();
    schedule();
  }
  let resizeTimer;
  function resize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rebuild, 80);
  }
  function resetMotion() {
    cancelAnimationFrame(animationId);
    animationId = 0;
    hover = 0; hoverTarget = 0; drops.length = 0;
    rebuild();
  }
  window.addEventListener("pointermove", pointerMove, { passive: true });
  window.addEventListener("pointerdown", pointerDown, { passive: true });
  document.documentElement.addEventListener("pointerleave", pointerLeave);
  window.addEventListener("blur", pointerLeave);
  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", resetMotion);
  reducedMotion.addEventListener("change", resetMotion);
  rebuild();
  Promise.all([
    document.fonts.load(fontString()),
    document.fonts.load(`${CONFIG.fontSize}px ${CJK_FONT}`, CONFIG.gibberish),
  ]).then(rebuild, rebuild);
  return () => {
    disposed = true;
    cancelAnimationFrame(animationId);
    clearTimeout(resizeTimer);
    window.removeEventListener("pointermove", pointerMove);
    window.removeEventListener("pointerdown", pointerDown);
    document.documentElement.removeEventListener("pointerleave", pointerLeave);
    window.removeEventListener("blur", pointerLeave);
    window.removeEventListener("resize", resize);
    document.removeEventListener("visibilitychange", resetMotion);
    reducedMotion.removeEventListener("change", resetMotion);
  };
}
