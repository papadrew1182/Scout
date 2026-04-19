import React from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { useRef, useEffect } from "react";
import { colors, fonts } from "../../lib/styles";
import { useAffirmation } from "./useAffirmation";

export function AffirmationCard() {
  const { affirmation, loading, reacted, react } = useAffirmation();
  const fadeAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (reacted) {
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 400,
        useNativeDriver: true,
      }).start();
    }
  }, [reacted, fadeAnim]);

  if (loading || !affirmation || reacted) {
    if (reacted) {
      return (
        <Animated.View style={[styles.card, { opacity: fadeAnim }]}>
          <Text style={styles.text}>{affirmation?.text}</Text>
        </Animated.View>
      );
    }
    return null;
  }

  return (
    <View style={styles.card}>
      <Text style={styles.sparkle}>✦</Text>
      <Text style={styles.text}>{affirmation.text}</Text>
      {affirmation.category && (
        <Text style={styles.meta}>
          {affirmation.category}
          {affirmation.tone ? ` · ${affirmation.tone}` : ""}
        </Text>
      )}
      <View style={styles.reactions}>
        <ReactionButton label="Heart" icon="♡" onPress={() => react("heart")} />
        <ReactionButton label="Nope" icon="👎" onPress={() => react("thumbs_down")} />
        <ReactionButton label="Skip" icon="→" onPress={() => react("skip")} />
        <ReactionButton label="Later" icon="↻" onPress={() => react("reshow")} />
      </View>
    </View>
  );
}

function ReactionButton({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={styles.reactionBtn}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label} this affirmation`}
    >
      <Text style={styles.reactionIcon}>{icon}</Text>
      <Text style={styles.reactionLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.purpleLight,
    borderRadius: 12,
    padding: 18,
    marginBottom: 14,
  },
  sparkle: {
    fontSize: 16,
    color: colors.purple,
    marginBottom: 6,
  },
  text: {
    fontSize: 16,
    fontWeight: "500",
    color: colors.text,
    fontFamily: fonts.body,
    lineHeight: 24,
  },
  meta: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    marginTop: 8,
  },
  reactions: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  reactionBtn: {
    alignItems: "center",
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  reactionIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  reactionLabel: {
    fontSize: 11,
    color: colors.muted,
    fontFamily: fonts.body,
  },
});
