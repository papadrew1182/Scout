import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../lib/styles";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  message: string | null;
}

/**
 * Top-level error boundary for the Scout app shell.
 *
 * Catches render-time errors anywhere below the shell and renders a
 * minimal recovery fallback with a reload control. Without this, a
 * thrown error inside any Expo Router screen would leave a blank page.
 *
 * Per-component error handling (ActivityIndicator/Retry) is still the
 * preferred path for expected failures — this only covers unexpected
 * render crashes.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || "Unknown error" };
  }

  componentDidCatch(error: Error, info: unknown) {
    // Logged to stdout / DevTools. A production error reporting provider
    // (e.g. Sentry) can hook in here once one is wired up.
    console.error("[Scout ErrorBoundary]", error, info);
  }

  reset = () => {
    this.setState({ hasError: false, message: null });
    if (typeof window !== "undefined" && typeof window.location?.reload === "function") {
      window.location.reload();
    }
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <View style={styles.wrap} testID="scout-error-boundary">
        <Text style={styles.title}>Something went wrong</Text>
        <Text style={styles.body}>
          Scout hit an unexpected error. Reloading usually fixes it.
        </Text>
        {this.state.message && (
          <Text style={styles.detail}>{this.state.message}</Text>
        )}
        <Pressable style={styles.btn} onPress={this.reset}>
          <Text style={styles.btnText}>Reload</Text>
        </Pressable>
      </View>
    );
  }
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    gap: 12,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: "700",
  },
  body: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: "center",
    maxWidth: 320,
  },
  detail: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: "monospace",
    textAlign: "center",
    maxWidth: 360,
  },
  btn: {
    marginTop: 12,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 24,
  },
  btnText: {
    color: colors.buttonPrimaryText,
    fontSize: 14,
    fontWeight: "700",
  },
});
