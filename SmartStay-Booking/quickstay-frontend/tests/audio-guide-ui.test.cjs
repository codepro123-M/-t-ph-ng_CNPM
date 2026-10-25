/* Real React rendering in jsdom; provider responses and native media methods are test doubles. */
const assert = require("node:assert/strict");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const esbuild = require("esbuild");
const fe = path.resolve(__dirname, "..");
const bundled = path.join(fe, "node_modules/.cache/audio-guide-dom.cjs");
esbuild.buildSync({
  stdin: {
    contents:
      'export {default as AudioGuide} from \"../src/AudioGuide.jsx\"; export {Context} from \"../src/context.jsx\";',
    resolveDir: __dirname,
    loader: "jsx",
  },
  outfile: bundled,
  bundle: true,
  platform: "node",
  format: "cjs",
  external: ["react"],
  logLevel: "silent",
});
const dom = new JSDOM('<!doctype html><div id="root"></div>', {
  url: "http://localhost:4173/",
});
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "Event",
  "MouseEvent",
  "DOMException",
])
  global[key] = dom.window[key];
Object.defineProperty(global, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
global.IS_REACT_ACT_ENVIRONMENT = true;
const played = [],
  spoken = [];
let rejectNext = false,
  pauseCount = 0;
dom.window.HTMLMediaElement.prototype.play = function () {
  if (rejectNext) {
    rejectNext = false;
    return Promise.reject(new Error("autoplay denied"));
  }
  played.push(this.src);
  return Promise.resolve();
};
dom.window.HTMLMediaElement.prototype.pause = function () {
  pauseCount++;
};
window.speechSynthesis = {
  cancel() {},
  pause() {},
  resume() {},
  getVoices() {
    return [];
  },
  speak(value) {
    spoken.push(value);
  },
};
global.SpeechSynthesisUtterance = class {
  constructor(text) {
    this.text = text;
  }
};
const React = require(path.join(fe, "node_modules/react"));
const { createRoot } = require(path.join(fe, "node_modules/react-dom/client"));
const { act } = React;
const { AudioGuide, Context } = require(bundled);
const id = (n) => n.toString(16).padStart(24, "0");
const source = (n) => ({
  id: id(n),
  name: "Noi luu tru",
  description: "Mo ta tieng Viet",
  language: "vi",
  resolved_lang: "vi",
  audio_url: null,
});
let setPoi,
  prepareCalls = 0,
  prepareImpl,
  detailImpl;
const client = {
  prepareGuide: async (...args) => {
    prepareCalls++;
    return prepareImpl(...args);
  },
  detail: async (...args) => detailImpl(...args),
  guideStatus: async () => ({ status: "ready" }),
};
const context = {
  connection: { mode: "api", base: "/api" },
  client,
  lang: "en",
  t: {
    listen: "Listen to your stay",
    listenSub: "Audio guide",
    play: "Play guide",
    pause: "Pause",
    stop: "Stop",
  },
};
function Harness() {
  const [poi, update] = React.useState(source(1));
  const [language, setLanguage] = React.useState("en");
  setPoi = update;
  return React.createElement(
    Context.Provider,
    { value: context },
    React.createElement(AudioGuide, {
      poi,
      language,
      setLanguage,
      onPrepared: update,
    }),
  );
}
const renderer = createRoot(document.getElementById("root"));
const click = async (button) =>
  act(async () => {
    button.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
const first = () => document.querySelector("button");
(async () => {
  await act(async () => renderer.render(React.createElement(Harness)));
  let finish;
  prepareImpl = () => new Promise((resolve) => (finish = resolve));
  detailImpl = async () => ({
    ...source(1),
    language: "en",
    resolved_lang: "en",
    audio_url: "/media/" + id(101),
  });
  await click(first());
  assert.equal(first().disabled, true);
  assert.match(first().textContent, /Preparing/);
  await act(async () => {
    finish({ status: "ready" });
    await Promise.resolve();
  });
  assert.equal(played.length, 1);
  assert.ok(played[0].endsWith("/media/" + id(101)));
  assert.match(first().textContent, /Pause/);
  assert.equal(
    pauseCount,
    1,
    "a fresh recording must not be stopped immediately by the source-update effect",
  );
  await click(first());
  assert.match(first().textContent, /Play/);
  await click(first());
  assert.equal(played.length, 2);
  await click(document.querySelector('button[aria-label="Stop"]'));
  await click(first());
  assert.equal(prepareCalls, 1);
  assert.equal(played.length, 3);
  console.log(
    "PASS: React prepares, switches to the saved recording, auto-plays, pauses/resumes and reuses cached audio",
  );
  await act(async () => setPoi(source(2)));
  prepareImpl = async () => ({ status: "ready" });
  detailImpl = async () => ({
    ...source(2),
    language: "en",
    audio_url: "/media/" + id(102),
  });
  rejectNext = true;
  await click(first());
  assert.match(
    document.querySelector(".form-error").textContent,
    /recording is ready/,
  );
  const calls = prepareCalls;
  await click(first());
  assert.equal(prepareCalls, calls);
  assert.ok(played.at(-1).endsWith(id(102)));
  console.log(
    "PASS: browser autoplay rejection offers a manual play without recreating the audio task",
  );
  await act(async () => setPoi(source(3)));
  prepareImpl = async () => {
    throw new Error("Translation provider unavailable; retry later");
  };
  await click(first());
  assert.match(
    document.querySelector(".form-error").textContent,
    /Translation provider unavailable/,
  );
  await click(
    [...document.querySelectorAll("button")].find((button) =>
      button.textContent.includes("browser voice"),
    ),
  );
  assert.equal(spoken.length, 1);
  assert.equal(spoken[0].lang, "vi-VN");
  console.log(
    "PASS: provider failure is visible; browser fallback reads the actual current content language",
  );
  await act(async () => setPoi(source(4)));
  prepareImpl = () => new Promise((resolve) => (finish = resolve));
  detailImpl = async () => ({
    ...source(4),
    language: "en",
    audio_url: "/media/" + id(104),
  });
  await click(first());
  const before = played.length;
  await click(document.querySelector('button[aria-label="Stop"]'));
  await act(async () => {
    finish({ status: "ready" });
    await Promise.resolve();
  });
  assert.equal(played.length, before);
  assert.equal(first().disabled, false);
  console.log(
    "PASS: stopping preparation suppresses late results and unwanted playback",
  );
  await act(async () => renderer.unmount());
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
