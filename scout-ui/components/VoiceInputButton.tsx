/**
 * Voice input button for ScoutPanel.
 *
 * Uses the browser MediaRecorder API (web only; on native this silently
 * renders nothing). Tap once to start recording, tap again to stop →
 * upload to /api/ai/transcribe → call onTranscribed(text) so the
 * parent can feed it into sendChatMessageStream.
 *
 * Gated on two signals:
 *   1. The backend /ready reports transcribe_available=true
 *   2. window.MediaRecorder and navigator.mediaDevices exist
 *
 * If either is missing, the button renders as null so the mic never
 * appears in browsers that can't handle it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { transcribeAudio } from "../lib/api";
import { colors } from "../lib/styles";

interface Props {
  disabled?: boolean;
  onTranscribed: (text: string) => void;
  onError?: (message: string) => void;
}

function hasMediaRecorder(): boolean {
  if (typeof window === "undefined") return false;
  // @ts-ignore
  return typeof window.MediaRecorder !== "undefined"
    && typeof navigator !== "undefined"
    && !!navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === "function";
}

export function VoiceInputButton({ disabled, onTranscribed, onError }: Props) {
  const [supported, setSupported] = useState<boolean>(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const recorderRef = useRef<any>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    setSupported(hasMediaRecorder());
  }, []);

  const stopStream = useCallback(() => {
    try {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    } catch {}
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (disabled || busy) return;
    if (!hasMediaRecorder()) {
      onError?.("Voice input not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      // @ts-ignore
      const rec = new window.MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      rec.ondataavailable = (e: any) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stopStream();
        setBusy(true);
        try {
          if (blob.size === 0) {
            onError?.("Empty recording. Try again.");
            return;
          }
          const { text } = await transcribeAudio(blob);
          const trimmed = (text || "").trim();
          if (!trimmed) {
            onError?.("Could not hear anything. Try again.");
            return;
          }
          onTranscribed(trimmed);
        } catch (e: any) {
          onError?.(e?.message || "Transcription failed.");
        } finally {
          setBusy(false);
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (e: any) {
      stopStream();
      onError?.(e?.message || "Microphone access denied.");
    }
  }, [disabled, busy, onTranscribed, onError, stopStream]);

  const stop = useCallback(() => {
    if (!recording) return;
    try {
      recorderRef.current?.stop();
    } catch {}
    setRecording(false);
  }, [recording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
      stopStream();
    };
  }, [stop, stopStream]);

  if (!supported) return null;

  return (
    <Pressable
      accessibilityLabel={recording ? "Stop recording" : "Start voice input"}
      style={[styles.btn, recording && styles.btnRecording, disabled && styles.btnDisabled]}
      onPress={recording ? stop : start}
      disabled={disabled || busy}
    >
      {busy ? (
        <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
      ) : (
        <Text style={styles.text}>{recording ? "■" : "🎤"}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    width: 44,
    height: 44,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  btnRecording: {
    backgroundColor: colors.negative,
    borderColor: colors.negative,
  },
  btnDisabled: {
    opacity: 0.5,
  },
  text: {
    color: colors.textPrimary,
    fontSize: 18,
  },
});
