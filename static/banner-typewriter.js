(function () {
  const node = document.querySelector(".page-banner-typewriter");
  if (!node) {
    return;
  }

  let phrases = [];
  try {
    phrases = JSON.parse(node.dataset.typewriterPhrases || "[]");
  } catch {
    phrases = [];
  }

  phrases = phrases.filter((phrase) => typeof phrase === "string" && phrase.trim());
  if (!phrases.length) {
    return;
  }

  const textNode = node.querySelector(".typewriter-text");
  const cursorNode = node.querySelector(".typewriter-cursor");
  if (!textNode) {
    return;
  }

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) {
    textNode.textContent = phrases[0];
    cursorNode?.remove();
    return;
  }

  const TYPE_MS = 46;
  const DELETE_MS = 28;
  const HOLD_MS = 2400;
  const BETWEEN_MS = 520;

  let currentIndex = -1;
  let charIndex = 0;
  let deleting = false;
  let timerId = null;

  function pickNextIndex() {
    if (phrases.length === 1) {
      return 0;
    }

    let next = currentIndex;
    while (next === currentIndex) {
      next = Math.floor(Math.random() * phrases.length);
    }
    return next;
  }

  function jitter(base) {
    return base + Math.floor(Math.random() * 36);
  }

  function pauseAfterPunctuation(base) {
    const char = phrases[currentIndex]?.[charIndex - 1];
    if (char === "." || char === "!" || char === "?" || char === ",") {
      return base + 220;
    }
    return base;
  }

  function tick() {
    const phrase = phrases[currentIndex];

    if (!deleting) {
      charIndex += 1;
      textNode.textContent = phrase.slice(0, charIndex);

      if (charIndex >= phrase.length) {
        deleting = true;
        timerId = window.setTimeout(tick, HOLD_MS);
        return;
      }

      timerId = window.setTimeout(tick, pauseAfterPunctuation(jitter(TYPE_MS)));
      return;
    }

    charIndex -= 1;
    textNode.textContent = phrase.slice(0, charIndex);

    if (charIndex <= 0) {
      deleting = false;
      currentIndex = pickNextIndex();
      charIndex = 0;
      timerId = window.setTimeout(tick, BETWEEN_MS);
      return;
    }

    timerId = window.setTimeout(tick, jitter(DELETE_MS));
  }

  function start() {
    currentIndex = pickNextIndex();
    charIndex = 0;
    deleting = false;
    textNode.textContent = "";
    timerId = window.setTimeout(tick, 400);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      window.clearTimeout(timerId);
      return;
    }
    window.clearTimeout(timerId);
    timerId = window.setTimeout(tick, 300);
  });

  start();
})();
