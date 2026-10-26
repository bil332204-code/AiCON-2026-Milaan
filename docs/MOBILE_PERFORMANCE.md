# Mobile visual-performance budget

The interactive canvas is decorative and deliberately reduces geometry density, frame frequency and pixel-density on narrow/mobile or data-saver browsers; desktop keeps its visual identity. Reduced-motion users already avoid continuous animation.

**Measured from the shipped source**: run `python scripts/frontend_perf_budget.py` to record the exact uncompressed JS/CSS byte count (budget ≤350,000 bytes); the report prints per-file bytes. This is a **source-size** check, not actual transferred gzip bytes, device FPS, Core Web Vitals, or proof of a Lighthouse score.

**Real mobile measurement (operator-run):** use a disposable preview build, Chrome mobile/4G emulation, and run `npx --yes lighthouse http://127.0.0.1:8000/ --only-categories=performance,accessibility --preset=desktop --output=json --output-path=/tmp/milaan-lighthouse.json` for a desktop baseline; for simulated mobile omit `--preset=desktop`. Record LCP/CLS/INP and run on identical throttling/device settings before and after. Do not report scores until actually executed.

**Expected trade-off**: animation contours contain fewer subpixel particles on narrow screens; core information, SHIP/HOLD/REVIEW labels and all controls remain available regardless of motion. No third-party dependency was installed.
