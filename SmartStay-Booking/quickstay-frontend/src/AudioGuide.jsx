import React, { useEffect, useRef, useState } from "react";
import { Globe2, Headphones, Loader2, Pause, Play, Square } from "lucide-react";
import { mediaUrl } from "./api.mjs";
import { useApp } from "./context.jsx";

function delay(signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, 1500);
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}

export default function AudioGuide({ poi, language, setLanguage, onPrepared }) {
  const { connection, client, t, lang } = useApp();
  const [playing, setPlaying] = useState(false),
    [paused, setPaused] = useState(false),
    [preparing, setPreparing] = useState(false),
    [error, setError] = useState(""),
    [browser, setBrowser] = useState(false);
  const audio = useRef(null),
    request = useRef(null),
    pendingPlay = useRef(false),
    source = useRef("recording");
  const src = poi.audio_url ? mediaUrl(poi.audio_url, connection.base) : null;
  const say = (vi, en) => (lang === "vi" ? vi : en);
  function stop() {
    request.current?.abort();
    pendingPlay.current = false;
    audio.current?.pause();
    if (audio.current) audio.current.currentTime = 0;
    window.speechSynthesis?.cancel();
    setPlaying(false);
    setPaused(false);
    setPreparing(false);
  }
  useEffect(() => {
    stop();
    setError("");
    setBrowser(false);
    return () => {
      request.current?.abort();
      audio.current?.pause();
      window.speechSynthesis?.cancel();
    };
  }, [poi.id, language, connection.base]);
  useEffect(() => {
    if (pendingPlay.current && src) {
      pendingPlay.current = false;
      audio.current
        .play()
        .then(() => setPlaying(true))
        .catch(() =>
          setError(
            say(
              "Bản ghi đã sẵn sàng. Nhấn Nghe để phát.",
              "Your recording is ready. Press Play to listen.",
            ),
          ),
        );
    }
  }, [src]);

  async function prepare() {
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    setPreparing(true);
    setError("");
    try {
      let state = await client.prepareGuide(poi.id, language, {
        signal: controller.signal,
      });
      const deadline = Date.now() + 180000;
      while (state.status !== "ready") {
        if (["failed", "cancelled", "paused"].includes(state.status))
          throw new Error(
            state.error ||
              say(
                "Chưa tạo được thuyết minh. Vui lòng thử lại.",
                "Audio preparation could not finish. Please retry.",
              ),
          );
        if (Date.now() > deadline)
          throw new Error(
            say(
              "Thuyết minh vẫn đang được tạo. Hãy thử lại sau một lát.",
              "Your guide is still processing. Please try again shortly.",
            ),
          );
        await delay(controller.signal);
        state = await client.guideStatus(poi.id, language, {
          signal: controller.signal,
        });
      }
      const fresh = await client.detail(poi.id, language, {
        signal: controller.signal,
      });
      if (!fresh.audio_url || fresh.language !== language)
        throw new Error(
          say(
            "Nguồn nội dung đã thay đổi. Vui lòng thử lại.",
            "The source content changed. Please retry.",
          ),
        );
      if (!controller.signal.aborted) {
        source.current = "recording";
        setBrowser(false);
        pendingPlay.current = true;
        onPrepared(fresh);
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setError(
          e.status === 429
            ? say(
                "Bạn đã yêu cầu quá nhiều lần. Hãy đợi vài phút.",
                "Too many requests. Please wait a few minutes.",
              )
            : e.message ||
                say(
                  "Dịch vụ thuyết minh chưa kết nối được.",
                  "The audio service is unavailable.",
                ),
        );
    } finally {
      if (!controller.signal.aborted) setPreparing(false);
    }
  }

  async function play(useBrowser = false) {
    setError("");
    if (playing && !paused) {
      if (source.current === "recording") audio.current.pause();
      else window.speechSynthesis?.pause();
      setPaused(true);
      return;
    }
    if (paused) {
      if (source.current === "recording") {
        try {
          await audio.current.play();
        } catch {
          setError(
            say("Không phát được bản ghi.", "Unable to play this recording."),
          );
          return;
        }
      } else window.speechSynthesis?.resume();
      setPaused(false);
      return;
    }
    if (
      !useBrowser &&
      connection.mode === "api" &&
      (!src || poi.language !== language)
    )
      return prepare();
    if (!useBrowser && src) {
      source.current = "recording";
      setBrowser(false);
      try {
        await audio.current.play();
        setPlaying(true);
      } catch {
        setError(
          say(
            "Không phát được bản ghi. Bạn có thể dùng giọng đọc trình duyệt bên dưới.",
            "The recording could not play. You can use the browser voice below.",
          ),
        );
      }
      return;
    }
    if (!window.speechSynthesis) {
      setError(
        say(
          "Trình duyệt chưa hỗ trợ giọng đọc.",
          "This browser does not support read-aloud.",
        ),
      );
      return;
    }
    source.current = "browser";
    setBrowser(true);
    const resolved = poi.language || poi.resolved_lang || "vi";
    const utterance = new SpeechSynthesisUtterance(
      poi.name + ". " + poi.description,
    );
    utterance.lang =
      { vi: "vi-VN", en: "en-US", zh: "zh-CN", ja: "ja-JP", ko: "ko-KR" }[
        resolved
      ] || resolved;
    utterance.rate = 0.92;
    const voice = window.speechSynthesis
      .getVoices()
      .find((v) => v.lang.toLowerCase().startsWith(resolved));
    if (voice) utterance.voice = voice;
    utterance.onend = () => {
      setPlaying(false);
      setPaused(false);
    };
    utterance.onerror = (e) => {
      setPlaying(false);
      if (!["canceled", "interrupted"].includes(e.error))
        setError(
          say(
            "Không tìm thấy giọng đọc phù hợp.",
            "No suitable browser voice is available.",
          ),
        );
    };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setPlaying(true);
  }
  return (
    <section className="audio-guide">
      <div className="audio-guide-title">
        <span className="headphone-icon">
          <Headphones size={21} />
        </span>
        <div>
          <h3>{t.listen}</h3>
          <p>{t.listenSub}</p>
        </div>
        <label className="audio-language">
          <Globe2 size={16} />
          <select
            aria-label="Narration language"
            value={language}
            onChange={(e) => {
              stop();
              setLanguage(e.target.value);
            }}
          >
            <option value="en">English</option>
            <option value="vi">Tiếng Việt</option>
            <option value="zh">中文</option>
            <option value="ja">日本語</option>
            <option value="ko">한국어</option>
          </select>
        </label>
      </div>
      <div className="audio-control-row">
        <button
          className="button button-blue"
          onClick={() => play()}
          disabled={preparing}
        >
          {preparing ? (
            <Loader2 size={15} className="spin" />
          ) : playing && !paused ? (
            <Pause size={15} />
          ) : (
            <Play size={15} />
          )}
          {preparing
            ? say("Đang tạo thuyết minh…", "Preparing your guide…")
            : playing && !paused
              ? t.pause
              : t.play}
        </button>
        {(playing || preparing) && (
          <button className="icon-button" aria-label={t.stop} onClick={stop}>
            <Square size={15} />
          </button>
        )}
        <span>
          {browser || connection.mode === "demo"
            ? say("Giọng đọc trình duyệt", "Browser read-aloud")
            : say("Bản ghi thuyết minh từ máy chủ", "Server audio recording")}
        </span>
      </div>
      {poi.language !== language && (
        <p className="guide-note">
          {say("Nội dung hiện tại: ", "Current text: ")}
          {(poi.language || "vi").toUpperCase()}
          {say(
            ". Nhấn Nghe để chuẩn bị ngôn ngữ đã chọn.",
            ". Press Play to prepare the selected language.",
          )}
        </p>
      )}
      {preparing && (
        <p className="guide-note" role="status">
          {say(
            "Lần đầu cần thời gian để dịch và tạo giọng nói. Bản ghi sẽ được lưu cho lần nghe sau.",
            "The first listen takes a little time to translate and generate speech. Your recording will be saved for future visits.",
          )}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {error && !preparing && (
        <button
          className="text-link"
          onClick={() => {
            stop();
            play(true);
          }}
        >
          {say(
            "Đọc nội dung hiện tại bằng giọng trình duyệt",
            "Read the current text with a browser voice",
          )}
        </button>
      )}
      <audio
        ref={audio}
        src={src || undefined}
        preload="none"
        onEnded={() => {
          setPlaying(false);
          setPaused(false);
        }}
        onError={() => {
          if (src) {
            setPlaying(false);
            setError(
              say(
                "Bản ghi hiện chưa tải được.",
                "The recording could not be loaded.",
              ),
            );
          }
        }}
      />
    </section>
  );
}
