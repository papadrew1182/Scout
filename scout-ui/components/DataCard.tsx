/**
 * DataCard — lightweight wrapper for cards that load async data.
 *
 * Normalizes loading / error / empty rendering so every card across
 * every surface follows the same pattern without duplicating the
 * if/else chain.
 */

import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { colors, shared } from "../lib/styles";

interface Props {
  title?: string;
  loading: boolean;
  error: string | null;
  empty: boolean;
  emptyText?: string;
  children: React.ReactNode;
}

export function DataCard({
  title,
  loading: isLoading,
  error,
  empty,
  emptyText = "No data available",
  children,
}: Props) {
  return (
    <View style={shared.card}>
      {title && <Text style={styles.title}>{title}</Text>}
      {isLoading && (
        <ActivityIndicator size="small" color={colors.accent} style={styles.spinner} />
      )}
      {!isLoading && error && <Text style={shared.errorText}>{error}</Text>}
      {!isLoading && !error && empty && (
        <Text style={shared.emptyText}>{emptyText}</Text>
      )}
      {!isLoading && !error && !empty && children}
    </View>
  );
}

const styles = StyleSheet.create({
  title: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: -0.2,
    marginBottom: 10,
  },
  spinner: { marginTop: 4, alignSelf: "flex-start" },
});
