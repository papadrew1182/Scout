/**
 * E2E-only crash route. Used by smoke-tests to force a render-time
 * error and verify the global ErrorBoundary catches it.
 *
 * Only active when `EXPO_PUBLIC_SCOUT_E2E=true` is set in the expo
 * export environment. In production builds (where the flag is unset)
 * this route renders a plain "Not available" notice and does NOT
 * throw. The filename starts with `__` so users never discover it
 * accidentally from the app shell.
 */

import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../lib/styles";
import { E2E_TEST_HOOKS } from "../lib/config";

function CrashNow(): JSX.Element {
  throw new Error("Intentional test crash — verifying ErrorBoundary");
}

export default function BoomRoute() {
  const [shouldCrash, setShouldCrash] = useState(false);

  if (!E2E_TEST_HOOKS) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Not available</Text>
        <Text style={styles.body}>
          This route is only enabled in E2E test builds.
        </Text>
      </View>
    );
  }

  if (shouldCrash) {
    return <CrashNow />;
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Boom test route</Text>
      <Text style={styles.body}>Click below to force a render crash.</Text>
      <Pressable
        style={styles.btn}
        onPress={() => setShouldCrash(true)}
        testID="boom-trigger"
      >
        <Text style={styles.btnText}>Trigger crash</Text>
      </Pressable>
    </View>
  );
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
  title: { color: colors.textPrimary, fontSize: 20, fontWeight: "700" },
  body: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: "center",
    maxWidth: 320,
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
