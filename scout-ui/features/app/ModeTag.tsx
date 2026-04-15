/**
 * ModeTag — tiny honest tag showing whether the current Scout UI is
 * talking to the mock client or a real backend.
 *
 * Block 4 introduces this so demo viewers never mistake seeded Roberts
 * household data for live production state. The tag is read-only; it
 * never changes mode and never blocks rendering.
 *
 * Surfaces that carry meaningful real-vs-mock implications (Control
 * Plane, Scout Assist) render this tag in their header. Today / Rewards
 * / Calendar do not — those surfaces already tell the user something
 * observable (completion flips, payout numbers, scheduled blocks) and
 * the extra tag would add noise.
 */

import { StyleSheet, Text, View } from "react-native";

import { colors } from "../../lib/styles";
import { isRunningMock } from "../lib/availability";

export function ModeTag() {
  const mock = isRunningMock();
  return (
    <View
      style={[styles.tag, mock ? styles.tagMock : styles.tagLive]}
      accessible
      accessibilityLabel={mock ? "Mock data mode" : "Live data mode"}
    >
      <Text style={[styles.text, mock ? styles.textMock : styles.textLive]}>
        {mock ? "MOCK DATA" : "LIVE DATA"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    marginTop: 6,
    marginBottom: 10,
  },
  tagMock: {
    backgroundColor: colors.warningBg,
    borderWidth: 1,
    borderColor: colors.warning,
  },
  tagLive: {
    backgroundColor: colors.positiveBg,
    borderWidth: 1,
    borderColor: colors.positive,
  },
  text: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.8,
  },
  textMock: { color: "#A2660C" },
  textLive: { color: "#00866B" },
});
