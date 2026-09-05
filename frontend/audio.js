// Tiny synthesized UI sound set — no audio files, just short Web Audio tones.
// Kept quiet and glassy: a light high shimmer on hover, a softer low tap on
// click. Browsers block audio before a user gesture, so the context is
// created lazily on the first interaction rather than at page load.

const UISound = (() => {
  let ctx = null;
  let lastHoverAt = 0;

  function ensureContext() {
    if (!ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return null;
      ctx = new AudioCtx();
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone({ freq, duration, gain, type, glide }) {
    const audioCtx = ensureContext();
    if (!audioCtx) return;

    const osc = audioCtx.createOscillator();
    const amp = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    if (glide) {
      osc.frequency.exponentialRampToValueAtTime(freq * glide, audioCtx.currentTime + duration);
    }

    amp.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    amp.gain.exponentialRampToValueAtTime(gain, audioCtx.currentTime + 0.008);
    amp.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);

    osc.connect(amp).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration + 0.02);
  }

  function hover() {
    const now = performance.now();
    if (now - lastHoverAt < 90) return; // avoid a rattle on fast mouse travel
    lastHoverAt = now;
    tone({ freq: 1760, duration: 0.09, gain: 0.035, type: "sine", glide: 1.12 });
  }

  function click() {
    tone({ freq: 420, duration: 0.1, gain: 0.06, type: "triangle", glide: 0.6 });
  }

  return { hover, click };
})();

// Delegated so it also covers .rule-chip buttons, which are created fresh
// after every breakdown render rather than existing at page load.
const SOUND_TARGETS = ".cta, .rule-chip, .regime-choice .pill, .addendum summary, .scope-note summary, .sample-chip";

document.addEventListener(
  "mouseenter",
  (event) => {
    const el = event.target.closest && event.target.closest(SOUND_TARGETS);
    if (el && !el.disabled) UISound.hover();
  },
  true // capture phase — mouseenter doesn't bubble
);

document.addEventListener("click", (event) => {
  const el = event.target.closest && event.target.closest(SOUND_TARGETS);
  if (el && !el.disabled) UISound.click();
});
